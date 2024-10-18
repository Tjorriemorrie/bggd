from django.db import migrations


def flip_is_new_values(apps, schema_editor):
    # Get the Listing model
    Listing = apps.get_model('main', 'Listing')

    # Flip all the is_new values (True to False, False to True)
    for listing in Listing.objects.all():
        listing.is_new = not listing.is_new
        listing.save()


class Migration(migrations.Migration):
    dependencies = [
        ('main', '0003_listing_is_second'),
    ]

    operations = [
        migrations.RenameField(
            model_name='listing',
            old_name='is_second',
            new_name='is_new',
        ),
        migrations.RunPython(flip_is_new_values),  # Call the function to flip the values
    ]
