from django.core.management.base import BaseCommand
import os
import glob
import logging
from datetime import datetime, timedelta
import shutil

logger = logging.getLogger('api')

class Command(BaseCommand):
    help = 'Cleans up old database backups'

    def add_arguments(self, parser):
        parser.add_argument(
            '--backup-dir',
            type=str,
            default='backups',
            help='Directory containing backups (default: backups)'
        )
        parser.add_argument(
            '--keep-days',
            type=int,
            default=30,
            help='Number of days to keep backups (default: 30)'
        )
        parser.add_argument(
            '--keep-count',
            type=int,
            default=10,
            help='Minimum number of backups to keep (default: 10)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force cleanup without confirmation'
        )

    def handle(self, *args, **options):
        backup_dir = options['backup_dir']
        keep_days = options['keep_days']
        keep_count = options['keep_count']
        dry_run = options['dry_run']
        force = options['force']

        # Check if backup directory exists
        if not os.path.exists(backup_dir):
            self.stderr.write(f"Backup directory not found: {backup_dir}")
            return

        # Get list of backup files
        backup_files = glob.glob(os.path.join(backup_dir, 'backup_*.sql*'))
        if not backup_files:
            self.stdout.write("No backups found")
            return

        # Get file information
        backups = []
        for backup_file in backup_files:
            file_info = {
                'path': backup_file,
                'name': os.path.basename(backup_file),
                'size': os.path.getsize(backup_file),
                'modified': datetime.fromtimestamp(os.path.getmtime(backup_file))
            }
            backups.append(file_info)

        # Sort backups by modification date (newest first)
        backups.sort(key=lambda x: x['modified'], reverse=True)

        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=keep_days)

        # Identify backups to delete
        to_delete = []
        for i, backup in enumerate(backups):
            if backup['modified'] < cutoff_date and i >= keep_count:
                to_delete.append(backup)

        if not to_delete:
            self.stdout.write("No backups to clean up")
            return

        # Display backups to be deleted
        self.stdout.write("\nBackups to be deleted:")
        self.stdout.write("-" * 100)
        self.stdout.write(
            f"{'Filename':<40} {'Size':<15} {'Modified':<30}"
        )
        self.stdout.write("-" * 100)

        total_size = 0
        for backup in to_delete:
            size_mb = backup['size'] / (1024 * 1024)
            total_size += backup['size']
            self.stdout.write(
                f"{backup['name']:<40} "
                f"{size_mb:.2f} MB{'':<5} "
                f"{backup['modified'].strftime('%Y-%m-%d %H:%M:%S'):<30}"
            )

        self.stdout.write("-" * 100)
        self.stdout.write(f"Total backups to delete: {len(to_delete)}")
        self.stdout.write(f"Total space to free: {total_size / (1024 * 1024):.2f} MB")

        if dry_run:
            self.stdout.write("\nThis was a dry run. No files were deleted.")
            return

        # Confirm deletion
        if not force:
            self.stdout.write("\nDo you want to delete these backups? [y/N]")
            if input().lower() != 'y':
                self.stdout.write("Cleanup cancelled")
                return

        # Delete backups
        deleted_count = 0
        deleted_size = 0
        for backup in to_delete:
            try:
                os.remove(backup['path'])
                deleted_count += 1
                deleted_size += backup['size']
                logger.info(f"Deleted backup: {backup['path']}")
            except Exception as e:
                self.stderr.write(f"Error deleting {backup['path']}: {str(e)}")
                logger.error(f"Error deleting backup {backup['path']}: {str(e)}")

        self.stdout.write(f"\nSuccessfully deleted {deleted_count} backups")
        self.stdout.write(f"Freed {deleted_size / (1024 * 1024):.2f} MB of space") 