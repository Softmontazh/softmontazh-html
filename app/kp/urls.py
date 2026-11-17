from django.urls import path

from . import views

app_name = "kp"
urlpatterns = [
    path("", views.cabinet, name="cabinet"),
    path("leads/<int:pk>/", views.lead_page, name="lead"),
    path("<int:pk>/", views.kp_page, name="kp"),
    path("v/<str:token>/", views.kp_public, name="public"),
    path("api/leads/<int:pk>", views.api_lead_update),
    path("api/leads/<int:pk>/kp", views.api_lead_kp),
    path("api/from-cart", views.api_kp_from_cart),
    path("api/tg/link", views.api_tg_link),
    path("api/tg/unlink", views.api_tg_unlink),
    path("api/tg/group-code", views.api_tg_group_code),
    path("api/kp/<int:pk>/preview", views.api_kp_preview),
    path("api/kp/<int:pk>/save", views.api_kp_save),
    path("api/kp/<int:pk>/link", views.api_kp_link),
    path("api/kp/<int:pk>/copy", views.api_kp_copy),
]
