from django.db import models


class ListingManager(models.Manager):
    def __init__(self, excludes: list = None, filter_: str = None):
        """Set filter."""
        super().__init__()
        self.excludes = excludes
        self._filter = filter_

    def get_queryset(self):
        """Exclude or filter by category."""
        qset = super().get_queryset()
        if self.excludes:
            qset = qset.exclude(category__in=self.excludes)
        if self._filter:
            qset = qset.filter(category=self._filter)
        return qset


class GameManager(models.Manager):
    def __init__(self, excludes: list = None, filters: list = None):
        """Set filter."""
        super().__init__()
        self.excludes = excludes
        self.filters = filters

    def get_queryset(self):
        """Exclude or filter by category."""
        qset = super().get_queryset()
        if self.excludes:
            qset = qset.exclude(listings__category__in=self.excludes)
        if self.filters:
            qset = qset.filter(listings__category__in=self.filters)
        return qset
