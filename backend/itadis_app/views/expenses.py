"""
Views для расходов
Согласно ТЗ п.6.6
"""
from rest_framework import viewsets, status, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema_view, extend_schema

from ..models import Expense
from ..serializers import ExpenseSerializer, ExpenseCreateSerializer
from ..permissions import CanCreateExpense
from ..services.finance import record_expense


from ..filters import ExpenseFilter


@extend_schema_view(
    list=extend_schema(
        tags=['expenses'], 
        description='Таблица расходов (бухгалтер видит свои, директор/админ - все)'
    ),
    retrieve=extend_schema(tags=['expenses'], description='Детали расхода'),
    create=extend_schema(
        tags=['expenses'], 
        description='Фиксация расхода (только бухгалтер/директор)',
        request=ExpenseCreateSerializer
    ),
)
class ExpenseViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    ViewSet для расходов (только создание и чтение, append-only)
    Бухгалтер/директор может создавать расходы со своего баланса
    """
    queryset = Expense.objects.all().select_related('entered_by')
    permission_classes = [IsAuthenticated]
    filterset_class = ExpenseFilter
    search_fields = ['comment']
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ExpenseCreateSerializer
        return ExpenseSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), CanCreateExpense()]
        return super().get_permissions()
    
    def get_queryset(self):
        """Фильтрация по роли"""
        queryset = super().get_queryset()
        
        # Бухгалтер видит только свои расходы
        if self.request.user.role == 'accountant':
            queryset = queryset.filter(entered_by=self.request.user)
        
        # Директор и админ видят все
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """
        POST /api/v1/expenses/
        Фиксация расхода: { amount, comment }
        comment обязателен
        """
        serializer = ExpenseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            expense = record_expense(
                amount=serializer.validated_data['amount'],
                comment=serializer.validated_data['comment'],
                user=request.user
            )
            
            return Response(
                ExpenseSerializer(expense).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {'detail': str(e), 'code': 'expense_failed'},
                status=status.HTTP_400_BAD_REQUEST
            )
