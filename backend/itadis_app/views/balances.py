"""
Views для балансов
Согласно ТЗ п.6.4
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema_view, extend_schema

from ..models import Balance
from ..serializers import BalanceSerializer
from ..permissions import CanViewOwnBalance, IsAccountantOrDirectorOrAdmin


@extend_schema_view(
    list=extend_schema(
        tags=['balances'], 
        description='Балансы всех сотрудников (только для бухгалтер/директор/админ)'
    ),
    retrieve=extend_schema(tags=['balances'], description='Баланс сотрудника'),
)
class BalanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для балансов (только чтение)
    """
    queryset = Balance.objects.all().select_related('user')
    serializer_class = BalanceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        """Разные права для разных действий"""
        if self.action == 'me':
            return [IsAuthenticated()]
        elif self.action in ['list', 'retrieve']:
            return [IsAuthenticated(), IsAccountantOrDirectorOrAdmin()]
        return super().get_permissions()
    
    def get_queryset(self):
        """Фильтрация по роли (исключаем директоров)"""
        queryset = super().get_queryset()
        
        # Исключаем балансы директоров, так как у них нет баланса
        queryset = queryset.exclude(user__role='director')
        
        # Кассир видит только свой баланс (но через action 'me')
        if self.request.user.role == 'cashier':
            queryset = queryset.filter(user=self.request.user)
        
        return queryset
    
    @extend_schema(
        tags=['balances'],
        description='Получить свой баланс',
        responses={200: BalanceSerializer}
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """
        GET /api/v1/balances/me/
        Баланс текущего пользователя (только для кассиров и бухгалтеров)
        """
        # Директор не имеет баланса
        if request.user.role == 'director':
            return Response({
                'user': str(request.user.id),
                'user_name': request.user.full_name,
                'user_role': request.user.role,
                'amount': None,
                'updated_at': None
            })
        
        try:
            balance = Balance.objects.select_related('user').get(user=request.user)
            serializer = BalanceSerializer(balance)
            return Response(serializer.data)
        except Balance.DoesNotExist:
            # Создаем баланс, если его нет (только для кассиров и бухгалтеров)
            from decimal import Decimal
            balance = Balance.objects.create(user=request.user, amount=Decimal('0.00'))
            serializer = BalanceSerializer(balance)
            return Response(serializer.data)
