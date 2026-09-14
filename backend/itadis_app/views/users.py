"""
Views для управления пользователями
Согласно ТЗ п.6.1
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.utils.translation import gettext_lazy as _

from ..models import User
from ..serializers import (
    UserSerializer, UserCreateSerializer, 
    UserDetailSerializer, ChangePasswordSerializer
)
from ..permissions import CanManageUsers
from ..services.audit import log_action


@extend_schema_view(
    list=extend_schema(tags=['users'], description='Список сотрудников (только директор)'),
    retrieve=extend_schema(tags=['users'], description='Детали сотрудника'),
    create=extend_schema(tags=['users'], description='Создание сотрудника (только директор)'),
    update=extend_schema(tags=['users'], description='Обновление сотрудника (только директор)'),
    partial_update=extend_schema(tags=['users'], description='Частичное обновление сотрудника (только директор)'),
)
class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления пользователями
    """
    queryset = User.objects.all().select_related('balance')
    permission_classes = [IsAuthenticated, CanManageUsers]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['retrieve', 'update', 'partial_update']:
            return UserDetailSerializer
        return UserSerializer
    
    def get_serializer_context(self):
        """Добавляем request в context для всех serializers"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def get_permissions(self):
        """Разные права для разных действий"""
        if self.action in ['me', 'change_password']:
            return [IsAuthenticated()]
        return super().get_permissions()
    
    def perform_create(self, serializer):
        user = serializer.save()
        log_action(
            user=self.request.user,
            action='user.create',
            object_type='User',
            object_id=user.id,
            payload={
                'created_user_login': user.login,
                'created_user_role': user.role
            }
        )
    
    def perform_update(self, serializer):
        user = serializer.save()
        log_action(
            user=self.request.user,
            action='user.update',
            object_type='User',
            object_id=user.id,
            payload={
                'updated_user_login': user.login,
                'changes': list(serializer.validated_data.keys())
            }
        )
    
    @extend_schema(
        tags=['users'],
        description='Получить данные текущего пользователя',
        responses={200: UserDetailSerializer}
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """
        GET /api/v1/users/me/
        Возвращает данные текущего пользователя
        """
        serializer = UserDetailSerializer(request.user, context={'request': request})
        return Response(serializer.data)
    
    @extend_schema(
        tags=['users'],
        description='Обновить данные текущего пользователя',
        request=UserDetailSerializer,
        responses={200: UserDetailSerializer}
    )
    @me.mapping.patch
    def update_me(self, request):
        """
        PATCH /api/v1/users/me/
        Обновление собственного профиля (username/login, first_name, last_name, avatar)
        """
        user = request.user
        
        serializer = UserDetailSerializer(
            user, 
            data=request.data, 
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        # Запрещаем менять роль через этот endpoint
        if 'role' in serializer.validated_data:
            return Response(
                {'detail': _('Нельзя изменить роль через этот endpoint'), 'code': 'permission_denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer.save()
        
        # Логируем изменение профиля
        log_action(
            user=user,
            action='profile.update',
            object_type='User',
            object_id=user.id,
            payload={'changes': list(serializer.validated_data.keys())}
        )
        
        return Response(serializer.data)
    
    @extend_schema(
        tags=['users'],
        description='Смена собственного пароля',
        request=ChangePasswordSerializer,
        responses={200: {'description': 'Пароль успешно изменён'}}
    )
    @action(detail=False, methods=['patch'], permission_classes=[IsAuthenticated])
    def change_password(self, request):
        """
        PATCH /api/v1/users/me/password/
        Смена собственного пароля
        """
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        
        # Проверяем текущий пароль
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'detail': _('Неверный текущий пароль'), 'code': 'invalid_password'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Устанавливаем новый пароль
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        # Логируем смену пароля
        log_action(
            user=user,
            action='password.change',
            object_type='User',
            object_id=user.id
        )
        
        return Response(
            {'detail': _('Пароль успешно изменён')},
            status=status.HTTP_200_OK
        )
