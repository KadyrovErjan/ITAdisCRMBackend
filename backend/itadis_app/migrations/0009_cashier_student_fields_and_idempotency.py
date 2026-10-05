# Generated manually because the local environment has no Django runtime.
import django.core.validators
import django.db.models.deletion
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('itadis_app', '0008_user_avatar'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='assistant_name',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Ассистент'),
        ),
        migrations.AddField(
            model_name='student',
            name='comment',
            field=models.TextField(blank=True, null=True, verbose_name='Комментарий'),
        ),
        migrations.AddField(
            model_name='student',
            name='contract_status',
            field=models.CharField(choices=[('unknown', 'Не указан'), ('signed', 'Подписан'), ('not_signed', 'Не подписан')], default='unknown', max_length=20, verbose_name='Статус договора'),
        ),
        migrations.AddField(
            model_name='student',
            name='course_price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))], verbose_name='Цена курса'),
        ),
        migrations.AddField(
            model_name='student',
            name='phone',
            field=models.CharField(blank=True, max_length=32, null=True, verbose_name='Телефон'),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='type',
            field=models.CharField(choices=[('booking', 'Бронь'), ('register', 'Регистрация'), ('topup', 'Доплата')], max_length=12, verbose_name='Тип'),
        ),
        migrations.CreateModel(
            name='IdempotencyKey',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('key', models.CharField(max_length=64, verbose_name='Ключ идемпотентности')),
                ('operation', models.CharField(choices=[('registration', 'Регистрация ученика'), ('payment', 'Платёж ученика')], max_length=20, verbose_name='Операция')),
                ('request_hash', models.CharField(max_length=64, verbose_name='Хэш запроса')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('cashier', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='idempotency_keys', to=settings.AUTH_USER_MODEL, verbose_name='Кассир')),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='idempotency_records', to='itadis_app.student')),
                ('transaction', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='idempotency_records', to='itadis_app.transaction')),
            ],
            options={
                'verbose_name': 'Ключ идемпотентности',
                'verbose_name_plural': 'Ключи идемпотентности',
                'db_table': 'idempotency_keys',
            },
        ),
        migrations.AddConstraint(
            model_name='idempotencykey',
            constraint=models.UniqueConstraint(fields=('cashier', 'key'), name='unique_idempotency_key_per_cashier'),
        ),
    ]
