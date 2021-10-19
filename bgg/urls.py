"""bgg URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from main import views

urlpatterns = [
    # path('favicon.ico', RedirectView.as_view(url=staticfiles_storage.url('favicon.ico')),),
    path('admin/', admin.site.urls),
    path('', views.home_view, name='home'),
    path('got/', views.got_view, name='got'),
    path('about/', views.about_view, name='about'),
    path('games/', views.GameListView.as_view(), name='game_list'),
    path('games/<int:pk>', views.GameDetailView.as_view(), name='game_detail'),
    path('players/', views.PlayerListView.as_view(), name='player_list'),
    path('players/<int:pk>', views.PlayerDetailView.as_view(), name='player_detail'),
    path('players/<int:pk>/predict', views.player_predict_view, name='player_predict'),
    path('reviews/', views.ReviewView.as_view(), name='reviews'),
]
