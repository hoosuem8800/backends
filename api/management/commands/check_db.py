from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError
import os

class Command(BaseCommand):
    help = 'Checks database connectivity'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Checking database connections...'))
        
        # Print environment variables for debugging
        self.stdout.write("Environment variables:")
        self.stdout.write(f"DATABASE_URL: {os.environ.get('DATABASE_URL', 'Not set')}")
        
        # Check each database connection
        for alias in connections:
            try:
                connection = connections[alias]
                connection.ensure_connection()
                if connection.is_usable():
                    self.stdout.write(self.style.SUCCESS(f'Database "{alias}" connection successful!'))
                else:
                    self.stdout.write(self.style.ERROR(f'Database "{alias}" connection failed.'))
            except OperationalError as e:
                self.stdout.write(self.style.ERROR(f'Database "{alias}" connection error: {str(e)}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Unexpected error with database "{alias}": {str(e)}')) 