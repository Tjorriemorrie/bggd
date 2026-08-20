from django.db import migrations, models

from main.sleeves import parse_sleeve_size

BATCH = 500


def read_sleeve_sizes(apps, schema_editor):
    """Fill the sleeve size of every listing already scraped, from its name."""
    Listing = apps.get_model('main', 'Listing')
    sized = []
    for listing in Listing.objects.filter(name__icontains='sleeve').iterator():
        size = parse_sleeve_size(listing.name)
        if not size:
            continue
        listing.sleeve_width, listing.sleeve_height = size
        sized.append(listing)
    Listing.objects.bulk_update(sized, ['sleeve_width', 'sleeve_height'], batch_size=BATCH)


class Migration(migrations.Migration):
    dependencies = [
        ('main', '0027_fanaticus_store_subdomain'),
    ]

    operations = [
        migrations.AddField(
            model_name='listing',
            name='sleeve_width',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='sleeve_height',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.RunPython(read_sleeve_sizes, migrations.RunPython.noop),
    ]
