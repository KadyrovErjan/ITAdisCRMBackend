"""
Кастомные фильтры для django-filter
Согласно ТЗ раздел 9 - фильтрация и пагинация
"""
from django_filters import rest_framework as filters
from django.db.models import Q
from .models import Transaction, Collection, Expense, AuditLog, Student, Group


class TransactionFilter(filters.FilterSet):
    """Фильтр для транзакций"""
    date_from = filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to = filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
    amount_min = filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_max = filters.NumberFilter(field_name='amount', lookup_expr='lte')
    
    class Meta:
        model = Transaction
        fields = {
            'cashier': ['exact'],
            'student': ['exact'],
            'student__group': ['exact'],
            'type': ['exact'],
        }


class CollectionFilter(filters.FilterSet):
    """Фильтр для сборов"""
    date_from = filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to = filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
    amount_min = filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_max = filters.NumberFilter(field_name='amount', lookup_expr='lte')
    
    class Meta:
        model = Collection
        fields = {
            'from_user': ['exact'],
            'to_user': ['exact'],
        }


class ExpenseFilter(filters.FilterSet):
    """Фильтр для расходов"""
    date_from = filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to = filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
    amount_min = filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_max = filters.NumberFilter(field_name='amount', lookup_expr='lte')
    comment_contains = filters.CharFilter(field_name='comment', lookup_expr='icontains')
    
    class Meta:
        model = Expense
        fields = {
            'entered_by': ['exact'],
        }


class AuditLogFilter(filters.FilterSet):
    """Фильтр для журнала аудита"""
    date_from = filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to = filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
    action_contains = filters.CharFilter(field_name='action', lookup_expr='icontains')
    
    class Meta:
        model = AuditLog
        fields = {
            'user': ['exact'],
            'action': ['exact'],
            'object_type': ['exact'],
        }


class StudentFilter(filters.FilterSet):
    """Фильтр для учеников"""
    search = filters.CharFilter(method='filter_search')
    assistant = filters.CharFilter(field_name='assistant_name', lookup_expr='icontains')
    contract_status = filters.CharFilter(field_name='contract_status')
    payment_status = filters.CharFilter(method='filter_payment_status')
    has_debt = filters.BooleanFilter(method='filter_has_debt')
    
    def filter_search(self, queryset, name, value):
        """Поиск по имени ученика"""
        return queryset.filter(Q(full_name__icontains=value) | Q(phone__icontains=value))

    def filter_payment_status(self, queryset, name, value):
        filters_by_status = {
            'debt': Q(course_price__isnull=False, remaining_balance_annotated__gt=0),
            'paid': Q(course_price__isnull=False, remaining_balance_annotated=0),
            'overpaid': Q(course_price__isnull=False, remaining_balance_annotated__lt=0),
            'unknown': Q(course_price__isnull=True),
        }
        condition = filters_by_status.get(value)
        return queryset.filter(condition) if condition is not None else queryset

    def filter_has_debt(self, queryset, name, value):
        if value is None:
            return queryset
        condition = Q(course_price__isnull=False, remaining_balance_annotated__gt=0)
        return queryset.filter(condition) if value else queryset.exclude(condition)
    
    class Meta:
        model = Student
        fields = {
            'group': ['exact'],
            'registered_by': ['exact'],
            'status': ['exact'],
        }


class GroupFilter(filters.FilterSet):
    """Фильтр для групп"""
    search = filters.CharFilter(method='filter_search')
    student_name = filters.CharFilter(method='filter_student_name')
    
    def filter_search(self, queryset, name, value):
        """Поиск по названию группы или предмету"""
        return queryset.filter(
            Q(name__icontains=value) | Q(subject__icontains=value)
        )

    def filter_student_name(self, queryset, name, value):
        """Возвращает группы, в которых имя или телефон ученика совпадают с поиском."""
        return queryset.filter(
            Q(students__full_name__icontains=value) | Q(students__phone__icontains=value)
        ).distinct()
    
    class Meta:
        model = Group
        fields = {
            'subject': ['exact'],
            'created_by': ['exact'],
            'status': ['exact'],
        }
