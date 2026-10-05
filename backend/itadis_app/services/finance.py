"""
Сервисный слой для финансовых операций
Согласно ТЗ раздел 7 - все операции атомарные с блокировками
"""
from decimal import Decimal
from hashlib import sha256
import json
from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError as DRFValidationError
import logging

from ..models import User, Student, Group, Transaction, Balance, Collection, Expense, IdempotencyKey
from .audit import log_action

logger = logging.getLogger(__name__)


def _request_hash(payload: dict) -> str:
    """Stable fingerprint used to reject a reused idempotency key with new data."""
    normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return sha256(normalized.encode('utf-8')).hexdigest()


def _reserve_idempotency_key(cashier, key, operation, payload):
    """Returns an existing completed request or reserves a new key atomically."""
    if not key:
        return None, False

    key = str(key).strip()
    if not key or len(key) > 64:
        raise DRFValidationError({'idempotency_key': _('Некорректный ключ идемпотентности')})

    request_hash = _request_hash(payload)
    try:
        record = IdempotencyKey.objects.select_for_update().get(cashier=cashier, key=key)
        if record.operation != operation or record.request_hash != request_hash:
            raise DRFValidationError({
                'idempotency_key': _('Этот ключ уже использован для другого запроса')
            })
        return record, True
    except IdempotencyKey.DoesNotExist:
        try:
            # Savepoint keeps the surrounding financial transaction usable after a race.
            with transaction.atomic():
                record = IdempotencyKey.objects.create(
                    cashier=cashier,
                    key=key,
                    operation=operation,
                    request_hash=request_hash,
                )
            return record, False
        except IntegrityError:
            record = IdempotencyKey.objects.select_for_update().get(cashier=cashier, key=key)
            if record.operation != operation or record.request_hash != request_hash:
                raise DRFValidationError({
                    'idempotency_key': _('Этот ключ уже использован для другого запроса')
                })
            return record, True


def _increase_cashier_balance(cashier: User, amount: Decimal) -> None:
    if not amount:
        return
    balance = Balance.objects.select_for_update().get(user=cashier)
    balance.amount += amount
    balance.save(update_fields=['amount', 'updated_at'])


def register_student_payment(
    student_data: dict,
    group_id: str,
    amount: Decimal,
    cashier: User,
    booking_amount: Decimal = Decimal('0.00'),
    idempotency_key: str | None = None,
) -> tuple[Student, list[Transaction], bool]:
    """
    Регистрация нового ученика с первым платежом
    Атомарно создаёт Student, Transaction(booking/register) и увеличивает Balance кассира.
    
    Args:
        student_data: dict с полями {'full_name': str}
        group_id: UUID группы
        amount: сумма первого платежа
        cashier: пользователь-кассир
    
    Returns:
        tuple (Student, transactions, replayed)
    
    Raises:
        ValidationError: если данные некорректны
    """
    if amount < 0 or booking_amount < 0:
        raise DRFValidationError({
            'amount': _('Сумма не может быть отрицательной'),
            'code': 'invalid_amount'
        })

    try:
        with transaction.atomic():
            payload = {
                'student_data': student_data,
                'group_id': str(group_id),
                'amount': str(amount),
                'booking_amount': str(booking_amount),
            }
            idempotency_record, replayed = _reserve_idempotency_key(
                cashier, idempotency_key, 'registration', payload
            )
            if replayed:
                return idempotency_record.student, [], True

            # Получаем группу
            try:
                group = Group.objects.select_for_update().get(id=group_id)
            except Group.DoesNotExist:
                raise DRFValidationError({
                    'group': _('Группа не найдена'),
                    'code': 'group_not_found'
                })
            
            # Создаём ученика
            student = Student.objects.create(
                **student_data,
                group=group,
                registered_by=cashier
            )

            transactions = []
            if booking_amount:
                transactions.append(Transaction.objects.create(
                    student=student, cashier=cashier, amount=booking_amount, type='booking'
                ))
            if amount:
                transactions.append(Transaction.objects.create(
                    student=student, cashier=cashier, amount=amount, type='register'
                ))

            _increase_cashier_balance(cashier, booking_amount + amount)

            if idempotency_record:
                idempotency_record.student = student
                idempotency_record.transaction = transactions[-1] if transactions else None
                idempotency_record.save(update_fields=['student', 'transaction'])
            
            # Логируем действие
            log_action(
                user=cashier,
                action='student.register',
                object_type='Student',
                object_id=student.id,
                payload={
                    'student_name': student.full_name,
                    'group_id': str(group_id),
                    'booking_amount': str(booking_amount),
                    'first_payment_amount': str(amount),
                    'transaction_ids': [str(item.id) for item in transactions],
                }
            )
            for trans in transactions:
                log_action(
                    user=cashier,
                    action=f'transaction.{trans.type}',
                    object_type='Transaction',
                    object_id=trans.id,
                    payload={'student_id': str(student.id), 'amount': str(trans.amount)},
                )
            
            logger.info(
                f"Student registered: {student.full_name} by {cashier.full_name}, "
                f"booking: {booking_amount}, first payment: {amount}"
            )
            
            return student, transactions, False
            
    except Exception as e:
        logger.error(f"Failed to register student: {e}")
        log_action(
            user=cashier,
            action='student.register.failed',
            object_type='Student',
            object_id=None,
            payload={
                'error': str(e),
                'student_data': student_data,
                'amount': str(amount)
            }
        )
        raise


