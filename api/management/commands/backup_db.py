from django.core.management.base import BaseCommand
from django.conf import settings
from datetime import datetime
import os
import subprocess
import logging

logger = logging.getLogger('api')

class Command(BaseCommand):
    help = 'Creates a backup of the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='backups',
            help='Directory to store backups (default: backups)'
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress the backup file'
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']
        compress = options['compress']

        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(output_dir, f'backup_{timestamp}.sql')

        # Get database settings
        db_settings = settings.DATABASES['default']
        db_name = db_settings['NAME']
        db_user = db_settings['USER']
        db_password = db_settings['PASSWORD']
        db_host = db_settings['HOST']
        db_port = db_settings['PORT']

        # Build pg_dump command
        cmd = [
            'pg_dump',
            '-U', db_user,
            '-h', db_host,
            '-p', db_port,
            '-F', 'c' if compress else 'p',
            '-f', backup_file,
            db_name
        ]

        # Set PGPASSWORD environment variable
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password

        try:
            # Execute backup command
            subprocess.run(cmd, env=env, check=True)
            self.stdout.write(f"Database backup created successfully: {backup_file}")
            
            # Clean up old backups (keep last 5)
            if os.path.exists(output_dir):
                backups = sorted(
                    [f for f in os.listdir(output_dir) if f.startswith('backup_')],
                    reverse=True
                )
                for old_backup in backups[5:]:
                    os.remove(os.path.join(output_dir, old_backup))
                    self.stdout.write(f"Removed old backup: {old_backup}")

        except subprocess.CalledProcessError as e:
            self.stderr.write(f"Error creating database backup: {str(e)}")
            logger.error(f"Database backup failed: {str(e)}")
        except Exception as e:
            self.stderr.write(f"Unexpected error: {str(e)}")
            logger.error(f"Unexpected error during backup: {str(e)}") 