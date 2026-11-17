from django.urls import path

from . import views

urlpatterns = [
    path("my/", views.my_page),
    path("my/login/", views.login_page),
    path("my/tg-login", views.tg_login),
    path("my/logout", views.logout),
    path("api/tg/webapp-login", views.api_webapp_login),
    path("api/me", views.api_me),
    path("api/me/cart", views.api_me_cart),
    path("api/me/profile", views.api_me_profile),
]
