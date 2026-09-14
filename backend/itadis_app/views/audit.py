"""
Views для журнала аудита
Согласно ТЗ п.6.8
"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema_view, extend_schema

from ..models import AuditLog
from ..serializers import AuditLogSerializer
from ..permissions import IsDirectorOrAdmin


from ..filters import AuditLogFilter


@extend_schema_view(
    list=extend_schema(
        tags=['audit'], 
        description='Просмотр журнала аудита (только директор/админ)'
    ),
    retrieve=extend_schema(tags=['audit'], description='Детали записи аудита'),
)
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для журнала аудита (только чтение)
    Доступ: директор и админ
    """
    queryset = AuditLog.objects.all().select_related('user')
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsDirectorOrAdmin]
    filterset_class = AuditLogFilter
    search_fields = ['action', 'object_type']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Базовый queryset без дополнительной фильтрации"""
        return super().get_queryset()
