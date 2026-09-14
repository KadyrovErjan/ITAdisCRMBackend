"""
Views для транзакций
Согласно ТЗ п.6.3
"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema_view, extend_schema

from ..models import Transaction
from ..serializers import TransactionSerializer
from ..permissions import CanViewOwnTransactions
from ..filters import TransactionFilter


@extend_schema_view(
    list=extend_schema(
        tags=['transactions'], 
        description='История транзакций (кассир видит только свои, остальные - все)'
    ),
    retrieve=extend_schema(tags=['transactions'], description='Детали транзакции'),
)
class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для транзакций (только чтение, append-only)
    Кассир видит только свои, бухгалтер/директор/админ - все
    """
    queryset = Transaction.objects.all().select_related(
        'student', 'student__group', 'cashier'
    )
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated, CanViewOwnTransactions]
    filterset_class = TransactionFilter
    search_fields = ['student__full_name', 'cashier__full_name']
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Фильтрация по роли"""
        queryset = super().get_queryset()
        
        # Кассир видит только свои транзакции
        if self.request.user.role == 'cashier':
            queryset = queryset.filter(cashier=self.request.user)
        
        return queryset
