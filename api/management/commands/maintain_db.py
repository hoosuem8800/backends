from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from api.models import Scan, Appointment, Payment
from rest_framework.authtoken.models import Token
import logging

logger = logging.getLogger('api')

class Command(BaseCommand):
    help = 'Performs database maintenance tasks including cleanup of old data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to keep data (default: 30)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        cutoff_date = timezone.now() - timedelta(days=days)

        self.stdout.write(f"Starting database maintenance (cutoff date: {cutoff_date})")

        # Clean up old scans
        old_scans = Scan.objects.filter(upload_date__lt=cutoff_date)
        if dry_run:
            self.stdout.write(f"Would delete {old_scans.count()} old scans")
        else:
            count = old_scans.count()
            old_scans.delete()
            self.stdout.write(f"Deleted {count} old scans")

        # Clean up completed appointments
        old_appointments = Appointment.objects.filter(
            date_time__lt=cutoff_date,
            status='completed'
        )
        if dry_run:
            self.stdout.write(f"Would delete {old_appointments.count()} completed appointments")
        else:
            count = old_appointments.count()
            old_appointments.delete()
            self.stdout.write(f"Deleted {count} completed appointments")

        # Clean up old payments
        old_payments = Payment.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['completed', 'failed', 'refunded']
        )
        if dry_run:
            self.stdout.write(f"Would delete {old_payments.count()} old payments")
        else:
            count = old_payments.count()
            old_payments.delete()
            self.stdout.write(f"Deleted {count} old payments")

        # Clean up expired tokens
        expired_tokens = Token.objects.filter(
            created__lt=timezone.now() - timedelta(hours=24)
        )
        if dry_run:
            self.stdout.write(f"Would delete {expired_tokens.count()} expired tokens")
        else:
            count = expired_tokens.count()
            expired_tokens.delete()
            self.stdout.write(f"Deleted {count} expired tokens")

        if dry_run:
            self.stdout.write("Dry run completed - no changes were made")
        else:
            self.stdout.write("Database maintenance completed successfully") 