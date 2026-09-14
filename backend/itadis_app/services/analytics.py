"""
Сервисный слой для аналитики и отчётов
Согласно ТЗ п.6.7
"""
from decimal import Decimal
from datetime import datetime, date
from typing import Optional, List, Dict
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from ..models import Transaction, Expense, Collection, User


def get_summary_analytics(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None
) -> Dict:
    """
    Получить сводную аналитику за период
    
    Args:
        date_from: начало периода (опционально)
        date_to: конец периода (опционально)
    
    Returns:
        dict с ключами: total_income, total_expense, net_profit, total_students, active_groups
    """
    from ..models import Student, Group
    
    # Фильтры по датам
    filters_income = Q()
    filters_expense = Q()
    
    if date_from:
        filters_income &= Q(created_at__date__gte=date_from)
        filters_expense &= Q(created_at__date__gte=date_from)
    
    if date_to:
        filters_income &= Q(created_at__date__lte=date_to)
        filters_expense &= Q(created_at__date__lte=date_to)
    
    # Общий доход (все транзакции от учеников)
    total_income = Transaction.objects.filter(filters_income).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    # Общий расход
    total_expense = Expense.objects.filter(filters_expense).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    # Чистая прибыль
    net_profit = total_income - total_expense
    
    # Количество активных студентов (исключая frozen и expelled)
    total_students = Student.objects.filter(
        status__in=['active', 'debt']
    ).count()
    
    # Количество активных групп
    active_groups = Group.objects.filter(status='active').count()
    
    return {
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'total_students': total_students,
        'active_groups': active_groups,
        'period': {
            'from': date_from.isoformat() if date_from else None,
            'to': date_to.isoformat() if date_to else None
        }
    }


def get_monthly_analytics(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None
) -> List[Dict]:
    """
    Получить помесячную разбивку доходов/расходов
    
    Args:
        date_from: начало периода (опционально)
        date_to: конец периода (опционально)
    
    Returns:
        list of dict с ключами: month, income, expense, profit
    """
    # Фильтры по датам
    filters_income = Q()
    filters_expense = Q()
    
    if date_from:
        filters_income &= Q(created_at__date__gte=date_from)
        filters_expense &= Q(created_at__date__gte=date_from)
    
    if date_to:
        filters_income &= Q(created_at__date__lte=date_to)
        filters_expense &= Q(created_at__date__lte=date_to)
    
    # Доходы по месяцам
    income_by_month = Transaction.objects.filter(filters_income).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        total=Sum('amount')
    ).order_by('month')
    
    # Расходы по месяцам
    expense_by_month = Expense.objects.filter(filters_expense).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        total=Sum('amount')
    ).order_by('month')
    
    # Объединяем данные по месяцам
    monthly_data = {}
    
    for item in income_by_month:
        month_key = item['month'].strftime('%Y-%m')
        monthly_data[month_key] = {
            'month': month_key,
            'income': item['total'],
            'expense': Decimal('0.00'),
            'profit': item['total']
        }
    
    for item in expense_by_month:
        month_key = item['month'].strftime('%Y-%m')
        if month_key in monthly_data:
            monthly_data[month_key]['expense'] = item['total']
            monthly_data[month_key]['profit'] = (
                monthly_data[month_key]['income'] - item['total']
            )
        else:
            monthly_data[month_key] = {
                'month': month_key,
                'income': Decimal('0.00'),
                'expense': item['total'],
                'profit': -item['total']
            }
    
    # Сортируем по месяцам и возвращаем список
    result = sorted(monthly_data.values(), key=lambda x: x['month'])
    
    return result


def get_expenses_by_user(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    user_id: Optional[str] = None
) -> List[Dict]:
    """
    Получить детальный отчёт по расходам с группировкой по пользователям
    
    Args:
        date_from: начало периода (опционально)
        date_to: конец периода (опционально)
        user_id: фильтр по конкретному пользователю (опционально)
    
    Returns:
        list of dict с ключами: user_id, user_name, total_amount, expense_count
    """
    filters = Q()
    
    if date_from:
        filters &= Q(created_at__date__gte=date_from)
    
    if date_to:
        filters &= Q(created_at__date__lte=date_to)
    
    if user_id:
        filters &= Q(entered_by_id=user_id)
    
    # Группируем расходы по пользователям
    expenses_by_user = Expense.objects.filter(filters).values(
        'entered_by_id',
        'entered_by__full_name',
        'entered_by__role'
    ).annotate(
        total_amount=Sum('amount'),
        expense_count=Count('id')
    ).order_by('-total_amount')
    
    result = [
        {
            'user_id': str(item['entered_by_id']),
            'user_name': item['entered_by__full_name'],
            'user_role': item['entered_by__role'],
            'total_amount': item['total_amount'],
            'expense_count': item['expense_count']
        }
        for item in expenses_by_user
    ]
    
    return result


def get_cashier_statistics(
    cashier_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None
) -> List[Dict]:
    """
    Получить статистику по кассирам (сколько приняли денег)
    
    Args:
        cashier_id: фильтр по конкретному кассиру (опционально)
        date_from: начало периода (опционально)
        date_to: конец периода (опционально)
    
    Returns:
        list of dict с данными по каждому кассиру
    """
    filters = Q()
    
    if date_from:
        filters &= Q(created_at__date__gte=date_from)
    
    if date_to:
        filters &= Q(created_at__date__lte=date_to)
    
    if cashier_id:
        filters &= Q(cashier_id=cashier_id)
    
    # Группируем транзакции по кассирам
    stats_by_cashier = Transaction.objects.filter(filters).values(
        'cashier_id',
        'cashier__full_name'
    ).annotate(
        total_amount=Sum('amount'),
        transaction_count=Count('id'),
        register_count=Count('id', filter=Q(type='register')),
        topup_count=Count('id', filter=Q(type='topup'))
    ).order_by('-total_amount')
    
    result = [
        {
            'cashier_id': str(item['cashier_id']),
            'cashier_name': item['cashier__full_name'],
            'total_amount': item['total_amount'],
            'transaction_count': item['transaction_count'],
            'register_count': item['register_count'],
            'topup_count': item['topup_count']
        }
        for item in stats_by_cashier
    ]
    
    return result


def get_group_statistics() -> List[Dict]:
    """
    Получить статистику по активным группам (количество активных учеников, собранные суммы)
    
    Returns:
        list of dict с данными по каждой активной группе
    """
    from ..models import Group, Student
    from django.db.models import Prefetch
    
    # Только активные группы
    groups = Group.objects.filter(status='active').annotate(
        student_count=Count('students', filter=Q(students__status__in=['active', 'debt']))
    ).prefetch_related(
        Prefetch(
            'students',
            queryset=Student.objects.filter(status__in=['active', 'debt']).prefetch_related('transactions')
        )
    ).order_by('-created_at')
    
    result = []
    for group in groups:
        # Считаем общую сумму, собранную от активных учеников группы
        total_collected = Decimal('0.00')
        for student in group.students.all():
            total_collected += student.amount_paid_total
        
        result.append({
            'group_id': str(group.id),
            'group_name': group.name,
            'subject': group.subject,
            'student_count': group.student_count,
            'total_collected': total_collected,
            'progress': f"{group.current_lesson}/{group.total_lessons}",
            'progress_percent': round(
                (group.current_lesson / group.total_lessons * 100) 
                if group.total_lessons > 0 else 0, 
                2
            )
        })
    
    return result
