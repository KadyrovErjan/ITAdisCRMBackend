"""
Админка Django для управления моделями ITadis CRM
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import (
    User, Group, Student, Transaction, 
    Balance, Collection, Expense, AuditLog
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Админка для кастомной модели User"""
    list_display = ('login', 'full_name', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'created_at')
    search_fields = ('login', 'full_name')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('login', 'password')}),
        (_('Личная информация'), {'fields': ('full_name', 'role')}),
        (_('Права доступа'), {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        (_('Даты'), {'fields': ('created_at',)}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('login', 'full_name', 'role', 'password1', 'password2', 'is_active'),
        }),
    )
    
    readonly_fields = ('created_at',)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    """Админка для групп обучения"""
    list_display = ('name', 'subject', 'schedule', 'current_lesson', 'total_lessons', 'created_by', 'created_at')
    list_filter = ('subject', 'created_at', 'created_by')
    search_fields = ('name', 'subject')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (_('Основная информация'), {
            'fields': ('name', 'subject', 'schedule')
        }),
        (_('Прогресс'), {
            'fields': ('total_lessons', 'current_lesson')
        }),
        (_('Служебная информация'), {
            'fields': ('created_by', 'created_at')
        }),
    )


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    """Админка для учеников"""
    list_display = ('full_name', 'group', 'amount_paid_total', 'registered_by', 'created_at')
    list_filter = ('group', 'created_at', 'registered_by')
    search_fields = ('full_name',)
    readonly_fields = ('created_at', 'amount_paid_total')
    
    def amount_paid_total(self, obj):
        return obj.amount_paid_total
    amount_paid_total.short_description = _('Всего оплачено')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Админка для транзакций (только чтение)"""
    list_display = ('student', 'cashier', 'amount', 'type', 'created_at')
    list_filter = ('type', 'created_at', 'cashier')
    search_fields = ('student__full_name', 'cashier__full_name')
    readonly_fields = ('id', 'student', 'cashier', 'amount', 'type', 'created_at')
    
    def has_add_permission(self, request):
        """Запрет на добавление через админку (только через API)"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Запрет на изменение (append-only)"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Запрет на удаление (append-only)"""
        return False


@admin.register(Balance)
class BalanceAdmin(admin.ModelAdmin):
    """Админка для балансов"""
    list_display = ('user', 'amount', 'updated_at')
    search_fields = ('user__full_name', 'user__login')
    readonly_fields = ('user', 'amount', 'updated_at')
    
    def has_add_permission(self, request):
        """Баланс создаётся автоматически при создании пользователя"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Баланс удаляется вместе с пользователем"""
        return False


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    """Админка для сборов (только чтение)"""
    list_display = ('from_user', 'to_user', 'amount', 'created_at')
    list_filter = ('created_at', 'from_user', 'to_user')
    search_fields = ('from_user__full_name', 'to_user__full_name')
    readonly_fields = ('id', 'from_user', 'to_user', 'amount', 'created_at')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    """Админка для расходов (только чтение)"""
    list_display = ('entered_by', 'amount', 'comment_short', 'created_at')
    list_filter = ('created_at', 'entered_by')
    search_fields = ('comment', 'entered_by__full_name')
    readonly_fields = ('id', 'amount', 'comment', 'entered_by', 'created_at')
    
    def comment_short(self, obj):
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    comment_short.short_description = _('Комментарий')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Админка для журнала аудита (только чтение)"""
    list_display = ('user', 'action', 'object_type', 'object_id', 'created_at')
    list_filter = ('action', 'object_type', 'created_at')
    search_fields = ('user__full_name', 'action', 'object_type')
    readonly_fields = ('id', 'user', 'action', 'object_type', 'object_id', 'payload', 'created_at')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
