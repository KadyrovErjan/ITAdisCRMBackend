"""
Views для групп обучения
Согласно ТЗ п.6.2
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.utils.translation import gettext_lazy as _

from ..models import Group, Student
from ..serializers import GroupSerializer, GroupProgressSerializer, StudentSerializer
from ..permissions import IsOwnerCashierOrReadOnlyForAccountantDirector
from ..services.audit import log_action
from ..filters import GroupFilter


@extend_schema_view(
    list=extend_schema(tags=['groups'], description='Список групп'),
    retrieve=extend_schema(tags=['groups'], description='Детали группы'),
    create=extend_schema(tags=['groups'], description='Создание группы (только cashier)'),
    update=extend_schema(tags=['groups'], description='Обновление группы'),
    partial_update=extend_schema(tags=['groups'], description='Частичное обновление группы'),
)
class GroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet для групп обучения
    Кассир создает и редактирует только свои группы
    Бухгалтер/директор/админ - только чтение
    """
    queryset = Group.objects.all().select_related('created_by').prefetch_related('students')
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated, IsOwnerCashierOrReadOnlyForAccountantDirector]
    filterset_class = GroupFilter
    search_fields = ['name', 'subject']
    ordering_fields = ['created_at', 'name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Кассир видит только свои группы, остальные - все"""
        queryset = super().get_queryset()
        
        if self.request.user.role == 'cashier':
            queryset = queryset.filter(created_by=self.request.user)
        
        return queryset
    
    def perform_create(self, serializer):
        """Автоматически устанавливаем created_by"""
        group = serializer.save(created_by=self.request.user)
        log_action(
            user=self.request.user,
            action='group.create',
            object_type='Group',
            object_id=group.id,
            payload={'group_name': group.name}
        )
    
    @extend_schema(
        tags=['groups'],
        description='Обновить прогресс группы (current_lesson)',
        request=GroupProgressSerializer,
        responses={200: GroupSerializer}
    )
    @action(detail=True, methods=['patch'])
    def progress(self, request, pk=None):
        """
        PATCH /api/v1/groups/{id}/progress/
        Обновление прогресса группы (изменение current_lesson)
        """
        group = self.get_object()
        
        # Проверяем права: кассир только свои, директор все
        if request.user.role == 'cashier' and group.created_by != request.user:
            return Response(
                {'detail': _('Вы можете обновлять только свои группы'), 'code': 'permission_denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request.user.role not in ['cashier', 'director']:
            return Response(
                {'detail': _('У вас нет прав на это действие'), 'code': 'permission_denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = GroupProgressSerializer(data=request.data, context={'group': group})
        serializer.is_valid(raise_exception=True)
        
        old_lesson = group.current_lesson
        group.current_lesson = serializer.validated_data['current_lesson']
        group.save(update_fields=['current_lesson'])
        
        log_action(
            user=request.user,
            action='group.progress.update',
            object_type='Group',
            object_id=group.id,
            payload={
                'old_lesson': old_lesson,
                'new_lesson': group.current_lesson
            }
        )
        
        return Response(GroupSerializer(group).data)
    
    @extend_schema(
        tags=['groups'],
        description='Список учеников группы',
        responses={200: StudentSerializer(many=True)}
    )
    @action(detail=True, methods=['get'])
    def students(self, request, pk=None):
        """
        GET /api/v1/groups/{id}/students/
        Список учеников группы с суммами оплат
        """
        group = self.get_object()
        students = group.students.all().select_related('registered_by', 'group')
        serializer = StudentSerializer(students, many=True)
        # Возвращаем в формате пагинации для совместимости с frontend
        return Response({
            'count': len(serializer.data),
            'results': serializer.data
        })
    
    @extend_schema(
        tags=['groups'],
        description='Изменение статуса группы',
        request={'type': 'object', 'properties': {'status': {'type': 'string', 'enum': ['active', 'completed', 'archived']}}},
        responses={200: GroupSerializer}
    )
    @action(detail=True, methods=['patch'], url_path='change-status')
    def change_status(self, request, pk=None):
        """
        PATCH /api/v1/groups/{id}/change-status/
        Изменение статуса группы (active/completed/archived)
        """
        group = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in ['active', 'completed', 'archived']:
            return Response(
                {'detail': 'Неверный статус. Допустимые: active, completed, archived'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверяем права: кассир только свои, директор все
        if request.user.role == 'cashier' and group.created_by != request.user:
            return Response(
                {'detail': _('Вы можете изменять только свои группы'), 'code': 'permission_denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        old_status = group.status
        group.status = new_status
        group.save(update_fields=['status'])
        
        log_action(
            user=request.user,
            action='group.status.change',
            object_type='Group',
            object_id=group.id,
            payload={
                'old_status': old_status,
                'new_status': new_status
            }
        )
        
        return Response(GroupSerializer(group).data)