def record_student_payment(
    student_id: str,
    amount: Decimal,
    cashier: User,
    payment_type: str = 'topup',
    idempotency_key: str | None = None,
) -> tuple[Transaction, bool]:
    """
    Атомарно записывает финансовое поступление и увеличивает Balance кассира.
    
    Args:
        student_id: UUID ученика
        amount: сумма доплаты
        cashier: пользователь-кассир
    
    Returns:
        tuple (Transaction, replayed)
    
    Raises:
        ValidationError: если данные некорректны
    """
    if amount <= 0:
        raise DRFValidationError({
            'amount': _('Сумма должна быть больше нуля'),
            'code': 'invalid_amount'
        })
    if payment_type not in {'booking', 'topup'}:
        raise DRFValidationError({'type': _('Недопустимый тип платежа')})
    
    try:
        with transaction.atomic():
            payload = {
                'student_id': str(student_id),
                'amount': str(amount),
                'type': payment_type,
            }
            idempotency_record, replayed = _reserve_idempotency_key(
                cashier, idempotency_key, 'payment', payload
            )
            if replayed:
                return idempotency_record.transaction, True

            # Получаем ученика
            try:
                student = Student.objects.select_for_update().get(id=student_id)
            except Student.DoesNotExist:
                raise DRFValidationError({
                    'student': _('Ученик не найден'),
                    'code': 'student_not_found'
                })
            
            # Создаём транзакцию платежа
            trans = Transaction.objects.create(
                student=student,
                cashier=cashier,
                amount=amount,
                type=payment_type,
            )
            _increase_cashier_balance(cashier, amount)

            if idempotency_record:
                idempotency_record.student = student
                idempotency_record.transaction = trans
                idempotency_record.save(update_fields=['student', 'transaction'])
            
            # Логируем действие
            log_action(
                user=cashier,
                action=f'transaction.{payment_type}',
                object_type='Transaction',
                object_id=trans.id,
                payload={
                    'student_id': str(student_id),
                    'student_name': student.full_name,
                    'amount': str(amount)
                }
            )
            
            logger.info(
                f"Payment recorded: {student.full_name} paid {amount}, "
                f"cashier: {cashier.full_name}, transaction: {trans.id}"
            )
            
            return trans, False
            
    except Exception as e:
        logger.error(f"Failed to record topup: {e}")
        log_action(
            user=cashier,
            action=f'transaction.{payment_type}.failed',
            object_type='Transaction',
            object_id=None,
            payload={
                'error': str(e),
                'student_id': str(student_id),
                'amount': str(amount)
            }
        )
        raise


def record_topup_payment(
    student_id: str,
    amount: Decimal,
    cashier: User,
    idempotency_key: str | None = None,
) -> tuple[Transaction, bool]:
    """Backward-compatible wrapper for an ordinary top-up payment."""
    return record_student_payment(
        student_id=student_id,
        amount=amount,
        cashier=cashier,
        payment_type='topup',
        idempotency_key=idempotency_key,
    )


