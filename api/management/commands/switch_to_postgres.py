from django.core.management.base import BaseCommand
import os


class Command(BaseCommand):
    help = 'Configure settings to use PostgreSQL as the default database'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Switching default database to PostgreSQL'))
        
        # Test PostgreSQL connection
        from django.db import connections
        try:
            connection = connections['postgres']
            connection.ensure_connection()
            if connection.is_usable():
                self.stdout.write(self.style.SUCCESS('PostgreSQL connection successful!'))
            else:
                self.stdout.write(self.style.ERROR('PostgreSQL connection failed. Check your settings.'))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'PostgreSQL connection error: {str(e)}'))
            self.stdout.write('Make sure PostgreSQL is running and your credentials are correct.')
            return
        
        self.stdout.write('\nTo complete the switch to PostgreSQL:')
        self.stdout.write('1. Create a file named .env in your project root with these settings:')
        self.stdout.write(self.style.WARNING('''
# PostgreSQL settings
POSTGRES_DB=your_database_name
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
        '''))
        
        self.stdout.write('2. Run the following command to apply migrations to PostgreSQL:')
        self.stdout.write(self.style.WARNING('python manage.py migrate --database=postgres'))
        
        self.stdout.write('3. Run the migration command to transfer your data:')
        self.stdout.write(self.style.WARNING('python manage.py migrate_to_postgres'))
        
        self.stdout.write('4. Edit settings.py to use PostgreSQL as default:')
        self.stdout.write(self.style.WARNING('''
# Option 1: Swap the default database
DATABASES = {
    'default': DATABASES['postgres'],
    'sqlite': DATABASES['default']
}

# Option 2: Use DATABASE_URL environment variable
# Add to your .env file:
# DATABASE_URL=postgres://username:password@localhost:5432/database_name
        '''))
        
        self.stdout.write(self.style.SUCCESS('\nOnce configured, your Django app will use PostgreSQL!')) 