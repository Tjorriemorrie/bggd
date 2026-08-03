from django.db import migrations

OLD = 'https://fanaticus.co.za/'
NEW = 'https://store.fanaticus.co.za/'


def _move(apps, old, new):
    """Repoint listing urls from one host to the other, skipping collisions."""
    Listing = apps.get_model('main', 'Listing')
    taken = set(Listing.objects.filter(url__startswith=new).values_list('url', flat=True))
    for listing in Listing.objects.filter(url__startswith=old):
        url = new + listing.url[len(old) :]
        if url in taken:
            continue
        listing.url = url
        listing.save(update_fields=['url'])
        taken.add(url)


def forwards(apps, schema_editor):
    """Fanaticus moved its shop to store.fanaticus.co.za, keeping /product/<slug>/."""
    _move(apps, OLD, NEW)


def backwards(apps, schema_editor):
    """Move the urls back to the bare domain."""
    _move(apps, NEW, OLD)


class Migration(migrations.Migration):
    dependencies = [
        ('main', '0026_visitorlog'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
