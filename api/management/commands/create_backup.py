from django.core.management.base import BaseCommand
import os
import logging
import subprocess
import psycopg2
from datetime import datetime
from django.conf import settings

logger = logging.getLogger('api')

class Command(BaseCommand):
    help = 'Creates a database backup'

    def add_arguments(self, parser):
        parser.add_argument(
            '--backup-dir',
            type=str,
            default='backups',
            help='Directory to store backups (default: backups)'
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress the backup using gzip'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be backed up without actually creating a backup'
        )

    def handle(self, *args, **options):
        backup_dir = options['backup_dir']
        compress = options['compress']
        dry_run = options['dry_run']

        # Get database configuration
        db_config = settings.DATABASES['default']
        db_name = db_config['NAME']
        db_user = db_config['USER']
        db_password = db_config['PASSWORD']
        db_host = db_config['HOST']
        db_port = db_config['PORT']

        # Create backup directory if it doesn't exist
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # Generate backup filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"backup_{db_name}_{timestamp}.sql"
        if compress:
            backup_filename += '.gz'
        backup_path = os.path.join(backup_dir, backup_filename)

        # Display backup information
        self.stdout.write("\nBackup Information:")
        self.stdout.write(f"Database: {db_name}")
        self.stdout.write(f"Host: {db_host}")
        self.stdout.write(f"Port: {db_port}")
        self.stdout.write(f"User: {db_user}")
        self.stdout.write(f"Backup file: {backup_path}")
        self.stdout.write(f"Compression: {'Enabled' if compress else 'Disabled'}")

        if dry_run:
            self.stdout.write("\nThis was a dry run. No backup was created.")
            return

        # Test database connection
        try:
            conn = psycopg2.connect(
                dbname=db_name,
                user=db_user,
                password=db_password,
                host=db_host,
                port=db_port
            )
            conn.close()
        except Exception as e:
            self.stderr.write(f"Error connecting to database: {str(e)}")
            return

        # Create backup command
        try:
            self.stdout.write("\nCreating backup...")
            
            if compress:
                backup_cmd = [
                    'pg_dump',
                    '-h', db_host,
                    '-p', str(db_port),
                    '-U', db_user,
                    '-d', db_name,
                    '|',
                    'gzip',
                    '>',
                    backup_path
                ]
            else:
                backup_cmd = [
                    'pg_dump',
                    '-h', db_host,
                    '-p', str(db_port),
                    '-U', db_user,
                    '-d', db_name,
                    '-f', backup_path
                ]

            # Execute backup command
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password

            process = subprocess.Popen(
                ' '.join(backup_cmd),
                shell=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                self.stderr.write(f"Error creating backup: {stderr.decode()}")
                return

            # Verify backup file was created
            if not os.path.exists(backup_path):
                self.stderr.write("Backup file was not created")
                return

            backup_size = os.path.getsize(backup_path) / (1024 * 1024)
            self.stdout.write(f"\nBackup created successfully")
            self.stdout.write(f"Backup size: {backup_size:.2f} MB")
            logger.info(f"Database backup created: {backup_path}")

        except Exception as e:
            self.stderr.write(f"Error during backup: {str(e)}")
            logger.error(f"Error creating database backup: {str(e)}")
            return 