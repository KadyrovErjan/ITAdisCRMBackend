from decimal import Decimal

from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import AuditLog, Balance, Group, IdempotencyKey, Student, Transaction, User


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
        self.assertEqual(detail.data['payment_status'], 'paid')
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
        self.assertEqual(overpaid.data['payment_status'], 'overpaid')
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
        self.assertEqual(response.data['debt_students_count'], 1)
