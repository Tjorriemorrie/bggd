from django.contrib import admin
from django.urls import path
from django.views.decorators.cache import cache_page

from main import views

VIEW_CACHE = 60 * 10  # 10 minutes

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', cache_page(VIEW_CACHE)(views.home_view), name='home'),
    path('listings/', cache_page(VIEW_CACHE)(views.ListingListView.as_view()), name='listing-list'),
    path(
        'listing/<int:pk>/',
        cache_page(VIEW_CACHE)(views.ListingDetailView.as_view()),
        name='listing-detail',
    ),
    path(
        'listing/<int:pk>/<slug:slug>/',
        cache_page(VIEW_CACHE)(views.ListingDetailView.as_view()),
        name='listing-detail-slug',
    ),
    path('shops/', cache_page(VIEW_CACHE)(views.ShopListView.as_view()), name='shop-list'),
    path(
        'shop/<int:pk>/', cache_page(VIEW_CACHE)(views.ShopDetailView.as_view()), name='shop-detail'
    ),
    path(
        'shop/<int:pk>/<slug:slug>/',
        cache_page(VIEW_CACHE)(views.ShopDetailView.as_view()),
        name='shop-detail-slug',
    ),
    path('games/', cache_page(VIEW_CACHE)(views.GameListView.as_view()), name='game-list'),
    path(
        'game/<int:pk>/', cache_page(VIEW_CACHE)(views.GameDetailView.as_view()), name='game-detail'
    ),
    path(
        'game/<int:pk>/<slug:slug>/',
        cache_page(VIEW_CACHE)(views.GameDetailView.as_view()),
        name='game-detail-slug',
    ),
    path('fixme/', views.fixme_view, name='fixme'),
]
