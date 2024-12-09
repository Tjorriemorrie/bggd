import logging

from django import forms
from django.utils import timezone

from main.constants import CATEGORY_CHOICES
from main.models import Listing

logger = logging.getLogger(__name__)


class LookupForm(forms.Form):
    listing_id = forms.IntegerField(widget=forms.HiddenInput())
    bgg_id = forms.IntegerField(required=False, widget=forms.NumberInput())
    is_missing = forms.BooleanField(
        required=False, initial=False, label='Is missing?', widget=forms.CheckboxInput()
    )
    category = forms.ChoiceField(
        required=False,
        choices=list(CATEGORY_CHOICES),
        widget=forms.Select(),
        label='Category',
    )

    def save(self) -> Listing:
        """Save bgg_id to listing."""
        listing = Listing.objects.get(id=self.cleaned_data['listing_id'])
        new_bgg_id = self.cleaned_data.get('bgg_id') or None
        if listing.bgg_id != new_bgg_id:
            listing.bgg_id = new_bgg_id
            if listing.game:
                listing.game.shop_outdated = True
                listing.game.save()
            listing.game = None
        if self.cleaned_data.get('is_missing', False):
            listing.bgg_missing = True
            listing.bgg_id = None
            if listing.game:
                listing.game.shop_outdated = True
                listing.game.save()
            listing.game = None
        else:
            listing.bgg_missing = False

        # Update category
        category = self.cleaned_data.get('category') or None
        if listing.category != category:
            listing.category = category

        listing.bgg_looked_at = timezone.now()
        listing.save()
        logger.info(
            f'Saved bgg info: id={listing.bgg_id} missing={listing.bgg_missing} to {listing}'
        )
        return listing
