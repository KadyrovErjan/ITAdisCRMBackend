"""
Сервисный слой для финансовых операций
Согласно ТЗ раздел 7 - все операции атомарные с блокировками
"""
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError as DRFValidationError
import logging

from ..models import User, Student, Group, Transaction, Balance, Collection, Expense
from .audit import log_action

logger = logging.getLogger(__name__)


def register_student_payment(
    student_data: dict,
    group_id: str,
    amount: Decimal,
    cashier: User
) -> tuple[Student, Transaction]:
    """
    Регистрация нового ученика с первым платежом
    Атомарно создаёт Student, Transaction(register) и увеличивает Balance кассира
    
    Args:
        student_data: dict с полями {'full_name': str}
        group_id: UUID группы
        amount: сумма первого платежа
        cashier: пользователь-кассир
    
    Returns:
        tuple (Student, Transaction)
    
    Raises:
        ValidationError: если данные некорректны
    """
    if amount <= 0:
        raise DRFValidationError({
            'amount': _('Сумма должна быть больше нуля'),
            'code': 'invalid_amount'
        })

    try:
        with transaction.atomic():
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
                full_name=student_data['full_name'],
                group=group,
                registered_by=cashier
            )
            
            # Создаём транзакцию регистрации
            trans = Transaction.objects.create(
                student=student,
                cashier=cashier,
                amount=amount,
                type='register'
            )
            
            # Увеличиваем баланс кассира
            balance = Balance.objects.select_for_update().get(user=cashier)
            balance.amount += amount
            balance.save(update_fields=['amount', 'updated_at'])
            
            # Логируем действие
            log_action(
                user=cashier,
                action='student.register',
                object_type='Student',
                object_id=student.id,
                payload={
                    'student_name': student.full_name,
                    'group_id': str(group_id),
                    'amount': str(amount),
                    'transaction_id': str(trans.id)
                }
            )
            
            logger.info(
                f"Student registered: {student.full_name} by {cashier.full_name}, "
                f"amount: {amount}, transaction: {trans.id}"
            )
            
            return student, trans
            
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


def record_topup_payment(
    student_id: str,
    amount: Decimal,
    cashier: User
) -> Transaction:
    """
    Запись доплаты от ученика
    Атомарно создаёт Transaction(topup) и увеличивает Balance кассира
    
    Args:
        student_id: UUID ученика
        amount: сумма доплаты
        cashier: пользователь-кассир
    
    Returns:
        Transaction
    
    Raises:
        ValidationError: если данные некорректны
    """
    if amount <= 0:
        raise DRFValidationError({
            'amount': _('Сумма должна быть больше нуля'),
            'code': 'invalid_amount'
        })
    
    try:
        with transaction.atomic():
            # Получаем ученика
            try:
                student = Student.objects.select_for_update().get(id=student_id)
            except Student.DoesNotExist:
                raise DRFValidationError({
                    'student': _('Ученик не найден'),
                    'code': 'student_not_found'
                })
            
            # Создаём транзакцию доплаты
            trans = Transaction.objects.create(
                student=student,
                cashier=cashier,
                amount=amount,
                type='topup'
            )
            
            # Увеличиваем баланс кассира
            balance = Balance.objects.select_for_update().get(user=cashier)
            balance.amount += amount
            balance.save(update_fields=['amount', 'updated_at'])
            
            # Логируем действие
            log_action(
                user=cashier,
                action='transaction.topup',
                object_type='Transaction',
                object_id=trans.id,
                payload={
                    'student_id': str(student_id),
                    'student_name': student.full_name,
                    'amount': str(amount)
                }
            )
            
            logger.info(
                f"Topup recorded: {student.full_name} paid {amount}, "
                f"cashier: {cashier.full_name}, transaction: {trans.id}"
            )
            
            return trans
            
    except Exception as e:
        logger.error(f"Failed to record topup: {e}")
        log_action(
            user=cashier,
            action='transaction.topup.failed',
            object_type='Transaction',
            object_id=None,
            payload={
                'error': str(e),
                'student_id': str(student_id),
                'amount': str(amount)
            }
        )
        raise


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
