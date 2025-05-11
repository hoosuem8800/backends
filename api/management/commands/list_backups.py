from django.core.management.base import BaseCommand
import os
import logging
from datetime import datetime
from django.conf import settings

logger = logging.getLogger('api')

class Command(BaseCommand):
    help = 'Lists available database backups'

    def add_arguments(self, parser):
        parser.add_argument(
            '--backup-dir',
            type=str,
            default='backups',
            help='Directory containing backups (default: backups)'
        )
        parser.add_argument(
            '--sort-by',
            type=str,
            choices=['name', 'date', 'size'],
            default='date',
            help='Sort backups by name, date, or size (default: date)'
        )
        parser.add_argument(
            '--reverse',
            action='store_true',
            help='Reverse the sort order'
        )

    def handle(self, *args, **options):
        backup_dir = options['backup_dir']
        sort_by = options['sort_by']
        reverse = options['reverse']

        # Check if backup directory exists
        if not os.path.exists(backup_dir):
            self.stderr.write(f"Backup directory not found: {backup_dir}")
            return

        # Get list of backup files
        backup_files = []
        for filename in os.listdir(backup_dir):
            if filename.endswith(('.sql', '.sql.gz')):
                file_path = os.path.join(backup_dir, filename)
                file_stat = os.stat(file_path)
                backup_files.append({
                    'name': filename,
                    'path': file_path,
                    'size': file_stat.st_size,
                    'modified': datetime.fromtimestamp(file_stat.st_mtime)
                })

        if not backup_files:
            self.stdout.write("No backups found")
            return

        # Sort backups
        if sort_by == 'name':
            backup_files.sort(key=lambda x: x['name'], reverse=reverse)
        elif sort_by == 'date':
            backup_files.sort(key=lambda x: x['modified'], reverse=reverse)
        elif sort_by == 'size':
            backup_files.sort(key=lambda x: x['size'], reverse=reverse)

        # Display backups
        self.stdout.write("\nAvailable Backups:")
        self.stdout.write("-" * 80)
        self.stdout.write(f"{'Name':<40} {'Size':>10} {'Modified':<20}")
        self.stdout.write("-" * 80)

        for backup in backup_files:
            size_mb = backup['size'] / (1024 * 1024)
            modified_str = backup['modified'].strftime('%Y-%m-%d %H:%M:%S')
            self.stdout.write(f"{backup['name']:<40} {size_mb:>10.2f} MB {modified_str:<20}")

        self.stdout.write("-" * 80)
        self.stdout.write(f"Total backups: {len(backup_files)}")
        total_size = sum(b['size'] for b in backup_files) / (1024 * 1024)
        self.stdout.write(f"Total size: {total_size:.2f} MB") 