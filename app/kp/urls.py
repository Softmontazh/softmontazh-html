from django.urls import path

from . import views

app_name = "kp"
urlpatterns = [
    path("", views.index, name="index"),
    path("templates/<int:pk>/", views.template_editor, name="template"),
    path("api/templates/<int:pk>/preview", views.api_preview),
    path("api/templates/<int:pk>/save", views.api_save),
    path("api/templates/<int:pk>/copy", views.api_copy),
    path("api/templates/<int:pk>/delete", views.api_delete),
    path("api/templates/<int:pk>/logo", views.api_logo),
]
