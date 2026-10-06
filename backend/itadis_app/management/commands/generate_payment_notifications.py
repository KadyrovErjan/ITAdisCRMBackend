from django.core.management.base import BaseCommand
from itadis_app.services.payment_plans import generate_notifications


class Command(BaseCommand):
    help = 'Create idempotent upcoming/overdue payment notifications.'

    def handle(self, *args, **options):
        created = generate_notifications()
        self.stdout.write(self.style.SUCCESS(f'Created {created} payment notifications.'))
