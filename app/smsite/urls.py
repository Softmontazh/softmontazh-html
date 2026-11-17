from django.contrib import admin
from django.urls import include, path

from kp import views as kp_views

from django.conf import settings as _s  # noqa: E402

admin.site.site_header = f"Софтмонтаж — каталог · версия {_s.APP_VERSION}"
admin.site.site_title = "Софтмонтаж"
admin.site.site_url = "/catalog/"  # ссылка «Открыть сайт» в админке ведёт в каталог
admin.site.index_title = "Управление каталогом"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("kp/", include("kp.urls")),
    path("catalog/cart/", kp_views.cart_page, name="cart"),
    path("api/cart/items", kp_views.api_cart_items),
    path("api/cart/lead", kp_views.api_lead),
    path("", include("catalog.urls")),
]

# Локальная разработка: отдаём файлы статического сайта (на сервере это делает nginx)
from django.conf import settings  # noqa: E402

if settings.DEBUG:
    from django.urls import re_path
    from django.views.static import serve

    urlpatterns += [re_path(r"^(?P<path>(assets|brand)/.*)$", serve, {"document_root": settings.SITE_ROOT}),
                    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT})]
