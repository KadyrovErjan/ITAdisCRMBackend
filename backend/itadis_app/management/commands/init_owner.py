"""
Management команда для очистки базы данных и создания владельца сайта (директора)
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from itadis_app.models import (
    User, Student, Group, Transaction, 
    Balance, Collection, Expense, AuditLog
)


class Command(BaseCommand):
    help = 'Очищает все данные и создает владельца сайта (директора)'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Начинаем очистку базы данных...'))
        
        try:
            with transaction.atomic():
                # Очистка всех данных
                self.stdout.write('Удаление транзакций...')
                Transaction.objects.all().delete()
                
                self.stdout.write('Удаление расходов...')
                Expense.objects.all().delete()
                
                self.stdout.write('Удаление сборов...')
                Collection.objects.all().delete()
                
                self.stdout.write('Удаление студентов...')
                Student.objects.all().delete()
                
                self.stdout.write('Удаление групп...')
                Group.objects.all().delete()
                
                self.stdout.write('Удаление балансов...')
                Balance.objects.all().delete()
                
                self.stdout.write('Удаление журнала аудита...')
                AuditLog.objects.all().delete()
                
                self.stdout.write('Удаление пользователей...')
                User.objects.all().delete()
                
                self.stdout.write(self.style.SUCCESS('✓ Все данные успешно удалены'))
                
                # Создание владельца сайта (директора)
                self.stdout.write('\nСоздание владельца сайта...')
                
                director = User.objects.create_superuser(
                    login='adambek',
                    full_name='Адамбек',
                    role='director',
                    password='adambek123_',
                    is_active=True,
                    is_staff=True,
                    is_superuser=True
                )
                
                self.stdout.write(self.style.SUCCESS(f'✓ Владелец сайта создан: {director.login}'))
                
                # Проверка - у директора не должно быть баланса
                balance_check = Balance.objects.filter(user=director).first()
                if balance_check:
                    balance_check.delete()
                    self.stdout.write('  ℹ Баланс директора удален (директору не нужен баланс)')
                
                self.stdout.write(self.style.SUCCESS('\n' + '='*70))
                self.stdout.write(self.style.SUCCESS('✓ База данных успешно инициализирована!'))
                self.stdout.write(self.style.SUCCESS('='*70))
                
                # Вывод информации для входа
                self.stdout.write(self.style.WARNING('\n📋 ДАННЫЕ ДЛЯ ВХОДА (ВЛАДЕЛЕЦ САЙТА):'))
                self.stdout.write('')
                self.stdout.write(f'  Роль:     Директор (Владелец)')
                self.stdout.write(f'  ФИО:      {director.full_name}')
                self.stdout.write(f'  Login:    {director.login}')
                self.stdout.write(f'  Password: adambek123_')
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('='*70))
                self.stdout.write(self.style.SUCCESS('Теперь директор может войти и добавить работников! 🎉'))
                self.stdout.write(self.style.SUCCESS('='*70))
                self.stdout.write('')
                self.stdout.write(self.style.WARNING('📌 Примечания:'))
                self.stdout.write('  • Директор имеет полный доступ к системе')
                self.stdout.write('  • Может добавлять работников (кассиров и бухгалтеров)')
                self.stdout.write('  • Имеет доступ к админ-панели Django: http://localhost:8000/admin')
                self.stdout.write('  • Имеет доступ к аналитике и всем финансовым данным')
                self.stdout.write('')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Ошибка: {str(e)}'))
            raise
