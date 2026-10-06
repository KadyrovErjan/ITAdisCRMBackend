"""Contract schedule creation, allocation and date-aware financial summaries."""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from ..models import (
    PaymentAllocation, PaymentNotification, PaymentPlan, PaymentScheduleItem,
    PaymentSchedulePause, Student, Transaction,
)
from .audit import log_action

ZERO = Decimal('0.00')
CENT = Decimal('0.01')


def add_months(value, months):
    target = value.month - 1 + months
    year, month = value.year + target // 12, target % 12 + 1
    return value.replace(year=year, month=month, day=min(value.day, monthrange(year, month)[1]))


def monthly_amounts(total, periods):
    if periods < 1:
        raise ValidationError({'period_count': 'Количество периодов должно быть больше нуля.'})
    base = (total / periods).quantize(CENT, rounding=ROUND_DOWN)
    return [base] * (periods - 1) + [total - base * (periods - 1)]


def item_paid(item):
    if 'allocations' in getattr(item, '_prefetched_objects_cache', {}):
        return sum((allocation.amount for allocation in item._prefetched_objects_cache['allocations']), ZERO)
    return item.allocations.aggregate(value=Sum('amount'))['value'] or ZERO


def item_outstanding(item):
    return max(ZERO, item.amount_due - item_paid(item))


def build_plan(student, *, method, period_count, start_date, items, actor):
    """Create a confirmed plan. Existing receipts are allocated, never rewritten."""
    if student.course_price is None:
        raise ValidationError({'course_price': 'Для графика требуется договорная стоимость.'})
    if PaymentPlan.objects.filter(student=student).exists():
        raise ValidationError({'plan': 'У ученика уже есть подтверждённый график.'})
    if method not in {'full', 'monthly', 'custom'}:
        raise ValidationError({'payment_method': 'Недопустимый способ оплаты.'})
    if method == 'full':
        normalized = [{'due_date': start_date, 'amount_due': student.course_price}]
        period_count = 1
    elif method == 'monthly':
        amounts = monthly_amounts(student.course_price, period_count)
        normalized = [{'due_date': add_months(start_date, index), 'amount_due': value} for index, value in enumerate(amounts)]
    else:
        normalized = items or []
        period_count = len(normalized)
    if not normalized:
        raise ValidationError({'items': 'Нужен хотя бы один пункт графика.'})
    normalized = [
        {
            'due_date': item['due_date'] if isinstance(item['due_date'], date) else date.fromisoformat(str(item['due_date'])),
            'amount_due': Decimal(str(item['amount_due'])),
        }
        for item in normalized
    ]
    if sum(item['amount_due'] for item in normalized) != student.course_price:
        raise ValidationError({'items': 'Сумма графика должна в точности совпадать с договорной стоимостью.'})
    with transaction.atomic():
        plan = PaymentPlan.objects.create(student=student, payment_method=method, period_count=period_count, start_date=start_date, created_by=actor)
        PaymentScheduleItem.objects.bulk_create([
            PaymentScheduleItem(plan=plan, student=student, due_date=item['due_date'], amount_due=item['amount_due'])
            for item in sorted(normalized, key=lambda item: item['due_date'])
        ])
        allocate_unallocated_transactions(student)
        log_action(actor, 'payment_plan.create', 'PaymentPlan', plan.id, {'student_id': str(student.id), 'method': method, 'period_count': period_count})
    return plan


