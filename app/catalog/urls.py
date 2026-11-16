from django.urls import path

from . import views

urlpatterns = [
    path("catalog/", views.catalog_page, name="catalog"),
    path("catalog/<slug:slug>/", views.product_page, name="product"),
    path("api/catalog/menu", views.api_menu),
    path("api/catalog/products", views.api_products),
]
