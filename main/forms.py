from django import forms
from django.utils.timezone import now

from main.models import ShopGame


class ShopGameForm(forms.ModelForm):
    class Meta:
        model = ShopGame
        fields = ['shop', 'game', 'url', 'url_at', 'mia', 'current_available', 'current_price']

    def clean_url(self):
        """Clean the url."""
        url_part = self.cleaned_data['url'].partition('?')[0]
        self.cleaned_data['url_at'] = now()
        return url_part
