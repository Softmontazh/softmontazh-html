from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Софтмонтаж — каталог"
admin.site.site_title = "Софтмонтаж"
admin.site.index_title = "Управление каталогом"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("catalog.urls")),
]

# Локальная разработка: отдаём файлы статического сайта (на сервере это делает nginx)
from django.conf import settings  # noqa: E402

if settings.DEBUG:
    from django.urls import re_path
    from django.views.static import serve

    urlpatterns += [re_path(r"^(?P<path>(assets|brand)/.*)$", serve, {"document_root": settings.SITE_ROOT})]