def adjust_plan(student, *, items, actor):
    """Safely amend a confirmed schedule without touching receipts or allocations.

    A cashier may amend only a plan with no allocations. Once money has been
    attributed, a director may change future, completely unallocated rows only.
    The payload must keep those protected rows and preserve the contract sum.
    """
    with transaction.atomic():
        plan = PaymentPlan.objects.select_for_update().get(student=student)
        current = list(plan.items.select_for_update().prefetch_related('allocations').order_by('due_date', 'created_at'))
        has_allocations = PaymentAllocation.objects.filter(schedule_item__plan=plan).exists()
        if has_allocations and actor.role != 'director':
            raise ValidationError({'detail': 'После первой оплаты график может корректировать только директор.'})

        normalized = [
            {'id': str(row.get('id', '')), 'due_date': row['due_date'] if isinstance(row['due_date'], date) else date.fromisoformat(str(row['due_date'])), 'amount_due': Decimal(str(row['amount_due']))}
            for row in items
        ]
        if not normalized or any(row['amount_due'] <= ZERO for row in normalized):
            raise ValidationError({'items': 'Каждый пункт графика должен иметь положительную сумму.'})
        if sum(row['amount_due'] for row in normalized) != student.course_price:
            raise ValidationError({'items': 'Сумма графика должна в точности совпадать с договорной стоимостью.'})

        by_id = {str(item.id): item for item in current}
        submitted_ids = {row['id'] for row in normalized if row['id']}
        protected = [item for item in current if item.allocations.exists()]
        if any(str(item.id) not in submitted_ids for item in protected):
            raise ValidationError({'items': 'Нельзя удалить оплаченный пункт графика.'})
        for row in normalized:
            old = by_id.get(row['id'])
            if old and old.allocations.exists():
                if row['amount_due'] < item_paid(old) or row['due_date'] != old.due_date:
                    raise ValidationError({'items': 'Нельзя менять дату или сумму оплаченного пункта.'})
            elif has_allocations and old and old.due_date < timezone.localdate():
                raise ValidationError({'items': 'Директор может менять только будущие непогашенные пункты.'})

        before = [{'id': str(item.id), 'due_date': item.due_date.isoformat(), 'amount_due': str(item.amount_due)} for item in current]
        # Delete only rows which have never received an allocation.
        for item in current:
            if str(item.id) not in submitted_ids and not item.allocations.exists():
                item.delete()
        for row in normalized:
            old = by_id.get(row['id'])
            if old:
                old.due_date, old.amount_due = row['due_date'], row['amount_due']
                old.save(update_fields=['due_date', 'amount_due', 'updated_at'])
            else:
                PaymentScheduleItem.objects.create(plan=plan, student=student, due_date=row['due_date'], amount_due=row['amount_due'])
        plan.period_count = len(normalized)
        plan.payment_method = 'custom'
        plan.save(update_fields=['period_count', 'payment_method', 'updated_at'])
        log_action(actor, 'payment_plan.adjust', 'PaymentPlan', plan.id, {
            'student_id': str(student.id), 'before': before,
            'after': [{'due_date': row['due_date'].isoformat(), 'amount_due': str(row['amount_due'])} for row in normalized],
        })
    return plan


def allocate_unallocated_transactions(student):
    """Allocate every real receipt once. Safe to call repeatedly under DB locks."""
    with transaction.atomic():
        items = list(PaymentScheduleItem.objects.select_for_update().filter(student=student).order_by('due_date', 'created_at'))
        for receipt in Transaction.objects.select_for_update().filter(student=student).order_by('created_at', 'id'):
            already = receipt.payment_allocations.aggregate(value=Sum('amount'))['value'] or ZERO
            remaining = receipt.amount - already
            if remaining <= ZERO:
                continue
            for item in items:
                outstanding = item_outstanding(item)
                if outstanding <= ZERO:
                    continue
                allocated = min(remaining, outstanding)
                PaymentAllocation.objects.create(transaction=receipt, schedule_item=item, amount=allocated)
                remaining -= allocated
                if remaining <= ZERO:
                    break


def allocate_transaction(receipt):
    allocate_unallocated_transactions(receipt.student)


def financial_summary(student, today=None):
    today = today or timezone.localdate()
    try:
        plan = student.payment_plan
    except PaymentPlan.DoesNotExist:
        return {'payment_status': 'unknown', 'total_paid': str(student.amount_paid_total), 'due_now': '0.00', 'overdue_amount': '0.00', 'contract_remaining': None, 'next_payment_amount': None, 'next_payment_date': None, 'credit_amount': '0.00'}
    if 'items' in getattr(plan, '_prefetched_objects_cache', {}):
        items = sorted(plan._prefetched_objects_cache['items'], key=lambda item: (item.due_date, item.created_at))
    else:
        items = list(plan.items.prefetch_related('allocations').order_by('due_date', 'created_at'))
    total_paid = getattr(student, 'total_paid', None)
    if total_paid is None:
        total_paid = student.amount_paid_total
    outstanding = [(item, item_outstanding(item)) for item in items]
    due_now = sum((amount for item, amount in outstanding if item.due_date == today), ZERO)
    overdue = sum((amount for item, amount in outstanding if item.due_date < today), ZERO)
    next_item = next(((item, amount) for item, amount in outstanding if amount > ZERO), None)
    credit = max(ZERO, total_paid - student.course_price)
    remaining = max(ZERO, student.course_price - total_paid)
    if credit > ZERO:
        payment_status = 'overpaid'
    elif remaining == ZERO:
        payment_status = 'paid'
    elif overdue > ZERO:
        payment_status = 'overdue'
    elif due_now > ZERO:
        payment_status = 'due'
    else:
        payment_status = 'upcoming'
    return {
        'payment_status': payment_status, 'total_paid': str(total_paid), 'due_now': str(due_now),
        'overdue_amount': str(overdue), 'contract_remaining': str(remaining),
        'next_payment_amount': str(next_item[1]) if next_item else None,
        'next_payment_date': next_item[0].due_date.isoformat() if next_item else None,
        'credit_amount': str(credit),
    }


