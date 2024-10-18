from django.contrib import admin
from django.urls import path

from main import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home_view, name='home'),
    path('listings/', views.ListingListView.as_view(), name='listing-list'),
    path('listing/<int:pk>/', views.ListingDetailView.as_view(), name='listing-detail'),
    path(
        'listing/<int:pk>/<slug:slug>/',
        views.ListingDetailView.as_view(),
        name='listing-detail-slug',
    ),
    path('shops/', views.ShopListView.as_view(), name='shop-list'),
    path('shop/<int:pk>/', views.ShopDetailView.as_view(), name='shop-detail'),
    path('shop/<int:pk>/<slug:slug>/', views.ShopDetailView.as_view(), name='shop-detail-slug'),
    path('games/', views.GameListView.as_view(), name='game-list'),
    path('game/<int:pk>/', views.GameDetailView.as_view(), name='game-detail'),
    path('game/<int:pk>/<slug:slug>/', views.GameDetailView.as_view(), name='game-detail-slug'),
    # path('games/', views.GameListView.as_view(), name='game_list'),
    # path('got/', views.GotView.as_view(), name='got'),
    # path('about/', views.AboutView.as_view(), name='about'),
    # path('games/<int:pk>', views.GameDetailView.as_view(), name='game_detail'),
    # path('players/', views.PlayerListView.as_view(), name='player_list'),
    # path('players/<int:pk>', views.PlayerDetailView.as_view(), name='player_detail'),
    # path('players/<int:pk>/predict', views.player_predict_view, name='player_predict'),
    # path('reviews/', views.ReviewView.as_view(), name='reviews'),
    # path('redo/', views.redo_prediction_view, name='redo'),
    # path(r'ht/', include('health_check.urls')),
    # path(r'country', views.CountryView.as_view(), name='country'),
]
