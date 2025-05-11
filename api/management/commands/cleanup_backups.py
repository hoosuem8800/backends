from django.core.management.base import BaseCommand
import os
import logging
from datetime import datetime, timedelta
import glob

logger = logging.getLogger('api')

class Command(BaseCommand):
    help = 'Deletes old database backups'

    def add_arguments(self, parser):
        parser.add_argument(
            '--backup-dir',
            type=str,
            default='backups',
            help='Directory containing backups (default: backups)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to keep backups (default: 30)'
        )
        parser.add_argument(
            '--keep',
            type=int,
            default=5,
            help='Minimum number of backups to keep (default: 5)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force deletion without confirmation'
        )

    def handle(self, *args, **options):
        backup_dir = options['backup_dir']
        days = options['days']
        keep = options['keep']
        force = options['force']

        # Check if backup directory exists
        if not os.path.exists(backup_dir):
            self.stderr.write(f"Backup directory not found: {backup_dir}")
            return

        # Get list of backup files
        backup_files = glob.glob(os.path.join(backup_dir, 'backup_*.sql'))
        if not backup_files:
            self.stdout.write("No backups found to clean up")
            return

        # Sort backups by modification time (oldest first)
        backup_files.sort(key=os.path.getmtime)

        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Find backups to delete
        backups_to_delete = []
        for backup_file in backup_files:
            file_time = datetime.fromtimestamp(os.path.getmtime(backup_file))
            if file_time < cutoff_date:
                backups_to_delete.append(backup_file)

        # Ensure we keep at least the specified number of backups
        if len(backup_files) - len(backups_to_delete) < keep:
            backups_to_delete = backup_files[:-keep]

        if not backups_to_delete:
            self.stdout.write("No backups to delete")
            return

        # Display backups to be deleted
        self.stdout.write("\nBackups to be deleted:")
        self.stdout.write("-" * 80)
        for backup in backups_to_delete:
            file_time = datetime.fromtimestamp(os.path.getmtime(backup))
            self.stdout.write(
                f"{os.path.basename(backup):<30} "
                f"Created: {file_time.strftime('%Y-%m-%d %H:%M:%S'):<30}"
            )
        self.stdout.write("-" * 80)

        if not force:
            self.stdout.write(
                f"\nThis will delete {len(backups_to_delete)} backup(s). "
                "Do you want to continue? [y/N]"
            )
            if input().lower() != 'y':
                self.stdout.write("Cleanup cancelled")
                return

        # Delete backups
        deleted_count = 0
        for backup in backups_to_delete:
            try:
                os.remove(backup)
                deleted_count += 1
                logger.info(f"Deleted backup: {backup}")
            except Exception as e:
                self.stderr.write(f"Error deleting {backup}: {str(e)}")
                logger.error(f"Error deleting backup {backup}: {str(e)}")

        self.stdout.write(f"\nDeleted {deleted_count} backup(s)") 