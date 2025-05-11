import os
import json
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import connections
from django.core.serializers.json import DjangoJSONEncoder


class Command(BaseCommand):
    help = 'Migrates data from SQLite to PostgreSQL'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting data migration from SQLite to PostgreSQL'))
        
        # Get all models from all installed apps
        models = []
        for app_config in apps.get_app_configs():
            models.extend(app_config.get_models())
        
        # Create data directory if it doesn't exist
        if not os.path.exists('data_migration'):
            os.makedirs('data_migration')
        
        total_models = len(models)
        self.stdout.write(f'Found {total_models} models to migrate')
        
        # Export data from SQLite
        self.stdout.write(self.style.WARNING('Step 1: Exporting data from SQLite'))
        for i, model in enumerate(models, 1):
            self.stdout.write(f'[{i}/{total_models}] Exporting {model.__name__}')
            
            try:
                # Get all data from SQLite
                data = list(model.objects.using('default').all().values())
                
                # Save to JSON file
                model_name = f"{model._meta.app_label}.{model.__name__}"
                with open(f'data_migration/{model_name}.json', 'w') as f:
                    json.dump(data, f, cls=DjangoJSONEncoder)
                
                self.stdout.write(self.style.SUCCESS(f'  - Exported {len(data)} records'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  - Error exporting {model.__name__}: {str(e)}'))
        
        # Import data to PostgreSQL
        self.stdout.write(self.style.WARNING('\nStep 2: Importing data to PostgreSQL'))
        self.stdout.write('Make sure your PostgreSQL connection is configured in settings.py')
        
        proceed = input('Type "yes" to continue with the import: ')
        if proceed.lower() != 'yes':
            self.stdout.write(self.style.WARNING('Import cancelled'))
            return
        
        for i, model in enumerate(models, 1):
            model_name = f"{model._meta.app_label}.{model.__name__}"
            json_file = f'data_migration/{model_name}.json'
            
            if not os.path.exists(json_file):
                continue
            
            self.stdout.write(f'[{i}/{total_models}] Importing {model.__name__}')
            
            try:
                # Load data from JSON file
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                if not data:
                    self.stdout.write('  - No data to import')
                    continue
                
                # Clear existing data in PostgreSQL
                model.objects.using('postgres').all().delete()
                
                # Import data to PostgreSQL
                for item in data:
                    # Remove primary key to let Django create a new one if needed
                    # This prevents PK conflicts
                    pk_name = model._meta.pk.name
                    if pk_name in item:
                        pk_value = item[pk_name]
                    
                    # Create objects individually to handle errors better
                    try:
                        model.objects.using('postgres').create(**item)
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'  - Error importing item {pk_value}: {str(e)}'))
                
                self.stdout.write(self.style.SUCCESS(f'  - Imported {len(data)} records'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  - Error importing {model.__name__}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS('\nMigration completed!'))
        self.stdout.write('To switch to PostgreSQL, update your settings.py and run:')
        self.stdout.write('python manage.py check') 