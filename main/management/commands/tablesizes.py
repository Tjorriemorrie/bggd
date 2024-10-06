import sys

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Get estimated sizes of tables starting with 'main' by calculating instance sizes"

    def convert_bytes(self, size_in_bytes):
        """Convert bytes to a more readable format (MB or GB)."""
        if size_in_bytes >= 1_073_741_824:  # 1 GB
            return f'{size_in_bytes / 1_073_741_824:.2f} GB'
        elif size_in_bytes >= 1_048_576:  # 1 MB
            return f'{size_in_bytes / 1_048_576:.2f} MB'
        else:
            return f'{size_in_bytes} bytes'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Fetch all models in the current app
            app_models = apps.get_models()
            for model in app_models:
                # Check if the model's table name starts with 'main'
                if model._meta.db_table.startswith('main'):
                    # Retrieve all instances of the model
                    instances = model.objects.all()

                    total_size = 0
                    for instance in instances:
                        total_size += sys.getsizeof(instance)

                    readable_size = self.convert_bytes(total_size)
                    self.stdout.write(
                        f'Table: {model._meta.db_table}, Estimated Size: {readable_size}'
                    )
