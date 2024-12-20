from django.db import models


class ListingManager(models.Manager):
    def __init__(self, exclude_: str = None, filter_: str = None):
        """Set filter."""
        super().__init__()
        self._exclude = exclude_
        self._filter = filter_

    def get_queryset(self):
        """Exclude or filter by category."""
        qset = super().get_queryset()
        if self._exclude:
            qset = qset.exclude(category=self._exclude)
        if self._filter:
            qset = qset.filter(category=self._filter)
        return qset
