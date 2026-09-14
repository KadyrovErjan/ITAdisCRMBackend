"""
Serializers для ITadis CRM API
"""
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

from .models import (
    User, Group, Student, Transaction, 
    Balance, Collection, Expense, AuditLog
)


# ============= Authentication Serializers =============

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Кастомный serializer для JWT токенов
    Добавляет информацию о пользователе в ответ
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем поле login необязательным и добавляем username
        self.fields[self.username_field].required = False
        self.fields['username'] = serializers.CharField(required=False, write_only=True)
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        return token
    
    def validate(self, attrs):
        # Поддержка обоих полей: username и login
        login_value = attrs.get('login') or attrs.get('username')
        if not login_value:
            raise serializers.ValidationError({
                'login': _('Требуется указать login или username')
            })
        
        # Устанавливаем login для валидации
        attrs['login'] = login_value
        if 'username' in attrs:
            del attrs['username']
        
        data = super().validate(attrs)
        
        # Добавляем информацию о пользователе
        data['user'] = {
            'id': str(self.user.id),
            'login': self.user.login,
            'username': self.user.login,  # Алиас для frontend
            'full_name': self.user.full_name,
            'role': self.user.role,
        }
        
        return data


class LoginSerializer(serializers.Serializer):
    """Serializer для входа в систему"""
    login = serializers.CharField(required=False)
    username = serializers.CharField(required=False)  # Поддержка обоих полей
    password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        # Поддерживаем оба поля: login и username
        login_field = attrs.get('login') or attrs.get('username')
        if not login_field:
            raise serializers.ValidationError({
                'login': _('Требуется указать login или username')
            })
        attrs['login'] = login_field
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer для смены пароля"""
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    
    def validate_new_password(self, value):
        validate_password(value)
        return value
    
    def validate(self, attrs):
        # Проверяем, что новый пароль отличается от старого
        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError({
                'new_password': _('Новый пароль должен отличаться от старого')
            })
        return attrs


# ============= User Serializers =============

class UserSerializer(serializers.ModelSerializer):
    """Serializer для модели User (базовый)"""
    balance = serializers.SerializerMethodField(read_only=True)
    username = serializers.CharField(source='login', read_only=True)  # Алиас для frontend
    
    class Meta:
        model = User
        fields = [
            'id', 'login', 'username', 'full_name', 'role', 
            'is_active', 'created_at', 'balance'
        ]
        read_only_fields = ['id', 'created_at', 'balance', 'username']
    
    def get_balance(self, obj):
        """Получить баланс пользователя (только для кассиров и бухгалтеров)"""
        if obj.role == 'director':
            return None
        try:
            return str(obj.balance.amount)
        except:
            return '0.00'


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer для создания пользователя (только директор)"""
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    # Поддержка username как алиаса для login
    username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    # Поддержка first_name и last_name вместо full_name
    first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = ['id', 'login', 'username', 'full_name', 'first_name', 'last_name', 'role', 'password', 'is_active']
        read_only_fields = ['id']
        extra_kwargs = {
            'full_name': {'required': False},
            'login': {'required': False}
        }
    
    def validate(self, attrs):
        """Обработка username и преобразование first_name/last_name в full_name"""
        # Если пришел username вместо login, используем его
        username = attrs.pop('username', None)
        if username and not attrs.get('login'):
            attrs['login'] = username
        
        # Если пришли first_name и/или last_name, создаем full_name
        first_name = attrs.pop('first_name', '')
        last_name = attrs.pop('last_name', '')
        
        if first_name or last_name:
            attrs['full_name'] = f"{first_name} {last_name}".strip()
        
        # Проверяем обязательные поля
        if not attrs.get('login'):
            raise serializers.ValidationError({
                'login': _('Необходимо указать логин')
            })
        
        if not attrs.get('full_name'):
            raise serializers.ValidationError({
                'full_name': _('Необходимо указать имя и фамилию')
            })
        
        if not attrs.get('password'):
            raise serializers.ValidationError({
                'password': _('Необходимо указать пароль')
            })
        
        return attrs
    
    def create(self, validated_data):
        """Создание пользователя"""
        password = validated_data.pop('password')
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        return user


