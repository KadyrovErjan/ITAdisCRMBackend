import django.core.validators
import django.db.models.deletion
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('itadis_app', '0009_cashier_student_fields_and_idempotency')]

    operations = [
        migrations.AddField(model_name='group', name='technology', field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Направление')),
        migrations.AddField(model_name='group', name='duration_months', field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Длительность в месяцах')),
        migrations.AddField(model_name='group', name='study_days_per_week', field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Учебных дней в неделю')),
        migrations.AddField(model_name='group', name='start_date', field=models.DateField(blank=True, null=True, verbose_name='Дата начала')),
        migrations.AddField(model_name='group', name='end_date', field=models.DateField(blank=True, null=True, verbose_name='Дата окончания')),
        migrations.AddField(model_name='student', name='learning_status', field=models.CharField(blank=True, choices=[('active', 'Активный'), ('frozen', 'Заморожен'), ('completed', 'Завершил обучение'), ('archived', 'Архивирован')], max_length=20, null=True, verbose_name='Статус обучения')),
        migrations.CreateModel(name='PaymentPlan', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('payment_method', models.CharField(choices=[('full', 'Полностью'), ('monthly', 'Ежемесячно'), ('custom', 'Индивидуально')], max_length=12)),
            ('period_count', models.PositiveSmallIntegerField(default=1)), ('start_date', models.DateField()),
            ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_payment_plans', to=settings.AUTH_USER_MODEL)),
            ('student', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='payment_plan', to='itadis_app.student')),
        ], options={'db_table': 'payment_plans'}),
        migrations.CreateModel(name='PaymentScheduleItem', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('due_date', models.DateField()),
            ('amount_due', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))])),
            ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='items', to='itadis_app.paymentplan')),
            ('student', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payment_schedule_items', to='itadis_app.student')),
        ], options={'db_table': 'payment_schedule_items', 'ordering': ['due_date', 'created_at']}),
        migrations.CreateModel(name='PaymentSchedulePause', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('started_on', models.DateField()), ('ended_on', models.DateField(blank=True, null=True)), ('shifted_days', models.PositiveIntegerField(default=0)), ('reason', models.TextField(blank=True)), ('created_at', models.DateTimeField(auto_now_add=True)),
            ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_payment_pauses', to=settings.AUTH_USER_MODEL)), ('student', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payment_pauses', to='itadis_app.student')),
        ], options={'db_table': 'payment_schedule_pauses'}),
        migrations.CreateModel(name='PaymentAllocation', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('amount', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))])), ('created_at', models.DateTimeField(auto_now_add=True)),
            ('schedule_item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='allocations', to='itadis_app.paymentscheduleitem')), ('transaction', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payment_allocations', to='itadis_app.transaction')),
        ], options={'db_table': 'payment_allocations'}),
        migrations.CreateModel(name='PaymentNotification', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('kind', models.CharField(choices=[('upcoming', 'Скоро платёж'), ('overdue', 'Просрочен платёж')], max_length=12)), ('event_key', models.CharField(max_length=200, unique=True)), ('message', models.TextField()), ('read_at', models.DateTimeField(blank=True, null=True)), ('resolved_at', models.DateTimeField(blank=True, null=True)), ('created_at', models.DateTimeField(auto_now_add=True)),
            ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payment_notifications', to=settings.AUTH_USER_MODEL)), ('schedule_item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='notifications', to='itadis_app.paymentscheduleitem')), ('student', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payment_notifications', to='itadis_app.student')),
        ], options={'db_table': 'payment_notifications'}),
        migrations.AddConstraint(model_name='paymentallocation', constraint=models.UniqueConstraint(fields=('transaction', 'schedule_item'), name='unique_transaction_schedule_allocation')),
    ]