def collect_money(
    from_user_id: str,
    to_user: User,
    amount: Decimal
) -> Collection:
    """
    Сбор денег от одного сотрудника другому
    Атомарно списывает с from_user и зачисляет to_user
    
    Args:
        from_user_id: UUID пользователя, у которого собираем
        to_user: пользователь, которому зачисляем (обычно бухгалтер/директор)
        amount: сумма сбора
    
    Returns:
        Collection
    
    Raises:
        ValidationError: если недостаточно средств или данные некорректны
    """
    if amount <= 0:
        raise DRFValidationError({
            'amount': _('Сумма должна быть больше нуля'),
            'code': 'invalid_amount'
        })

    if from_user_id == str(to_user.id):
        raise DRFValidationError({
            'from_user': _('Нельзя собрать деньги у самого себя'),
            'code': 'same_user'
        })
    
    try:
        with transaction.atomic():
            # Получаем пользователя-источник
            try:
                from_user = User.objects.select_for_update().get(id=from_user_id)
            except User.DoesNotExist:
                raise DRFValidationError({
                    'from_user': _('Пользователь не найден'),
                    'code': 'user_not_found'
                })

            allowed_source_roles = {
                'accountant': {'cashier'},
                'director': {'cashier', 'accountant'},
            }
            permitted_roles = allowed_source_roles.get(to_user.role, set())
            if from_user.role not in permitted_roles:
                raise DRFValidationError({
                    'from_user': _('Этот сотрудник недоступен для сбора денег вашей ролью'),
                    'code': 'invalid_collection_source'
                })
            
            # Получаем балансы с блокировкой
            from_balance = Balance.objects.select_for_update().get(user=from_user)
            to_balance = Balance.objects.select_for_update().get(user=to_user)
            
            # Проверяем достаточность средств
            if amount > from_balance.amount:
                raise DRFValidationError({
                    'amount': _('Недостаточно средств. Доступно: %(available)s') % {
                        'available': from_balance.amount
                    },
                    'code': 'insufficient_funds'
                })
            
            # Списываем с источника
            from_balance.amount -= amount
            from_balance.save(update_fields=['amount', 'updated_at'])
            
            # Зачисляем получателю
            to_balance.amount += amount
            to_balance.save(update_fields=['amount', 'updated_at'])
            
            # Создаём запись о сборе
            collection = Collection.objects.create(
                from_user=from_user,
                to_user=to_user,
                amount=amount
            )
            
            # Логируем действие
            log_action(
                user=to_user,
                action='collection.create',
                object_type='Collection',
                object_id=collection.id,
                payload={
                    'from_user_id': str(from_user_id),
                    'from_user_name': from_user.full_name,
                    'to_user_name': to_user.full_name,
                    'amount': str(amount),
                    'from_balance_after': str(from_balance.amount),
                    'to_balance_after': str(to_balance.amount)
                }
            )
            
            logger.info(
                f"Money collected: {amount} from {from_user.full_name} "
                f"to {to_user.full_name}, collection: {collection.id}"
            )
            
            return collection
            
    except DRFValidationError:
        raise
    except Exception as e:
        logger.error(f"Failed to collect money: {e}")
        log_action(
            user=to_user,
            action='collection.create.failed',
            object_type='Collection',
            object_id=None,
            payload={
                'error': str(e),
                'from_user_id': str(from_user_id),
                'amount': str(amount)
            }
        )
        raise


def record_expense(
    amount: Decimal,
    comment: str,
    user: User
) -> Expense:
    """
    Фиксация расхода
    Атомарно списывает с баланса user и создаёт запись Expense
    
    Args:
        amount: сумма расхода
        comment: обязательный комментарий (на что потрачено)
        user: пользователь (бухгалтер/директор)
    
    Returns:
        Expense
    
    Raises:
        ValidationError: если недостаточно средств или комментарий пустой
    """
    if amount <= 0:
        raise DRFValidationError({
            'amount': _('Сумма должна быть больше нуля'),
            'code': 'invalid_amount'
        })
    
    if not comment or not comment.strip():
        raise DRFValidationError({
            'comment': _('Комментарий обязателен'),
            'code': 'comment_required'
        })
    
    try:
        with transaction.atomic():
            # Получаем баланс с блокировкой
            balance = Balance.objects.select_for_update().get(user=user)
            
            # Проверяем достаточность средств
            if amount > balance.amount:
                raise DRFValidationError({
                    'amount': _('Недостаточно средств. Доступно: %(available)s') % {
                        'available': balance.amount
                    },
                    'code': 'insufficient_funds'
                })
            
            # Списываем с баланса
            balance.amount -= amount
            balance.save(update_fields=['amount', 'updated_at'])
            
            # Создаём запись о расходе
            expense = Expense.objects.create(
                amount=amount,
                comment=comment.strip(),
                entered_by=user
            )
            
            # Логируем действие
            log_action(
                user=user,
                action='expense.create',
                object_type='Expense',
                object_id=expense.id,
                payload={
                    'amount': str(amount),
                    'comment': comment.strip()[:100],  # Ограничиваем для лога
                    'balance_after': str(balance.amount)
                }
            )
            
            logger.info(
                f"Expense recorded: {amount} by {user.full_name}, "
                f"expense: {expense.id}"
            )
            
            return expense
            
    except DRFValidationError:
        raise
    except Exception as e:
        logger.error(f"Failed to record expense: {e}")
        log_action(
            user=user,
            action='expense.create.failed',
            object_type='Expense',
            object_id=None,
            payload={
                'error': str(e),
                'amount': str(amount),
                'comment': comment[:100] if comment else None
            }
        )
        raise
