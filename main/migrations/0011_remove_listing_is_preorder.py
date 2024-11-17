from django.db import migrations


def remove_preorder_listings(apps, schema_editor):
    Listing = apps.get_model('main', 'Listing')
    # Delete all listings where `is_preorder` was True
    Listing.objects.filter(is_preorder=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('main', '0010_alter_game_slug_alter_listing_slug'),
    ]

    operations = [
        migrations.RunPython(remove_preorder_listings),
        migrations.RemoveField(
            model_name='listing',
            name='is_preorder',
        ),
    ]
