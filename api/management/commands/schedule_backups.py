from django.core.management.base import BaseCommand
from django.conf import settings
import os
import subprocess
import logging
from datetime import datetime, timedelta
import schedule
import time
import threading

logger = logging.getLogger('api')

class Command(BaseCommand):
    help = 'Schedules automatic database backups'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=24,
            help='Backup interval in hours (default: 24)'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default='backups',
            help='Directory to store backups (default: backups)'
        )
        parser.add_argument(
            '--keep',
            type=int,
            default=7,
            help='Number of backups to keep (default: 7)'
        )

    def handle(self, *args, **options):
        interval = options['interval']
        output_dir = options['output_dir']
        keep_backups = options['keep']

        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        def backup_job():
            try:
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
                    '-F', 'c',
                    '-f', backup_file,
                    db_name
                ]

                # Set PGPASSWORD environment variable
                env = os.environ.copy()
                env['PGPASSWORD'] = db_password

                # Execute backup command
                subprocess.run(cmd, env=env, check=True)
                logger.info(f"Automatic backup created: {backup_file}")

                # Clean up old backups
                if os.path.exists(output_dir):
                    backups = sorted(
                        [f for f in os.listdir(output_dir) if f.startswith('backup_')],
                        reverse=True
                    )
                    for old_backup in backups[keep_backups:]:
                        os.remove(os.path.join(output_dir, old_backup))
                        logger.info(f"Removed old backup: {old_backup}")

            except Exception as e:
                logger.error(f"Error in automatic backup: {str(e)}")

        def run_schedule():
            while True:
                schedule.run_pending()
                time.sleep(60)

        # Schedule the backup job
        schedule.every(interval).hours.do(backup_job)

        # Run the first backup immediately
        backup_job()

        # Start the scheduler in a separate thread
        scheduler_thread = threading.Thread(target=run_schedule)
        scheduler_thread.daemon = True
        scheduler_thread.start()

        self.stdout.write(
            f"Automatic backups scheduled every {interval} hours. "
            f"Keeping last {keep_backups} backups in {output_dir}"
        )
        self.stdout.write("Press Ctrl+C to stop")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write("\nStopping backup scheduler...") 