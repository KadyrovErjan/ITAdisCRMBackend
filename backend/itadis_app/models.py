"""
Модели данных для системы ITadis CRM
Согласно ТЗ раздел 5
"""
import uuid
from decimal import Decimal
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Менеджер для кастомной модели User"""
    
    def create_user(self, login, password=None, **extra_fields):
        """Создание обычного пользователя"""
        if not login:
            raise ValueError(_('Login обязателен'))
        
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        
        user = self.model(login=login, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, login, password=None, **extra_fields):
        """Создание суперпользователя"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        # The project has exactly three business roles. A Django superuser is
        # also the first director, not a separate application role.
        extra_fields.setdefault('role', 'director')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser должен иметь is_staff=True'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser должен иметь is_superuser=True'))
        
        return self.create_user(login, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Кастомная модель пользователя (сотрудника)
    Согласно ТЗ п.5.1
    """
    ROLE_CHOICES = (
        ('cashier', _('Кассир')),
        ('accountant', _('Бухгалтер')),
        ('director', _('Директор')),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(_('ФИО'), max_length=255)
    role = models.CharField(_('Роль'), max_length=20, choices=ROLE_CHOICES)
    login = models.CharField(_('Логин'), max_length=100, unique=True)
    avatar = models.ImageField(_('Аватар'), upload_to='avatars/', null=True, blank=True)
    is_active = models.BooleanField(_('Активен'), default=True)
    is_staff = models.BooleanField(_('Персонал'), default=False)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'login'
    REQUIRED_FIELDS = ['full_name', 'role']
    
    class Meta:
        verbose_name = _('Пользователь')
        verbose_name_plural = _('Пользователи')
        db_table = 'users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"
    
    def save(self, *args, **kwargs):
        """При создании пользователя автоматически создаём баланс (кроме директора)"""
        is_new = self._state.adding
        super().save(*args, **kwargs)
        
        # Баланс создаётся только для кассиров и бухгалтеров, не для директоров
        if is_new and self.role != 'director':
            Balance.objects.get_or_create(
                user=self,
                defaults={'amount': Decimal('0.00')}
            )


class Group(models.Model):
    """
    Группа обучения
    Согласно ТЗ п.5.2
    """
    STATUS_CHOICES = (
        ('active', _('Активдүү')),
        ('completed', _('Аяктады')),
        ('archived', _('Архивделген')),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('Название группы'), max_length=255)
    subject = models.CharField(_('Предмет'), max_length=255)
    schedule = models.CharField(_('Расписание'), max_length=255)
    total_lessons = models.PositiveIntegerField(_('Общее количество занятий'))
    current_lesson = models.PositiveIntegerField(_('Текущее занятие'), default=0)
    status = models.CharField(
        _('Статус группы'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text=_('Статус активности группы')
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,
        related_name='created_groups',
        verbose_name=_('Создал')
    )
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Группа')
        verbose_name_plural = _('Группы')
        db_table = 'groups'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.subject}"
    
    def clean(self):
        """Валидация: current_lesson не может превышать total_lessons"""
        from django.core.exceptions import ValidationError
        if self.current_lesson > self.total_lessons:
            raise ValidationError({
                'current_lesson': _('Текущее занятие не может превышать общее количество')
            })


class Student(models.Model):
    """
    Ученик
    Согласно ТЗ п.5.3
    amount_paid_total - вычисляемое поле (property)
    """
    STATUS_CHOICES = (
        ('active', _('Толук төлөп бүттү')),
        ('debt', _('Төлөө элек')),
        ('frozen', _('Тоңдурулган')),
        ('expelled', _('Чыгарылган')),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(_('ФИО ученика'), max_length=255)
    group = models.ForeignKey(
        Group,
        on_delete=models.PROTECT,
        related_name='students',
        verbose_name=_('Группа')
    )
    registered_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='registered_students',
        verbose_name=_('Зарегистрировал')
    )
    status = models.CharField(
        _('Статус'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text=_('Статус оплаты/активности ученика')
    )
    created_at = models.DateTimeField(_('Дата регистрации'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Ученик')
        verbose_name_plural = _('Ученики')
        db_table = 'students'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.full_name} ({self.group.name})"
    
    @property
    def amount_paid_total(self):
        """Вычисляемое поле - сумма всех транзакций ученика"""
        from django.db.models import Sum
        total = self.transactions.aggregate(total=Sum('amount'))['total']
        return total or Decimal('0.00')


class Transaction(models.Model):
    """
    Транзакция (поступление от ученика) - append-only
    Согласно ТЗ п.5.4
    """
    TYPE_CHOICES = (
        ('register', _('Регистрация')),
        ('topup', _('Доплата')),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        related_name='transactions',
        verbose_name=_('Ученик')
    )
    cashier = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='transactions',
        verbose_name=_('Кассир')
    )
    amount = models.DecimalField(
        _('Сумма'),
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    type = models.CharField(_('Тип'), max_length=12, choices=TYPE_CHOICES)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Транзакция')
        verbose_name_plural = _('Транзакции')
        db_table = 'transactions'
        ordering = ['-created_at']
        # Запрет на изменение и удаление на уровне БД (опционально)
        permissions = [
            ('view_all_transactions', 'Can view all transactions'),
        ]
    
    def __str__(self):
        return f"{self.student.full_name} - {self.amount} ({self.get_type_display()})"


class Balance(models.Model):
    """
    Баланс сотрудника
    Согласно ТЗ п.5.5
    Изменяется только через сервисный слой
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='balance',
        verbose_name=_('Пользователь')
    )
    amount = models.DecimalField(
        _('Баланс'),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    updated_at = models.DateTimeField(_('Дата обновления'), auto_now=True)
    
    class Meta:
        verbose_name = _('Баланс')
        verbose_name_plural = _('Балансы')
        db_table = 'balances'
    
    def __str__(self):
        return f"{self.user.full_name}: {self.amount}"


class Collection(models.Model):
    """
    Сбор денег (перевод между сотрудниками) - append-only
    Согласно ТЗ п.5.6
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='collections_from',
        verbose_name=_('От кого')
    )
    to_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='collections_to',
        verbose_name=_('Кому')
    )
    amount = models.DecimalField(
        _('Сумма'),
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Сбор')
        verbose_name_plural = _('Сборы')
        db_table = 'collections'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.from_user.full_name} → {self.to_user.full_name}: {self.amount}"


class Expense(models.Model):
    """
    Расход - append-only
    Согласно ТЗ п.5.7
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    amount = models.DecimalField(
        _('Сумма'),
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    comment = models.TextField(_('Комментарий'))  # Обязательное поле
    entered_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='expenses',
        verbose_name=_('Внёс')
    )
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Расход')
        verbose_name_plural = _('Расходы')
        db_table = 'expenses'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.entered_by.full_name}: {self.amount} - {self.comment[:50]}"


class AuditLog(models.Model):
    """
    Журнал аудита
    Согласно ТЗ п.5.8
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name=_('Пользователь')
    )
    action = models.CharField(_('Действие'), max_length=255)
    object_type = models.CharField(_('Тип объекта'), max_length=100, blank=True)
    object_id = models.UUIDField(_('ID объекта'), null=True, blank=True)
    payload = models.JSONField(_('Данные'), default=dict, blank=True)
    created_at = models.DateTimeField(_('Дата создания'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Лог аудита')
        verbose_name_plural = _('Логи аудита')
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action', '-created_at']),
        ]
    
    def __str__(self):
        user_name = self.user.full_name if self.user else 'Anonymous'
        return f"{user_name}: {self.action} ({self.created_at})"
