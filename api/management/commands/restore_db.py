from django.core.management.base import BaseCommand
from django.conf import settings
import os
import subprocess
import logging

logger = logging.getLogger('api')

class Command(BaseCommand):
    help = 'Restores the database from a backup file'

    def add_arguments(self, parser):
        parser.add_argument(
            'backup_file',
            type=str,
            help='Path to the backup file to restore from'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force restore without confirmation'
        )

    def handle(self, *args, **options):
        backup_file = options['backup_file']
        force = options['force']

        # Check if backup file exists
        if not os.path.exists(backup_file):
            self.stderr.write(f"Backup file not found: {backup_file}")
            return

        # Get database settings
        db_settings = settings.DATABASES['default']
        db_name = db_settings['NAME']
        db_user = db_settings['USER']
        db_password = db_settings['PASSWORD']
        db_host = db_settings['HOST']
        db_port = db_settings['PORT']

        # Confirm restore
        if not force:
            confirm = input(
                f"Are you sure you want to restore the database from {backup_file}? "
                "This will overwrite all current data. (y/n): "
            )
            if confirm.lower() != 'y':
                self.stdout.write("Restore cancelled")
                return

        # Build restore command
        cmd = [
            'pg_restore',
            '-U', db_user,
            '-h', db_host,
            '-p', db_port,
            '-d', db_name,
            '--clean',
            '--if-exists',
            backup_file
        ]

        # Set PGPASSWORD environment variable
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password

        try:
            # Execute restore command
            subprocess.run(cmd, env=env, check=True)
            self.stdout.write("Database restored successfully")
        except subprocess.CalledProcessError as e:
            self.stderr.write(f"Error restoring database: {str(e)}")
            logger.error(f"Database restore failed: {str(e)}")
        except Exception as e:
            self.stderr.write(f"Unexpected error: {str(e)}")
            logger.error(f"Unexpected error during restore: {str(e)}") 