class UserDetailSerializer(serializers.ModelSerializer):
    """Подробный serializer для пользователя"""
    balance = serializers.SerializerMethodField(read_only=True)
    # Добавляем username как alias для login
    username = serializers.CharField(source='login', read_only=True)
    # Avatar для загрузки изображения
    avatar = serializers.ImageField(required=False, allow_null=True)
    # Разделяем full_name на first_name и last_name для frontend
    first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    # Password для смены пароля через админку
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, min_length=8)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'login', 'full_name', 
            'first_name', 'last_name', 'avatar', 'password',
            'role', 'is_active', 'created_at', 'balance'
        ]
        read_only_fields = ['id', 'created_at', 'username', 'balance']
    
    def get_balance(self, obj):
        """Получить баланс пользователя (только для кассиров и бухгалтеров)"""
        if obj.role == 'director':
            return None
        try:
            return str(obj.balance.amount)
        except:
            return '0.00'
    
    def validate(self, attrs):
        """Преобразуем first_name и last_name в full_name, обрабатываем username -> login"""
        # Маппинг username -> login (username объявлен read_only, берём из initial_data)
        incoming_username = self.initial_data.get('username')
        if incoming_username and incoming_username != getattr(self.instance, 'login', None):
            attrs['login'] = incoming_username
        
        # Если пришли first_name и/или last_name, объединяем в full_name
        first_name = attrs.pop('first_name', None)
        last_name = attrs.pop('last_name', None)
        
        # Игнорируем случай когда ОБА поля пустые строки (нет намерения менять имя)
        if first_name or last_name:
            if first_name is not None and last_name is not None:
                attrs['full_name'] = f"{first_name} {last_name}".strip()
            elif first_name is not None:
                # Только имя, сохраняем фамилию из существующего full_name
                if self.instance and self.instance.full_name:
                    existing_parts = self.instance.full_name.split(maxsplit=1)
                    existing_last = existing_parts[1] if len(existing_parts) > 1 else ''
                    attrs['full_name'] = f"{first_name} {existing_last}".strip()
                else:
                    attrs['full_name'] = first_name.strip()
            elif last_name is not None:
                # Только фамилия, сохраняем имя из существующего full_name
                if self.instance and self.instance.full_name:
                    existing_parts = self.instance.full_name.split(maxsplit=1)
                    existing_first = existing_parts[0] if existing_parts else ''
                    attrs['full_name'] = f"{existing_first} {last_name}".strip()
                else:
                    attrs['full_name'] = last_name.strip()
        
        return attrs
    
    def to_representation(self, instance):
        """При выдаче добавляем first_name и last_name"""
        data = super().to_representation(instance)
        
        # Разделяем full_name на first_name и last_name
        if instance.full_name:
            parts = instance.full_name.split(maxsplit=1)
            data['first_name'] = parts[0] if parts else ''
            data['last_name'] = parts[1] if len(parts) > 1 else ''
        else:
            data['first_name'] = ''
            data['last_name'] = ''
        
        # Добавляем полный URL аватара
        if instance.avatar:
            request = self.context.get('request')
            if request:
                data['avatar'] = request.build_absolute_uri(instance.avatar.url)
            else:
                data['avatar'] = instance.avatar.url
        else:
            data['avatar'] = None
        
        return data
    
    def update(self, instance, validated_data):
        """Обработка смены пароля через set_password"""
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=['password'])
        return instance


# ============= Group Serializers =============

class GroupSerializer(serializers.ModelSerializer):
    """Serializer для групп обучения"""
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    student_count = serializers.SerializerMethodField(read_only=True)
    progress_percent = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Group
        fields = [
            'id', 'name', 'subject', 'schedule', 
            'total_lessons', 'current_lesson', 'status',
            'created_by', 'created_by_name', 
            'created_at', 'student_count', 'progress_percent'
        ]
        read_only_fields = ['id', 'created_by', 'created_at']
    
    def get_student_count(self, obj):
        return obj.students.count()
    
    def get_progress_percent(self, obj):
        if obj.total_lessons > 0:
            return round((obj.current_lesson / obj.total_lessons) * 100, 2)
        return 0.0
    
    def validate(self, attrs):
        # Валидация: current_lesson <= total_lessons
        current = attrs.get('current_lesson', 0)
        total = attrs.get('total_lessons', 0)
        
        if current > total:
            raise serializers.ValidationError({
                'current_lesson': _('Текущее занятие не может превышать общее количество')
            })
        
        return attrs


class GroupProgressSerializer(serializers.Serializer):
    """Serializer для обновления прогресса группы"""
    current_lesson = serializers.IntegerField(min_value=0)
    
    def validate_current_lesson(self, value):
        group = self.context.get('group')
        if group and value > group.total_lessons:
            raise serializers.ValidationError(
                _('Текущее занятие не может превышать общее количество (%(total)s)') % {
                    'total': group.total_lessons
                }
            )
        return value


