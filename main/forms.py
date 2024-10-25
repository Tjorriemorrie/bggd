import logging

from django import forms
from django.utils import timezone

from main.models import Listing

logger = logging.getLogger(__name__)


class LookupForm(forms.Form):
    listing_id = forms.IntegerField(widget=forms.HiddenInput())
    bgg_id = forms.IntegerField(required=False, widget=forms.NumberInput())
    is_missing = forms.BooleanField(
        required=False, initial=False, label='Is missing?', widget=forms.CheckboxInput()
    )
    is_accessory = forms.BooleanField(
        required=False, initial=False, label='Is accessory?', widget=forms.CheckboxInput()
    )

    def save(self) -> Listing:
        """Save bgg_id to listing."""
        listing = Listing.objects.get(id=self.cleaned_data['listing_id'])
        listing.bgg_id = self.cleaned_data.get('bgg_id') or None
        if self.cleaned_data.get('is_missing', False):
            listing.bgg_missing = True
            listing.bgg_id = None
        else:
            listing.bgg_missing = False
        listing.is_accessory = self.cleaned_data.get('is_accessory', False)
        listing.bgg_looked_at = timezone.now()
        listing.save()
        logger.info(
            f'Saved bgg info: id={listing.bgg_id} missing={listing.bgg_missing} to {listing}'
        )
        return listing
