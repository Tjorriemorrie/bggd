from datetime import datetime

from django.db import migrations, models
from django.utils.timezone import make_aware


def fix_scraped_at_values(apps, schema_editor):
    Listing = apps.get_model('main', 'Listing')  # Get the Listing model dynamically
    for listing in Listing.objects.all():
        # Combine the date with a default time of 00:00:00
        new_datetime = datetime.combine(listing.scraped_at, datetime.min.time())
        # Make it timezone-aware if your project uses timezone support
        listing.scraped_at = make_aware(new_datetime)
        # Save the updated value
        listing.save()


class Migration(migrations.Migration):
    dependencies = [
        ('main', '0014_game_fix_me_pageview_viewed_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='listing',
            name='scraped_at',
            field=models.DateTimeField(),
        ),
        migrations.RunPython(fix_scraped_at_values),  # Add a RunPython operation
    ]
