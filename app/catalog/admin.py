from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html

from django.db.models import Count

from .models import Brand, Category, ImportRun, Node, Product, SiteSettings, recalc_prices


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    readonly_fields = ["last_check"]
    fieldsets = [
        ("Менеджер", {"fields": ["manager_name", "show_phone", "manager_phone", "manager_whatsapp"],
                      "description": "Контакты для покупателей: подставляются в кнопки звонка и WhatsApp на всём сайте (обновление — в течение минуты)."}),
        ("Цены", {"fields": ["markup_percent", "round_to", "price_note"]}),
        ("Что показывать", {"fields": ["show_without_price", "show_out_of_stock"]}),
        ("Выгрузки Barlau", {"fields": ["import_interval", "last_check", "excel_url", "yml_url"]}),
    ]

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        return redirect(reverse("admin:catalog_sitesettings_change", args=[SiteSettings.get().pk]))

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if {"markup_percent", "round_to"} & set(form.changed_data):
            recalc_prices()
            messages.info(request, "Цены на сайте пересчитаны.")


class CategoryInline(admin.TabularInline):
    model = Category
    fields = ["name", "enabled", "sort", "markup_percent", "purchase_discount", "n_products"]
    readonly_fields = ["name", "n_products"]
    extra = 0
    can_delete = False
    show_change_link = True

    @admin.display(description="Товаров")
    def n_products(self, obj):
        return obj.products.filter(is_active=True).count()


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ["name", "enabled", "sort", "markup_percent", "purchase_discount", "n_products"]
    list_editable = ["enabled", "sort", "markup_percent", "purchase_discount"]
    fields = ["name", "slug", "enabled", "sort", "markup_percent", "purchase_discount"]
    readonly_fields = ["slug"]
    inlines = [CategoryInline]

    @admin.display(description="Товаров")
    def n_products(self, obj):
        return obj.products.filter(is_active=True).count()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if {"markup_percent", "purchase_discount"} & set(form.changed_data):
            recalc_prices(obj.products.all())

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        recalc_prices(form.instance.products.all())

    def changelist_view(self, request, extra_context=None):
        resp = super().changelist_view(request, extra_context)
        if request.method == "POST" and "_save" in request.POST:
            recalc_prices()  # правили наценку прямо в списке
        return resp


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "brand", "enabled", "sort", "markup_percent", "purchase_discount"]
    list_editable = ["enabled", "sort", "markup_percent", "purchase_discount"]
    list_filter = ["brand", "enabled"]
    search_fields = ["name"]
    fields = ["brand", "name", "slug", "enabled", "sort", "markup_percent", "purchase_discount"]
    readonly_fields = ["brand", "name", "slug"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        recalc_prices(obj.products.all())

    def changelist_view(self, request, extra_context=None):
        resp = super().changelist_view(request, extra_context)
        if request.method == "POST" and "_save" in request.POST:
            recalc_prices()
        return resp


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["thumb", "model", "brand", "category", "base_price", "price", "purchase_price", "margin", "stock_label_", "is_active", "hidden"]
    list_display_links = ["thumb", "model"]
    list_editable = ["hidden"]
    list_filter = ["brand", "is_active", "hidden", ("price_override", admin.EmptyFieldListFilter), "category"]
    search_fields = ["model", "name", "article", "type"]
    list_per_page = 50
    list_select_related = ["brand", "category"]
    actions = ["hide", "show"]
    readonly_fields = ["barlau_id", "model", "name", "type", "brand", "category", "node", "subpath", "description", "image_preview",
                       "barlau_link", "article", "gtin", "warranty", "box_qty", "base_price", "price", "stock", "stock_label",
                       "is_active", "last_seen", "created", "updated", "site_link", "purchase_price", "purchase_source", "margin"]
    fieldsets = [
        ("На сайте", {"fields": ["site_link", "hidden", "title_override", "price_override", "description_override"]}),
        ("Закупка (видите только вы)", {"fields": ["purchase_price", "purchase_source", "margin", "purchase_override"]}),
        ("Из выгрузки Barlau (обновляется автоматически)", {"fields": [
            "image_preview", "model", "name", "type", "brand", "category", "node", "subpath", "base_price", "price", "stock", "stock_label",
            "warranty", "article", "gtin", "box_qty", "description", "barlau_id", "barlau_link", "is_active", "last_seen", "created", "updated"]}),
    ]

    @admin.display(description="")
    def thumb(self, obj):
        return format_html('<img src="{}" style="width:44px;height:44px;object-fit:contain" referrerpolicy="no-referrer" loading="lazy">', obj.image_url) if obj.image_url else "—"

    @admin.display(description="Маржа")
    def margin(self, obj):
        if not obj.purchase_price or not obj.price:
            return "—"
        m = obj.price - obj.purchase_price
        return f"{m:,} ₸ · {m * 100 / obj.price:.0f}%".replace(",", " ")

    @admin.display(description="Остаток", ordering="stock")
    def stock_label_(self, obj):
        return obj.stock_label or obj.stock

    @admin.display(description="Фото")
    def image_preview(self, obj):
        return format_html('<img src="{}" style="max-width:260px;max-height:260px" referrerpolicy="no-referrer">', obj.image_url) if obj.image_url else "—"

    @admin.display(description="Страница в Barlau")
    def barlau_link(self, obj):
        return format_html('<a href="{0}" target="_blank" rel="noopener">{0}</a>', obj.barlau_url) if obj.barlau_url else "—"

    @admin.display(description="Страница на сайте")
    def site_link(self, obj):
        return format_html('<a href="/catalog/{0}/" target="_blank">softmontazh.kz/catalog/{0}/</a>', obj.slug)

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        recalc_prices(Product.objects.filter(pk=obj.pk))

    @admin.action(description="Скрыть с сайта")
    def hide(self, request, qs):
        self.message_user(request, f"Скрыто: {qs.update(hidden=True)}")

    @admin.action(description="Показывать на сайте")
    def show(self, request, qs):
        self.message_user(request, f"Показывается: {qs.update(hidden=False)}")


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    """Дерево разделов Barlau — здесь задаётся скидка закупки по разделам и подразделам."""
    list_display = ["tree_name", "purchase_discount", "effective", "n_products"]
    list_editable = ["purchase_discount"]
    list_display_links = None
    search_fields = ["name"]
    list_filter = ["depth"]
    list_per_page = 200
    ordering = ["path"]
    fields = ["name", "purchase_discount"]
    readonly_fields = ["name"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        nodes = {n.pk: n for n in Node.objects.only("pk", "parent_id", "barlau_id", "name", "purchase_discount", "path")}
        self._eff, self._cnt = {}, {}
        for n in nodes.values():
            cur, eff = n, None
            while cur is not None:
                if cur.purchase_discount is not None:
                    eff = (cur.purchase_discount, cur.name if cur.pk != n.pk else "")
                    break
                cur = nodes.get(cur.parent_id)
            self._eff[n.pk] = eff
        direct = dict(Product.objects.filter(is_active=True).order_by().values("node_id").annotate(n=Count("id")).values_list("node_id", "n"))
        for pk, c in direct.items():
            cur = nodes.get(pk)
            while cur is not None:
                self._cnt[cur.pk] = self._cnt.get(cur.pk, 0) + c
                cur = nodes.get(cur.parent_id)
        resp = super().changelist_view(request, extra_context)
        if request.method == "POST" and "_save" in request.POST:
            recalc_prices()
        return resp

    @admin.display(description="Раздел", ordering="path")
    def tree_name(self, obj):
        return format_html('<span style="padding-left:{}px">{}{}</span>', obj.depth * 18,
                           "" if obj.depth == 0 else "└ ", obj.name)

    @admin.display(description="Действует")
    def effective(self, obj):
        e = getattr(self, "_eff", {}).get(obj.pk)
        if not e:
            return "— (бренд или не задана)"
        return f"−{e[0].normalize():f}%" + (f" от «{e[1]}»" if e[1] else "")

    @admin.display(description="Товаров")
    def n_products(self, obj):
        return getattr(self, "_cnt", {}).get(obj.pk, 0)


@admin.register(ImportRun)
class ImportRunAdmin(admin.ModelAdmin):
    list_display = ["started", "status", "source", "total", "created_count", "updated_count", "price_up", "price_down",
                    "out_of_stock", "back_in_stock", "deactivated_count"]
    readonly_fields = [f.name for f in ImportRun._meta.fields]
    change_list_template = "admin/catalog/importrun_changelist.html"

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        return [path("request/", self.admin_site.admin_view(self.request_import), name="catalog_importrun_request")] + super().get_urls()

    def request_import(self, request):
        if request.method == "POST":
            SiteSettings.objects.filter(pk=SiteSettings.get().pk).update(import_requested=True)
            messages.success(request, "Обновление запрошено — начнётся в течение 10 минут (загрузка будет полной, даже если выгрузка не менялась). Обновите эту страницу позже.")
        return redirect(reverse("admin:catalog_importrun_changelist"))

    def changelist_view(self, request, extra_context=None):
        extra_context = {**(extra_context or {}), "import_requested": SiteSettings.get().import_requested}
        return super().changelist_view(request, extra_context)
