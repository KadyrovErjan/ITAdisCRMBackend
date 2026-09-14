from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('itadis_app', '0002_add_admin_role')]

    operations = [
        migrations.RunSQL("UPDATE users SET role = 'director' WHERE role = 'admin'", migrations.RunSQL.noop),
        migrations.AlterField(
            model_name='user', name='role',
            field=models.CharField(
                choices=[('cashier', 'Кассир'), ('accountant', 'Бухгалтер'), ('director', 'Директор')],
                max_length=20, verbose_name='Роль',
            ),
        ),
    ]