# ============= Student Serializers =============

class StudentSerializer(serializers.ModelSerializer):
    """Serializer для учеников"""
    group_name = serializers.CharField(source='group.name', read_only=True)
    registered_by_name = serializers.CharField(source='registered_by.full_name', read_only=True)
    amount_paid_total = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Student
        fields = [
            'id', 'full_name', 'group', 'group_name',
            'registered_by', 'registered_by_name',
            'status', 'created_at', 'amount_paid_total'
        ]
        read_only_fields = ['id', 'registered_by', 'created_at']
    
    def get_amount_paid_total(self, obj):
        return str(obj.amount_paid_total)


class StudentRegistrationSerializer(serializers.Serializer):
    """Serializer для регистрации нового ученика с первым платежом"""
    full_name = serializers.CharField(max_length=255)
    group = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(_('Сумма должна быть больше нуля'))
        return value


class StudentTopupSerializer(serializers.Serializer):
    """Serializer для доплаты от ученика"""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(_('Сумма должна быть больше нуля'))
        return value


# ============= Transaction Serializers =============

class TransactionSerializer(serializers.ModelSerializer):
    """Serializer для транзакций"""
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    cashier_name = serializers.CharField(source='cashier.full_name', read_only=True)
    group_name = serializers.CharField(source='student.group.name', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'student', 'student_name', 'group_name',
            'cashier', 'cashier_name', 'amount', 
            'type', 'type_display', 'created_at'
        ]
        read_only_fields = ['id', 'student', 'cashier', 'created_at']


# ============= Balance Serializers =============

class BalanceSerializer(serializers.ModelSerializer):
    """Serializer для балансов"""
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_role = serializers.CharField(source='user.role', read_only=True)
    
    class Meta:
        model = Balance
        fields = ['user', 'user_name', 'user_role', 'amount', 'updated_at']
        read_only_fields = ['user', 'amount', 'updated_at']


# ============= Collection Serializers =============

class CollectionSerializer(serializers.ModelSerializer):
    """Serializer для сборов"""
    from_user_name = serializers.CharField(source='from_user.full_name', read_only=True)
    to_user_name = serializers.CharField(source='to_user.full_name', read_only=True)
    
    class Meta:
        model = Collection
        fields = [
            'id', 'from_user', 'from_user_name',
            'to_user', 'to_user_name', 
            'amount', 'created_at'
        ]
        read_only_fields = ['id', 'to_user', 'created_at']


class CollectionCreateSerializer(serializers.Serializer):
    """Serializer для создания сбора"""
    from_user = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(_('Сумма должна быть больше нуля'))
        return value


# ============= Expense Serializers =============

class ExpenseSerializer(serializers.ModelSerializer):
    """Serializer для расходов"""
    entered_by_name = serializers.CharField(source='entered_by.full_name', read_only=True)
    
    class Meta:
        model = Expense
        fields = [
            'id', 'amount', 'comment', 
            'entered_by', 'entered_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'entered_by', 'created_at']
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(_('Сумма должна быть больше нуля'))
        return value
    
    def validate_comment(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(_('Комментарий обязателен'))
        return value.strip()


class ExpenseCreateSerializer(serializers.Serializer):
    """Serializer для создания расхода"""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    comment = serializers.CharField()
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(_('Сумма должна быть больше нуля'))
        return value
    
    def validate_comment(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(_('Комментарий обязателен'))
        return value.strip()


# ============= AuditLog Serializers =============

class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer для журнала аудита"""
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_name', 'action', 
            'object_type', 'object_id', 'payload', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']


# ============= Analytics Serializers =============

class AnalyticsSummarySerializer(serializers.Serializer):
    """Serializer для общей аналитики"""
    total_income = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_expense = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_profit = serializers.DecimalField(max_digits=12, decimal_places=2)
    period = serializers.DictField()


class AnalyticsMonthlySerializer(serializers.Serializer):
    """Serializer для помесячной аналитики"""
    month = serializers.CharField()
    income = serializers.DecimalField(max_digits=12, decimal_places=2)
    expense = serializers.DecimalField(max_digits=12, decimal_places=2)
    profit = serializers.DecimalField(max_digits=12, decimal_places=2)


class AnalyticsExpensesByUserSerializer(serializers.Serializer):
    """Serializer для расходов по пользователям"""
    user_id = serializers.CharField()
    user_name = serializers.CharField()
    user_role = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    expense_count = serializers.IntegerField()
