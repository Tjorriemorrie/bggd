from django import forms

from main.models import ShopGame


class ShopGameForm(forms.ModelForm):
    class Meta:
        model = ShopGame
        fields = ['shop', 'game', 'url', 'mia']

    def clean_url(self):
        """Clean the url."""
        if self.cleaned_data['url']:
            url_part = self.cleaned_data['url'].partition('?')[0]
            return url_part
