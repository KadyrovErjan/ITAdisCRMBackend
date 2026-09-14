"""
Permission-классы для контроля доступа по ролям
Согласно ТЗ раздел 3 - матрица доступа
"""
from rest_framework import permissions
from django.utils.translation import gettext_lazy as _
from .services.audit import log_permission_denied


class IsCashier(permissions.BasePermission):
    """Доступ только для кассиров"""
    message = _('Доступ только для кассиров')
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        has_perm = request.user.role == 'cashier'
        if not has_perm:
            log_permission_denied(request.user, view.action if hasattr(view, 'action') else 'unknown', view.__class__.__name__)
        return has_perm


class IsAccountant(permissions.BasePermission):
    """Доступ только для бухгалтеров"""
    message = _('Доступ только для бухгалтеров')
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        has_perm = request.user.role == 'accountant'
        if not has_perm:
            log_permission_denied(request.user, view.action if hasattr(view, 'action') else 'unknown', view.__class__.__name__)
        return has_perm


class IsDirector(permissions.BasePermission):
    """Доступ только для директора"""
    message = _('Доступ только для директора')
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        has_perm = request.user.role == 'director'
        if not has_perm:
            log_permission_denied(request.user, view.action if hasattr(view, 'action') else 'unknown', view.__class__.__name__)
        return has_perm


class IsAccountantOrDirector(permissions.BasePermission):
    """Доступ для бухгалтера или директора"""
    message = _('Доступ только для бухгалтера или директора')
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        has_perm = request.user.role in ['accountant', 'director']
        if not has_perm:
            log_permission_denied(request.user, view.action if hasattr(view, 'action') else 'unknown', view.__class__.__name__)
        return has_perm


class IsDirectorOrAdmin(permissions.BasePermission):
    """Совместимость имени: доступ только для директора."""
    message = _('Доступ только для директора или администратора')
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        has_perm = request.user.role == 'director'
        if not has_perm:
            log_permission_denied(request.user, view.action if hasattr(view, 'action') else 'unknown', view.__class__.__name__)
        return has_perm


class IsAccountantOrDirectorOrAdmin(permissions.BasePermission):
    """Совместимость имени: доступ бухгалтеру или директору."""
    message = _('Доступ только для бухгалтера, директора или администратора')
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        has_perm = request.user.role in ['accountant', 'director']
        if not has_perm:
            log_permission_denied(request.user, view.action if hasattr(view, 'action') else 'unknown', view.__class__.__name__)
        return has_perm


class IsOwnerCashier(permissions.BasePermission):
    """
    Кассир может редактировать только свои созданные объекты
    Используется на уровне объекта (has_object_permission)
    """
    message = _('Вы можете редактировать только свои объекты')
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Для кассира проверяем, что он создатель
        if request.user.role == 'cashier':
            # Проверяем разные поля в зависимости от модели
            creator_field = None
            if hasattr(obj, 'created_by'):
                creator_field = obj.created_by
            elif hasattr(obj, 'registered_by'):
                creator_field = obj.registered_by
            elif hasattr(obj, 'cashier'):
                creator_field = obj.cashier
            
            if creator_field:
                return creator_field.id == request.user.id
        
        return False


class IsOwnerCashierOrReadOnlyForAccountantDirector(permissions.BasePermission):
    """
    Кассир может создавать/редактировать только свои объекты
    Бухгалтер/директор/админ могут только читать (list/retrieve)
    Согласно ТЗ раздел 3 - для групп и учеников
    """
    message = _('У вас нет прав на это действие')
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Бухгалтер, директор, админ - только чтение
        if request.user.role in ['accountant', 'director']:
            return request.method in permissions.SAFE_METHODS
        
        # Кассир - полный доступ (но проверка владельца на уровне объекта)
        if request.user.role == 'cashier':
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Чтение разрешено всем аутентифицированным
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Изменение только для кассира-владельца
        if request.user.role == 'cashier':
            creator_field = None
            if hasattr(obj, 'created_by'):
                creator_field = obj.created_by
            elif hasattr(obj, 'registered_by'):
                creator_field = obj.registered_by
            
            if creator_field:
                return creator_field.id == request.user.id
        
        return False


class CanViewOwnTransactions(permissions.BasePermission):
    """
    Кассир видит только свои транзакции
    Бухгалтер/директор/админ видят все
    Согласно ТЗ п.3 - раздел "Транзакции — просмотр"
    """
    message = _('Вы можете видеть только свои транзакции')
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Все роли могут просматривать (но фильтруется в queryset)
        return request.method in permissions.SAFE_METHODS
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Только чтение
        if request.method not in permissions.SAFE_METHODS:
            return False
        
        # Бухгалтер, директор, админ видят все
        if request.user.role in ['accountant', 'director']:
            return True
        
        # Кассир видит только свои
        if request.user.role == 'cashier':
            return obj.cashier.id == request.user.id
        
        return False


class CanViewOwnBalance(permissions.BasePermission):
    """
    Все сотрудники могут видеть свой баланс
    Бухгалтер/директор/админ могут видеть балансы всех
    Согласно ТЗ п.3 - раздел "Свой баланс" и "Балансы всех сотрудников"
    """
    message = _('У вас нет доступа к этому балансу')
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Только чтение
        if request.method not in permissions.SAFE_METHODS:
            return False
        
        # Бухгалтер, директор, админ видят все балансы
        if request.user.role in ['accountant', 'director']:
            return True
        
        # Кассир видит только свой баланс
        if request.user.role == 'cashier':
            return obj.user.id == request.user.id
        
        return False


class CanCreateCollection(permissions.BasePermission):
    """
    Создание сборов:
    - Бухгалтер может собирать у кассиров
    - Директор может собирать у кассиров и бухгалтера
    Согласно ТЗ п.3 - раздел "Сбор денег (collections) — создание"
    """
    message = _('У вас нет прав на сбор денег')
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Только бухгалтер и директор
        return request.user.role in ['accountant', 'director']


class CanCreateExpense(permissions.BasePermission):
    """
    Создание расходов: только бухгалтер и директор (с своего баланса)
    Согласно ТЗ п.3 - раздел "Расходы (expenses) — создание"
    """
    message = _('Только бухгалтер и директор могут создавать расходы')
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.role in ['accountant', 'director']


class CanViewAnalytics(permissions.BasePermission):
    """
    Доступ к аналитике: только директор
    Согласно ТЗ п.3 - раздел "Аналитика (/analytics/*)"
    """
    message = _('Доступ к аналитике только для директора')
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        has_perm = request.user.role == 'director'
        if not has_perm:
            log_permission_denied(request.user, 'view_analytics', view.__class__.__name__)
        return has_perm


class CanManageUsers(permissions.BasePermission):
    """Управление сотрудниками — только директор."""
    message = _('Управление пользователями доступно только директору')
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Чтение своего профиля доступно всем
        if view.action == 'me' and request.method in permissions.SAFE_METHODS:
            return True
        
        # Смена своего пароля доступна всем
        if view.action == 'change_password':
            return True
        
        # Остальное — только директор
        has_perm = request.user.role == 'director'
        if not has_perm and view.action not in ['me', 'change_password']:
            log_permission_denied(request.user, view.action, view.__class__.__name__)
        return has_perm


class ReadOnly(permissions.BasePermission):
    """Только чтение (для append-only моделей)"""
    message = _('Изменение и удаление запрещено')
    
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS
    
    def has_object_permission(self, request, view, obj):
        return request.method in permissions.SAFE_METHODS
