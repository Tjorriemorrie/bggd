import logging

from django.db.models import (
    Count,
    ExpressionWrapper,
    F,
    FloatField,
    OrderBy,
    OuterRef,
    Q,
    Subquery,
    Value,
)
from django.db.models.functions import Concat
from django.template.defaultfilters import floatformat
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django_tables2 import BooleanColumn, Column, tables

from main.models import Game, Listing, Scrapelog, Shop
from main.selectors import get_last_scrape
from main.templatetags.fmt import discount, price

logger = logging.getLogger(__name__)


class ListingTable(tables.Table):
    img = Column(verbose_name='', attrs={'td': {'class': 'text-end'}})
    name = Column(
        verbose_name='Name',
        attrs={
            'td': {
                'class': lambda record: 'text-decoration-line-through'
                if not record.in_stock
                else ''
            },
        },
    )
    price = Column(initial_sort_descending=True)
    discount = Column(verbose_name='Discount', empty_values=(), initial_sort_descending=True)
    in_stock = BooleanColumn(verbose_name='Available')
    is_new = BooleanColumn(verbose_name='New')

    class Meta:
        model = Listing
        fields = (
            'img',
            'name',
            'shop',
            'price',
            'discount',
            'in_stock',
            'is_new',
        )
        template_name = 'main/table_list.html'

    def __getattr__(self, item):
        """Handle ordering in one function."""
        if item.startswith('order_'):
            field_name = item.replace('order_', '')
            return lambda queryset, is_descending: self._handle_ordering(
                field_name, queryset, is_descending
            )
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

    def _handle_ordering(self, field_name, queryset, is_descending):
        """Handle ordering for all fields."""
        str_field_name = f'-{field_name}' if is_descending else field_name
        required_ordering = [str_field_name] + [
            default_field
            for default_field in ['-in_stock', '-discount', '-price']
            if default_field not in (field_name, f'-{field_name}')
        ]

        created_ordering = []
        for req_field_name in required_ordering:
            is_desc = req_field_name.startswith('-')
            fn = req_field_name.lstrip('-')
            if fn == 'discount':
                discount_expr = ExpressionWrapper(
                    F('game__shop_mean') - F('price'), output_field=FloatField()
                )
                queryset = queryset.annotate(discount=discount_expr)
            # Create the new order field
            order_field = F(fn).desc(nulls_last=True) if is_desc else F(fn).asc(nulls_last=True)
            created_ordering.append(order_field)

        queryset = queryset.order_by(*created_ordering)
        return queryset, True

    def render_img(self, value: str, record: Listing):
        """Render image."""
        oos = 'out-of-stock-img' if not record.in_stock else ''
        return format_html(f'<img src="{value}" class="list-img {oos}" />')

    def render_name(self, record: Listing):
        """Render name."""
        name = f'<a href="{record.get_absolute_url()}" class="me-3">{record.name}</a>'
        game = (
            f'<a href="{record.game.get_absolute_url()}" class=""><i class="bi bi-puzzle"></i></a>'
            if record.game
            else ''
        )
        return format_html(name + game)

    def render_shop(self, record: Listing):
        """Render shop."""
        name = f'<a class="me-3">{record.shop.name}</a>'
        ext = (
            f'<a href="{record.url}" target="_blank" class="me-3">'
            f'<i class="bi bi-box-arrow-up-right"></i>'
            f'</a>'
        )
        return format_html(name + ext)

    def render_price(self, record: Listing):
        """Render price."""
        return price(record, show_currency=False)

    def render_discount(self, record: Listing):
        """Render price with filter."""
        return discount(record, show_currency=False)


