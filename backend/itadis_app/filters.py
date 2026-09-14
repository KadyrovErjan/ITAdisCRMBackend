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
    
    def filter_search(self, queryset, name, value):
        """Поиск по имени ученика"""
        return queryset.filter(
            Q(full_name__icontains=value)
        )
    
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
    
    def filter_search(self, queryset, name, value):
        """Поиск по названию группы или предмету"""
        return queryset.filter(
            Q(name__icontains=value) | Q(subject__icontains=value)
        )
    
    class Meta:
        model = Group
        fields = {
            'subject': ['exact'],
            'created_by': ['exact'],
            'status': ['exact'],
        }
