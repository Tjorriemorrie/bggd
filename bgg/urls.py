from django.urls import include, path

from main import views
from main.admin import admin_site_urls

urlpatterns = [
    # path('favicon.ico', RedirectView.as_view(url=staticfiles_storage.url('favicon.ico')),),
    path('admin/', admin_site_urls),
    path('', views.HomeView.as_view(), name='home'),
    path('got/', views.GotView.as_view(), name='got'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('games/', views.GameListView.as_view(), name='game_list'),
    path('games/<int:pk>', views.GameDetailView.as_view(), name='game_detail'),
    path('players/', views.PlayerListView.as_view(), name='player_list'),
    path('players/<int:pk>', views.PlayerDetailView.as_view(), name='player_detail'),
    path('players/<int:pk>/predict', views.player_predict_view, name='player_predict'),
    path('reviews/', views.ReviewView.as_view(), name='reviews'),
    path('shop/', views.ShopView.as_view(), name='shop'),
    path('redo/', views.redo_prediction_view, name='redo'),
    path(r'ht/', include('health_check.urls')),
    path(r'country', views.CountryView.as_view(), name='country'),
]
