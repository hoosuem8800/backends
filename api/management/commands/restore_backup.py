from django.core.management.base import BaseCommand
import os
import logging
import subprocess
import psycopg2
from datetime import datetime
from django.conf import settings

logger = logging.getLogger('api')

class Command(BaseCommand):
    help = 'Restores a database from a backup'

    def add_arguments(self, parser):
        parser.add_argument(
            'backup_file',
            type=str,
            help='Path to the backup file to restore'
        )
        parser.add_argument(
            '--backup-dir',
            type=str,
            default='backups',
            help='Directory containing backups (default: backups)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force restore without confirmation'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be restored without actually restoring'
        )

    def handle(self, *args, **options):
        backup_file = options['backup_file']
        backup_dir = options['backup_dir']
        force = options['force']
        dry_run = options['dry_run']

        # Get database configuration
        db_config = settings.DATABASES['default']
        db_name = db_config['NAME']
        db_user = db_config['USER']
        db_password = db_config['PASSWORD']
        db_host = db_config['HOST']
        db_port = db_config['PORT']

        # Construct full backup path
        if not os.path.isabs(backup_file):
            backup_path = os.path.join(backup_dir, backup_file)
        else:
            backup_path = backup_file

        # Check if backup file exists
        if not os.path.exists(backup_path):
            self.stderr.write(f"Backup file not found: {backup_path}")
            return

        # Display restore information
        self.stdout.write("\nRestore Information:")
        self.stdout.write(f"Database: {db_name}")
        self.stdout.write(f"Host: {db_host}")
        self.stdout.write(f"Port: {db_port}")
        self.stdout.write(f"User: {db_user}")
        self.stdout.write(f"Backup file: {backup_path}")
        self.stdout.write(f"Backup size: {os.path.getsize(backup_path) / (1024 * 1024):.2f} MB")

        if dry_run:
            self.stdout.write("\nThis was a dry run. No restore was performed.")
            return

        # Confirm restore
        if not force:
            confirm = input("\nWARNING: This will overwrite the current database. Continue? [y/N]: ")
            if confirm.lower() != 'y':
                self.stdout.write("Restore cancelled")
                return

        # Test database connection
        try:
            conn = psycopg2.connect(
                dbname='postgres',  # Connect to default database
                user=db_user,
                password=db_password,
                host=db_host,
                port=db_port
            )
            conn.close()
        except Exception as e:
            self.stderr.write(f"Error connecting to database: {str(e)}")
            return

        # Create restore command
        try:
            self.stdout.write("\nRestoring database...")
            
            # Drop existing connections
            drop_connections_cmd = [
                'psql',
                '-h', db_host,
                '-p', str(db_port),
                '-U', db_user,
                '-d', 'postgres',
                '-c', f"SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '{db_name}' AND pid <> pg_backend_pid();"
            ]

            # Drop and recreate database
            drop_db_cmd = [
                'psql',
                '-h', db_host,
                '-p', str(db_port),
                '-U', db_user,
                '-d', 'postgres',
                '-c', f"DROP DATABASE IF EXISTS {db_name};"
            ]

            create_db_cmd = [
                'psql',
                '-h', db_host,
                '-p', str(db_port),
                '-U', db_user,
                '-d', 'postgres',
                '-c', f"CREATE DATABASE {db_name};"
            ]

            # Restore command
            if backup_path.endswith('.gz'):
                restore_cmd = [
                    'gunzip',
                    '-c',
                    backup_path,
                    '|',
                    'psql',
                    '-h', db_host,
                    '-p', str(db_port),
                    '-U', db_user,
                    '-d', db_name
                ]
            else:
                restore_cmd = [
                    'psql',
                    '-h', db_host,
                    '-p', str(db_port),
                    '-U', db_user,
                    '-d', db_name,
                    '-f', backup_path
                ]

            # Execute commands
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password

            for cmd in [drop_connections_cmd, drop_db_cmd, create_db_cmd]:
                process = subprocess.Popen(
                    ' '.join(cmd),
                    shell=True,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = process.communicate()
                if process.returncode != 0:
                    self.stderr.write(f"Error preparing restore: {stderr.decode()}")
                    return

            process = subprocess.Popen(
                ' '.join(restore_cmd),
                shell=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                self.stderr.write(f"Error during restore: {stderr.decode()}")
                return

            self.stdout.write("\nDatabase restored successfully")
            logger.info(f"Database restored from backup: {backup_path}")

        except Exception as e:
            self.stderr.write(f"Error during restore: {str(e)}")
            logger.error(f"Error restoring database: {str(e)}")
            return 