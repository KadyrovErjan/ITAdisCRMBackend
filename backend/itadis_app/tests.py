from decimal import Decimal
from datetime import date, timedelta

from django.db import IntegrityError
from django.db.models import Sum
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from .models import AuditLog, Balance, Group, IdempotencyKey, Student, Transaction, User, PaymentAllocation, PaymentNotification, PaymentSchedulePause
from .services.payment_plans import build_plan, financial_summary, generate_notifications, monthly_amounts, allocate_unallocated_transactions, freeze_student, resume_student


class CashierApiTests(APITestCase):
    def setUp(self):
        self.cashier = User.objects.create_user(
            login='cashier', password='safe-password-123', full_name='Cashier One', role='cashier'
        )
        self.other_cashier = User.objects.create_user(
            login='cashier-two', password='safe-password-123', full_name='Cashier Two', role='cashier'
        )
        self.accountant = User.objects.create_user(
            login='accountant', password='safe-password-123', full_name='Accountant', role='accountant'
        )
        self.group = Group.objects.create(
            name='Python 1', subject='Python', schedule='Mon 18:00', total_lessons=12, created_by=self.cashier
        )
        self.other_group = Group.objects.create(
            name='Python 2', subject='Python', schedule='Wed 18:00', total_lessons=12, created_by=self.other_cashier
        )

    def register_student(self, key='register-key', **overrides):
        payload = {
            'full_name': 'Aida Student',
            'phone': '+996700123456',
            'group': str(self.group.id),
            'course_price': '45000.00',
            'booking_amount': '1000.00',
            'amount': '14000.00',
        }
        payload.update(overrides)
        self.client.force_authenticate(self.cashier)
        return self.client.post(
            reverse('student-register'), payload, format='json', HTTP_IDEMPOTENCY_KEY=key
        )

    def test_registration_creates_booking_and_first_payment_atomically(self):
        response = self.register_student()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        student = Student.objects.get(full_name='Aida Student')
        self.assertEqual(student.course_price, Decimal('45000.00'))
        self.assertEqual(student.transactions.count(), 2)
        self.assertEqual(student.amount_paid_total, Decimal('15000.00'))
        self.assertEqual(student.remaining_balance, Decimal('30000.00'))
        self.assertEqual(Balance.objects.get(user=self.cashier).amount, Decimal('15000.00'))

    def test_registration_replay_does_not_duplicate_financial_records(self):
        first = self.register_student()
        second = self.register_student()
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertTrue(second.data['replayed'])
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(Balance.objects.get(user=self.cashier).amount, Decimal('15000.00'))
        self.assertEqual(IdempotencyKey.objects.count(), 1)

    def test_same_idempotency_key_with_different_payload_is_rejected(self):
        self.register_student(key='reused-key')
        response = self.register_student(key='reused-key', amount='15000.00')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Transaction.objects.count(), 2)

    def test_payment_replay_does_not_duplicate_balance(self):
        student_id = self.register_student().data['student']['id']
        url = reverse('student-payments', args=[student_id])
        first = self.client.post(url, {'amount': '5000.00'}, format='json', HTTP_IDEMPOTENCY_KEY='payment-key')
        second = self.client.post(url, {'amount': '5000.00'}, format='json', HTTP_IDEMPOTENCY_KEY='payment-key')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(Transaction.objects.filter(student_id=student_id).count(), 3)
        self.assertEqual(Balance.objects.get(user=self.cashier).amount, Decimal('20000.00'))

    def test_failed_registration_rolls_back_everything(self):
        response = self.register_student(group='00000000-0000-0000-0000-000000000000')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Student.objects.exists())
        self.assertFalse(Transaction.objects.exists())
        self.assertEqual(Balance.objects.get(user=self.cashier).amount, Decimal('0.00'))

    def test_cashier_cannot_register_as_accountant(self):
        self.client.force_authenticate(self.accountant)
        response = self.client.post(reverse('student-register'), {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cashier_cannot_pay_or_edit_another_cashiers_student(self):
        self.client.force_authenticate(self.other_cashier)
        student = Student.objects.create(full_name='Owned Student', group=self.other_group, registered_by=self.other_cashier)
        self.client.force_authenticate(self.cashier)
        response = self.client.post(reverse('student-payments', args=[student.id]), {'amount': '100'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_debt_filter_and_phone_search_are_server_side(self):
        self.register_student()
        Student.objects.create(
            full_name='Paid Student', phone='+996555000000', group=self.group,
            registered_by=self.cashier, course_price=Decimal('1000.00')
        )
        paid = Student.objects.get(full_name='Paid Student')
        Transaction.objects.create(student=paid, cashier=self.cashier, amount=Decimal('1000.00'), type='register')
        self.client.force_authenticate(self.cashier)
        debt = self.client.get(reverse('student-list'), {'payment_status': 'debt'})
        search = self.client.get(reverse('student-list'), {'search': '700123'})
        self.assertEqual(debt.status_code, status.HTTP_200_OK)
        self.assertEqual(debt.data['count'], 1)
        self.assertEqual(search.data['count'], 1)

    def test_transactions_are_append_only(self):
        self.client.force_authenticate(self.cashier)
        response = self.client.post(reverse('transaction-list'), {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_booking_and_student_status_are_audited(self):
        student_id = self.register_student().data['student']['id']
        booking = self.client.post(
            reverse('student-booking', args=[student_id]), {'amount': '500.00'}, format='json',
            HTTP_IDEMPOTENCY_KEY='separate-booking-key'
        )
        status_change = self.client.patch(
            reverse('student-change-status', args=[student_id]), {'status': 'frozen'}, format='json'
        )
        self.assertEqual(booking.status_code, status.HTTP_201_CREATED)
        self.assertEqual(status_change.status_code, status.HTTP_200_OK)
        actions = set(AuditLog.objects.values_list('action', flat=True))
        self.assertTrue({'student.register', 'transaction.booking', 'student.status.change'}.issubset(actions))

    def test_course_finance_scenario_reaches_paid_without_double_booking(self):
        student_id = self.register_student().data['student']['id']
        url = reverse('student-payments', args=[student_id])
        self.client.post(url, {'amount': '15000.00'}, format='json', HTTP_IDEMPOTENCY_KEY='second-payment')
        self.client.post(url, {'amount': '15000.00'}, format='json', HTTP_IDEMPOTENCY_KEY='third-payment')
        student = Student.objects.get(id=student_id)
        detail = self.client.get(reverse('student-detail', args=[student_id]))
        self.assertEqual(student.amount_paid_total, Decimal('45000.00'))
        self.assertEqual(student.remaining_balance, Decimal('0.00'))
        # Existing registrations without an explicitly confirmed schedule do
        # not infer a contractual debt/payment state.
        self.assertEqual(detail.data['payment_status'], 'unknown')
        self.assertEqual(Balance.objects.get(user=self.cashier).amount, Decimal('45000.00'))

    def test_overpayment_and_legacy_student_without_course_price(self):
        student_id = self.register_student(course_price='45000.00').data['student']['id']
        self.client.post(
            reverse('student-payments', args=[student_id]), {'amount': '35000.00'}, format='json',
            HTTP_IDEMPOTENCY_KEY='overpayment-key'
        )
        overpaid = self.client.get(reverse('student-detail', args=[student_id]))
        legacy = Student.objects.create(
            full_name='Legacy Student', group=self.group, registered_by=self.cashier, course_price=None
        )
        legacy_response = self.client.get(reverse('student-detail', args=[legacy.id]))
        self.assertEqual(Decimal(overpaid.data['remaining_balance']), Decimal('-5000.00'))
        self.assertEqual(overpaid.data['payment_status'], 'unknown')
        self.assertIsNone(legacy_response.data['remaining_balance'])
        self.assertEqual(legacy_response.data['payment_status'], 'unknown')

    def test_different_idempotency_keys_create_distinct_operations_and_are_scoped_to_cashier(self):
        student_id = self.register_student().data['student']['id']
        url = reverse('student-payments', args=[student_id])
        self.client.post(url, {'amount': '500.00'}, format='json', HTTP_IDEMPOTENCY_KEY='unique-a')
        self.client.post(url, {'amount': '500.00'}, format='json', HTTP_IDEMPOTENCY_KEY='unique-b')
        self.assertEqual(Transaction.objects.filter(student_id=student_id).count(), 4)
        self.client.force_authenticate(self.other_cashier)
        other = Student.objects.create(full_name='Other', group=self.other_group, registered_by=self.other_cashier)
        response = self.client.post(
            reverse('student-payments', args=[other.id]), {'amount': '100.00'}, format='json',
            HTTP_IDEMPOTENCY_KEY='unique-a'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(IdempotencyKey.objects.filter(key='unique-a').count(), 2)
        with self.assertRaises(IntegrityError):
            IdempotencyKey.objects.create(cashier=self.other_cashier, key='unique-a', operation='payment', request_hash='x' * 64)

    def test_history_transfer_and_permission_boundaries(self):
        student_id = self.register_student().data['student']['id']
        history = self.client.get(reverse('student-history', args=[student_id]))
        self.assertEqual(history.status_code, status.HTTP_200_OK)
        self.assertEqual(history.data['count'], 2)
        transfer = self.client.post(
            reverse('student-transfer-group', args=[student_id]), {'group_id': str(self.other_group.id)}, format='json'
        )
        self.assertEqual(transfer.status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.accountant)
        financial = self.client.post(
            reverse('student-booking', args=[student_id]), {'amount': '100.00'}, format='json', HTTP_IDEMPOTENCY_KEY='accountant-key'
        )
        edit = self.client.patch(reverse('student-update-details', args=[student_id]), {'comment': 'No access'}, format='json')
        balance = self.client.patch(reverse('balance-detail', args=[self.cashier.id]), {'amount': '1'}, format='json')
        self.assertEqual(financial.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(edit.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(balance.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cashier_dashboard_returns_aggregated_data(self):
        self.register_student()
        response = self.client.get(reverse('cashier-dashboard'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data['balance']), Decimal('15000.00'))
        self.assertEqual(Decimal(response.data['today_received']), Decimal('15000.00'))
        self.assertEqual(response.data['debt_students_count'], 0)


class PaymentPlanServiceTests(APITestCase):
    def setUp(self):
        self.director = User.objects.create_user(login='director-plan', password='safe-password-123', full_name='Director', role='director')
        self.cashier = User.objects.create_user(login='cashier-plan', password='safe-password-123', full_name='Cashier', role='cashier')
        self.group = Group.objects.create(name='Python49', subject='Python', schedule='Mon', total_lessons=12, created_by=self.cashier)
        self.student = Student.objects.create(full_name='Asan', group=self.group, registered_by=self.cashier, course_price=Decimal('60000.00'))

    def test_monthly_rounding_and_legacy_receipt_allocation(self):
        self.assertEqual(monthly_amounts(Decimal('100.00'), 3), [Decimal('33.33'), Decimal('33.33'), Decimal('33.34')])
        booking = Transaction.objects.create(student=self.student, cashier=self.cashier, type='booking', amount=Decimal('5000.00'))
        plan = build_plan(self.student, method='monthly', period_count=6, start_date=date.today(), items=None, actor=self.director)
        self.assertEqual(plan.items.count(), 6)
        self.assertEqual(PaymentAllocation.objects.filter(transaction=booking).aggregate(total=Sum('amount'))['total'], Decimal('5000.00'))
        allocate_unallocated_transactions(self.student)
        self.assertEqual(PaymentAllocation.objects.filter(transaction=booking).count(), 1)

    def test_group_student_search_matches_phone_as_well_as_name(self):
        self.student.phone = '+996700000099'
        self.student.save(update_fields=['phone'])
        self.client.force_authenticate(self.cashier)
        response = self.client.get(reverse('group-list'), {'student_name': '700000099'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(str(response.data['results'][0]['id']), str(self.group.id))
        group_students = self.client.get(
            reverse('group-students', args=[self.group.id]), {'search': '700000099'}
        )
        self.assertEqual(group_students.status_code, status.HTTP_200_OK)
        self.assertEqual(group_students.data['count'], 1)

    def test_due_overdue_ahead_and_notifications_are_idempotent(self):
        start = date.today() - timedelta(days=1)
        build_plan(self.student, method='custom', period_count=2, start_date=start, items=[
            {'due_date': start, 'amount_due': Decimal('10000.00')},
            {'due_date': start + timedelta(days=30), 'amount_due': Decimal('50000.00')},
        ], actor=self.director)
        Transaction.objects.create(student=self.student, cashier=self.cashier, type='topup', amount=Decimal('4000.00'))
        allocate_unallocated_transactions(self.student)
        summary = financial_summary(self.student, today=date.today())
        self.assertEqual(summary['overdue_amount'], '6000.00')
        self.assertEqual(summary['contract_remaining'], '56000.00')
        self.assertEqual(generate_notifications(today=date.today()), 1)
        self.assertEqual(generate_notifications(today=date.today()), 0)
        self.assertEqual(PaymentNotification.objects.count(), 1)

    def test_fixed_date_statuses_credit_and_allocation_invariant(self):
        fixed = date(2026, 11, 5)
        build_plan(self.student, method='custom', period_count=3, start_date=fixed, items=[
            {'due_date': fixed - timedelta(days=1), 'amount_due': Decimal('10000.00')},
            {'due_date': fixed, 'amount_due': Decimal('10000.00')},
            {'due_date': fixed + timedelta(days=1), 'amount_due': Decimal('40000.00')},
        ], actor=self.director)
        self.assertEqual(financial_summary(self.student, today=fixed - timedelta(days=2))['payment_status'], 'upcoming')
        self.assertEqual(financial_summary(self.student, today=fixed - timedelta(days=1))['payment_status'], 'due')
        self.assertEqual(financial_summary(self.student, today=fixed)['payment_status'], 'overdue')
        receipt = Transaction.objects.create(student=self.student, cashier=self.cashier, type='topup', amount=Decimal('25000.00'))
        allocate_unallocated_transactions(self.student)
        allocated = PaymentAllocation.objects.filter(transaction=receipt).aggregate(total=Sum('amount'))['total']
        self.assertLessEqual(allocated, receipt.amount)
        self.assertEqual(allocated, Decimal('25000.00'))
        extra = Transaction.objects.create(student=self.student, cashier=self.cashier, type='topup', amount=Decimal('40000.00'))
        allocate_unallocated_transactions(self.student)
        self.assertEqual(financial_summary(self.student, today=fixed)['credit_amount'], '5000.00')
        self.assertLessEqual(PaymentAllocation.objects.filter(transaction=extra).aggregate(total=Sum('amount'))['total'], extra.amount)

    def test_learning_status_and_freeze_preserve_existing_overdue(self):
        fixed = date(2026, 11, 5)
        build_plan(self.student, method='full', period_count=1, start_date=fixed - timedelta(days=1), items=None, actor=self.director)
        self.client.force_authenticate(self.cashier)
        response = self.client.patch(reverse('student-change-status', args=[self.student.id]), {'status': 'frozen'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.student.refresh_from_db()
        self.assertEqual(self.student.learning_status, 'frozen')
        self.assertEqual(self.student.effective_learning_status, 'frozen')
        self.assertEqual(financial_summary(self.student, today=fixed)['overdue_amount'], '60000.00')

    def test_freeze_and_resume_return_student_not_pause_identifier(self):
        build_plan(self.student, method='full', period_count=1, start_date=date(2026, 11, 5), items=None, actor=self.director)
        self.client.force_authenticate(self.cashier)

        frozen = self.client.post(reverse('student-freeze', args=[self.student.id]), {}, format='json')
        self.assertEqual(frozen.status_code, status.HTTP_200_OK)
        self.assertEqual(str(frozen.data['id']), str(self.student.id))
        self.assertEqual(frozen.data['learning_status'], 'frozen')
        self.assertEqual(PaymentSchedulePause.objects.filter(student=self.student, ended_on__isnull=True).count(), 1)

        resumed = self.client.post(reverse('student-resume', args=[self.student.id]), {}, format='json')
        self.assertEqual(resumed.status_code, status.HTTP_200_OK)
        self.assertEqual(str(resumed.data['id']), str(self.student.id))
        self.assertEqual(resumed.data['learning_status'], 'active')

    def test_custom_plan_bad_sum_is_rejected_and_legacy_student_is_unknown(self):
        self.assertEqual(financial_summary(self.student)['payment_status'], 'unknown')
        self.client.force_authenticate(self.cashier)
        response = self.client.post(reverse('student-payment-plan', args=[self.student.id]), {
            'payment_method': 'custom', 'start_date': '2026-11-05', 'items': [
                {'due_date': '2026-11-05', 'amount_due': '59000.00'},
            ],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cashier_cannot_adjust_allocated_plan_director_can_audit_future_row(self):
        plan = build_plan(self.student, method='monthly', period_count=6, start_date=date(2026, 11, 5), items=None, actor=self.director)
        receipt = Transaction.objects.create(student=self.student, cashier=self.cashier, type='topup', amount=Decimal('10000.00'))
        allocate_unallocated_transactions(self.student)
        items = list(plan.items.order_by('due_date'))
        payload = {'items': [{'id': str(row.id), 'due_date': row.due_date.isoformat(), 'amount_due': str(row.amount_due)} for row in items]}
        self.client.force_authenticate(self.cashier)
        self.assertEqual(self.client.patch(reverse('student-payment-plan', args=[self.student.id]), payload, format='json').status_code, status.HTTP_400_BAD_REQUEST)
        payload['items'][1]['amount_due'] = '11000.00'
        payload['items'][5]['amount_due'] = '9000.00'
        self.client.force_authenticate(self.director)
        response = self.client.patch(reverse('student-payment-plan', args=[self.student.id]), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(AuditLog.objects.filter(action='payment_plan.adjust').exists())
        self.assertLessEqual(PaymentAllocation.objects.filter(transaction=receipt).aggregate(total=Sum('amount'))['total'], receipt.amount)

    def test_resume_shifts_only_items_not_due_before_pause_and_repeated_freeze_is_safe(self):
        fixed = date(2026, 11, 5)
        plan = build_plan(self.student, method='custom', period_count=2, start_date=fixed, items=[
            {'due_date': fixed - timedelta(days=1), 'amount_due': Decimal('10000.00')},
            {'due_date': fixed + timedelta(days=2), 'amount_due': Decimal('50000.00')},
        ], actor=self.director)
        freeze_student(self.student, self.cashier, started_on=fixed)
        with self.assertRaises(ValidationError):
            freeze_student(self.student, self.cashier, started_on=fixed)
        resume_student(self.student, self.cashier, ended_on=fixed + timedelta(days=5))
        items = list(plan.items.order_by('due_date'))
        self.assertEqual(items[0].due_date, fixed - timedelta(days=1))
        self.assertEqual(items[1].due_date, fixed + timedelta(days=7))
        self.assertEqual(PaymentSchedulePause.objects.filter(student=self.student, ended_on__isnull=True).count(), 0)

    def test_resume_does_not_shift_a_fully_paid_future_period(self):
        fixed = date(2026, 11, 5)
        plan = build_plan(self.student, method='custom', period_count=2, start_date=fixed, items=[
            {'due_date': fixed + timedelta(days=2), 'amount_due': Decimal('10000.00')},
            {'due_date': fixed + timedelta(days=32), 'amount_due': Decimal('50000.00')},
        ], actor=self.director)
        paid_period, unpaid_period = plan.items.order_by('due_date')
        receipt = Transaction.objects.create(
            student=self.student, cashier=self.cashier, type='topup', amount=Decimal('10000.00')
        )
        allocate_unallocated_transactions(self.student)
        self.assertEqual(
            PaymentAllocation.objects.filter(transaction=receipt).aggregate(total=Sum('amount'))['total'],
            Decimal('10000.00'),
        )

        freeze_student(self.student, self.cashier, started_on=fixed)
        resume_student(self.student, self.cashier, ended_on=fixed + timedelta(days=5))
        paid_period.refresh_from_db()
        unpaid_period.refresh_from_db()

        self.assertEqual(paid_period.due_date, fixed + timedelta(days=2))
        self.assertEqual(unpaid_period.due_date, fixed + timedelta(days=37))

    def test_partial_notification_resolves_after_payment(self):
        fixed = date(2026, 11, 5)
        build_plan(self.student, method='full', period_count=1, start_date=fixed - timedelta(days=1), items=None, actor=self.director)
        Transaction.objects.create(student=self.student, cashier=self.cashier, type='topup', amount=Decimal('1000.00'))
        allocate_unallocated_transactions(self.student)
        self.assertEqual(generate_notifications(today=fixed), 1)
        notification = PaymentNotification.objects.get()
        self.assertIn('Осталась задолженность', notification.message)
        Transaction.objects.create(student=self.student, cashier=self.cashier, type='topup', amount=Decimal('59000.00'))
        allocate_unallocated_transactions(self.student)
        generate_notifications(today=fixed)
        notification.refresh_from_db()
        self.assertIsNotNone(notification.resolved_at)
