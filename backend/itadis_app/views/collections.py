"""
Views для сборов (collections)
Согласно ТЗ п.6.5
"""
from rest_framework import viewsets, status, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema_view, extend_schema

from ..models import Collection
from ..serializers import CollectionSerializer, CollectionCreateSerializer
from ..permissions import CanCreateCollection
from ..services.finance import collect_money
from ..filters import CollectionFilter


@extend_schema_view(
    list=extend_schema(
        tags=['collections'], 
        description='История сборов (бухгалтер видит свои получения, директор/админ - все)'
    ),
    retrieve=extend_schema(tags=['collections'], description='Детали сбора'),
    create=extend_schema(
        tags=['collections'], 
        description='Сбор денег (только бухгалтер/директор)',
        request=CollectionCreateSerializer
    ),
)
class CollectionViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    ViewSet для сборов (только создание и чтение, append-only)
    Бухгалтер/директор может собирать деньги
    """
    queryset = Collection.objects.all().select_related('from_user', 'to_user')
    permission_classes = [IsAuthenticated]
    filterset_class = CollectionFilter
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CollectionCreateSerializer
        return CollectionSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), CanCreateCollection()]
        return super().get_permissions()
    
    def get_queryset(self):
        """Фильтрация по роли"""
        queryset = super().get_queryset()
        
        # Бухгалтер видит только свои получения
        if self.request.user.role == 'accountant':
            queryset = queryset.filter(to_user=self.request.user)
        
        # Директор и админ видят все
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """
        POST /api/v1/collections/
        Сбор денег: { from_user, amount }
        Сервер автоматически подставляет to_user = request.user
        """
        serializer = CollectionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            collection = collect_money(
                from_user_id=serializer.validated_data['from_user'],
                to_user=request.user,
                amount=serializer.validated_data['amount']
            )
            
            return Response(
                CollectionSerializer(collection).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {'detail': str(e), 'code': 'collection_failed'},
                status=status.HTTP_400_BAD_REQUEST
            )
