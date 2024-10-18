from django.db import models


class ListingManager(models.Manager):
    def get_queryset(self):
        """Exclude listings that are marked as accessories."""
        return super().get_queryset().exclude(is_accessory=True)

    def incl_accessories(self):
        """"""
        return super().get_queryset()

    def only_accessories(self):
        """Get only accessories."""
        return super().get_queryset().filter(is_accessory=True)