class ShopTable(tables.Table):
    new_cnt = Column(verbose_name='New Items', empty_values=(), initial_sort_descending=True)
    second_cnt = Column(verbose_name='Second Items', empty_values=(), initial_sort_descending=True)
    scraped = Column(verbose_name='Scraped', empty_values=(), initial_sort_descending=True)

    class Meta:
        model = Shop
        fields = (
            'name',
            'new_cnt',
            'second_cnt',
            'scraped',
        )
        template_name = 'main/table_list.html'

    def render_name(self, record: Shop):
        """Render name."""
        # Use get_absolute_url to link to the detail page
        name = f'<a href="{record.get_absolute_url()}" class="me-3">{record.name}</a>'
        return format_html(name)

    def order_new_cnt(self, queryset, is_descending):
        """Order listings count."""
        queryset = queryset.annotate(new_cnt=Count('listings', filter=Q(listings__is_new=True)))
        ordering = '-new_cnt' if is_descending else 'new_cnt'
        return queryset.order_by(ordering), True

    def render_new_cnt(self, record: Shop):
        """Show number of listings."""
        return record.listings.filter(is_new=True).count()

    def order_second_cnt(self, queryset, is_descending):
        """Order listings count."""
        queryset = queryset.annotate(second_cnt=Count('listings', filter=Q(listings__is_new=False)))
        ordering = '-second_cnt' if is_descending else 'second_cnt'
        return queryset.order_by(ordering), True

    def render_second_cnt(self, record: Shop):
        """Show number of listings."""
        return record.listings.filter(is_new=False).count()

    def order_scraped(self, queryset, is_descending):
        """Order based on last scrape."""
        # Subquery to find the latest scraped_at for each shop
        latest_scrape = (
            Scrapelog.objects.filter(target=Concat(Value('shop '), OuterRef('name')))
            .order_by('-scraped_at')
            .values('scraped_at')[:1]
        )

        # Annotate each shop with the latest scrape date from Scrapelog
        queryset = queryset.annotate(last_scraped_at=Subquery(latest_scrape))

        ordering = 'last_scraped_at' if not is_descending else '-last_scraped_at'
        return queryset.order_by(ordering), True

    def render_scraped(self, record: Shop):
        """Show last scraped date."""
        if scrapelog := get_last_scrape(record):
            return f'{scrapelog.scraped_at:%Y-%m-%d}'
        else:
            return ''


class GameTable(tables.Table):
    rating = Column(initial_sort_descending=True)
    img = Column(verbose_name='', empty_values=(), attrs={'td': {'class': 'text-end'}})
    year = Column(initial_sort_descending=True)
    shop_price = Column(verbose_name='Price', initial_sort_descending=True)
    shop_saving = Column(verbose_name='Discount', initial_sort_descending=True)
    shop_in_stock = BooleanColumn(verbose_name='Available', initial_sort_descending=True)

    class Meta:
        model = Game
        fields = (
            'rank',
            'rating',
            'year',
            'img',
            'name',
            'shop_price',
            'shop_saving',
            'shop_in_stock',
        )
        template_name = 'main/table_list.html'

    def __getattr__(self, item):
        """Handle ordering in one function."""
        if item.startswith('order_'):
            field_name = item.replace('order_', '')
            return lambda queryset, is_descending: self._handle_ordering(
                field_name, queryset, is_descending
            )
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

    def _handle_ordering(self, field_name, queryset, is_descending):
        """Handle ordering for all fields."""
        cleaned_ordering = []

        for order in queryset.query.order_by:
            # Check if order is an OrderBy object or a string
            if isinstance(order, OrderBy):
                # Compare the field name from OrderBy with the current field_name
                order_field_name = (
                    order.expression.name if hasattr(order.expression, 'name') else order.expression
                )
            else:
                # Remove '-' from string-based fields
                order_field_name = order.lstrip('-')

            # Only keep the orders that are not for the current field_name
            if order_field_name != field_name:
                cleaned_ordering.append(order)

        # Create the new order field
        order_field = (
            F(field_name).desc(nulls_last=True)
            if is_descending
            else F(field_name).asc(nulls_last=True)
        )

        # Prepend the new order field
        cleaned_ordering.insert(0, order_field)

        # Apply the new ordering
        queryset = queryset.order_by(*cleaned_ordering)

        return queryset, True

    def render_rating(self, value: float):
        """Render with floatformat."""
        return floatformat(value, 1)

    def render_img(self, record: Game):
        """Render img."""
        oos = 'out-of-stock-img' if not record.shop_in_stock else ''
        img = (
            f'<a href="{record.get_absolute_url()}">'
            f'<img src="{record.img}" class="list-img {oos}"/>'
            f'</a>'
        )
        return mark_safe(img)

    def render_name(self, record: Game):
        """Render name."""
        # Use get_absolute_url to link to the detail page
        oos = 'class="out-of-stock-txt"' if not record.shop_in_stock else ''
        name = f'<a href="{record.get_absolute_url()}" {oos}>{record.name}</a>'
        return mark_safe(name)

    # def order_rank(self, queryset, is_descending):
    def order_shop_price(self, queryset, is_descending):
        """Order field with None values at the end."""
        order_field = (
            F('shop_price').desc(nulls_last=True)
            if is_descending
            else F('shop_price').asc(nulls_last=True)
        )
        queryset = queryset.order_by(order_field)
        return queryset, True

    def render_shop_price(self, record: Game):
        """Render price with filter."""
        price_txt = price(record, show_currency=False)
        shop_name = record.shop_best.name
        return mark_safe(f'{price_txt}<br/>{shop_name}')

    def render_shop_saving(self, record: Game):
        """Render price with filter."""
        return discount(record, show_currency=False)

    def render_shop_in_stock(self, record: Game):
        """Render number of shops."""
        cnt = record.listings.filter(in_stock=True).count()
        return cnt
