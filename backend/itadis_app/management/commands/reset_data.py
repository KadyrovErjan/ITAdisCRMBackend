"""
Management команда для очистки базы данных и создания новых пользователей
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from itadis_app.models import (
    User, Student, Group, Transaction, 
    Balance, Collection, Expense, AuditLog
)


class Command(BaseCommand):
    help = 'Очищает все данные и создает новых пользователей'

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
                
                # Создание новых пользователей
                self.stdout.write('\nСоздание новых пользователей...')
                
                # 1. Директор: Адамбек
                director = User.objects.create_user(
                    login='adambek',
                    full_name='Адамбек',
                    role='director',
                    password='adambek123_',
                    is_active=True
                )
                self.stdout.write(self.style.SUCCESS(f'✓ Директор создан: {director.login} (Адамбек)'))
                
                # 2. Кассир 1: Акмоор
                cashier1 = User.objects.create_user(
                    login='akmoor',
                    full_name='Акмоор',
                    role='cashier',
                    password='akmoor123_',
                    is_active=True
                )
                self.stdout.write(self.style.SUCCESS(f'✓ Кассир 1 создан: {cashier1.login} (Акмоор)'))
                
                # 3. Кассир 2: Айдат
                cashier2 = User.objects.create_user(
                    login='aidat',
                    full_name='Айдат',
                    role='cashier',
                    password='aidat123_',
                    is_active=True
                )
                self.stdout.write(self.style.SUCCESS(f'✓ Кассир 2 создан: {cashier2.login} (Айдат)'))
                
                # 4. Бухгалтер: Бугалтер
                accountant = User.objects.create_user(
                    login='bugalter',
                    full_name='Бугалтер',
                    role='accountant',
                    password='bugalter123_',
                    is_active=True
                )
                self.stdout.write(self.style.SUCCESS(f'✓ Бухгалтер создан: {accountant.login} (Бугалтер)'))
                
                # Проверка балансов (они должны создаться автоматически через сигнал)
                self.stdout.write('\nПроверка балансов...')
                for user in [director, cashier1, cashier2, accountant]:
                    balance = Balance.objects.filter(user=user).first()
                    if balance:
                        self.stdout.write(f'  ✓ Баланс найден для {user.full_name}: {balance.amount} ₸')
                    else:
                        # Если баланс не создался автоматически, создаем вручную
                        Balance.objects.create(user=user, amount=0)
                        self.stdout.write(f'  ✓ Баланс создан для {user.full_name}')
                
                self.stdout.write(self.style.SUCCESS('\n' + '='*60))
                self.stdout.write(self.style.SUCCESS('✓ Все операции выполнены успешно!'))
                self.stdout.write(self.style.SUCCESS('='*60))
                
                # Вывод информации для входа
                self.stdout.write(self.style.WARNING('\n📋 ДАННЫЕ ДЛЯ ВХОДА:'))
                self.stdout.write('')
                
                users_info = [
                    ('Директор', 'adambek', 'adambek123_', 'Адамбек'),
                    ('Кассир 1', 'akmoor', 'akmoor123_', 'Акмоор'),
                    ('Кассир 2', 'aidat', 'aidat123_', 'Айдат'),
                    ('Бухгалтер', 'bugalter', 'bugalter123_', 'Бугалтер'),
                ]
                
                for role, login, password, name in users_info:
                    self.stdout.write(f'  {role}: {name}')
                    self.stdout.write(f'    Login:    {login}')
                    self.stdout.write(f'    Password: {password}')
                    self.stdout.write('')
                
                self.stdout.write(self.style.SUCCESS('='*60))
                self.stdout.write(self.style.SUCCESS('База данных готова к использованию! 🎉'))
                self.stdout.write(self.style.SUCCESS('='*60))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Ошибка: {str(e)}'))
            raise
