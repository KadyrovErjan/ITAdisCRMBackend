from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('itadis_app', '0001_initial')]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('cashier', 'Кассир'),
                    ('accountant', 'Бухгалтер'),
                    ('director', 'Директор'),
                    ('admin', 'Администратор'),
                ],
                max_length=20,
                verbose_name='Роль',
            ),
        ),
    ]