def freeze_student(student, actor, started_on=None, reason=''):
    started_on = started_on or timezone.localdate()
    try:
        student.payment_plan
    except PaymentPlan.DoesNotExist:
        # Freezing a legacy learner remains valid but has no financial pause.
        student.learning_status = 'frozen'
        student.save(update_fields=['learning_status'])
        log_action(actor, 'student.freeze', 'Student', student.id, {'started_on': started_on, 'financial_plan': False})
        return None
    with transaction.atomic():
        if PaymentSchedulePause.objects.filter(student=student, ended_on__isnull=True).exists():
            raise ValidationError({'freeze': 'Ученик уже заморожен.'})
        student.learning_status = 'frozen'
        student.save(update_fields=['learning_status'])
        pause = PaymentSchedulePause.objects.create(student=student, started_on=started_on, reason=reason, created_by=actor)
        log_action(actor, 'student.freeze', 'Student', student.id, {'started_on': started_on})
    return pause


def resume_student(student, actor, ended_on=None):
    ended_on = ended_on or timezone.localdate()
    try:
        student.payment_plan
    except PaymentPlan.DoesNotExist:
        student.learning_status = 'active'
        student.save(update_fields=['learning_status'])
        log_action(actor, 'student.resume', 'Student', student.id, {'ended_on': ended_on, 'financial_plan': False})
        return None
    with transaction.atomic():
        pause = PaymentSchedulePause.objects.select_for_update().filter(student=student, ended_on__isnull=True).latest('started_on')
        shifted_days = max(0, (ended_on - pause.started_on).days)
        # Preserve previously overdue obligations; only obligations that had not
        # become due before freeze are shifted.
        for item in PaymentScheduleItem.objects.select_for_update().filter(student=student, due_date__gte=pause.started_on):
            # A fully settled period is financial history, not a future
            # obligation.  Freezing must never rewrite its due date.
            if item_outstanding(item) <= ZERO:
                continue
            item.due_date += timedelta(days=shifted_days)
            item.save(update_fields=['due_date', 'updated_at'])
        pause.ended_on, pause.shifted_days = ended_on, shifted_days
        pause.save(update_fields=['ended_on', 'shifted_days'])
        student.learning_status = 'active'
        student.save(update_fields=['learning_status'])
        log_action(actor, 'student.resume', 'Student', student.id, {'ended_on': ended_on, 'shifted_days': shifted_days})
    return pause


def generate_notifications(today=None):
    today = today or timezone.localdate()
    created = 0
    for item in PaymentScheduleItem.objects.select_related('student__group', 'student__registered_by').prefetch_related('allocations'):
        if PaymentSchedulePause.objects.filter(student=item.student, ended_on__isnull=True).exists():
            # A live pause stops new reminder/escalation events. Any already
            # overdue item remains financially overdue, but is not spammed.
            continue
        outstanding = item_outstanding(item)
        if outstanding <= ZERO:
            PaymentNotification.objects.filter(schedule_item=item, resolved_at__isnull=True).update(resolved_at=timezone.now())
            continue
        if item.due_date == today + timedelta(days=3):
            kind, prefix = 'upcoming', 'Скоро оплата'
        elif item.due_date < today:
            kind, prefix = 'overdue', 'Просрочен платёж' if outstanding == item.amount_due else 'Осталась задолженность'
        else:
            continue
        key = f'{item.id}:{kind}'
        message = f'{prefix}: {item.student.full_name} — {outstanding} сом. Срок оплаты: {item.due_date}. Группа: {item.student.group.name}.'
        _, was_created = PaymentNotification.objects.get_or_create(recipient=item.student.registered_by, student=item.student, schedule_item=item, kind=kind, event_key=key, defaults={'message': message})
        created += int(was_created)
    return created
