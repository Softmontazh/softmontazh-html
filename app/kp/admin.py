from django.contrib import admin

from .models import KP, KPItem, KPTemplate, Lead


@admin.register(KPTemplate)
class KPTemplateAdmin(admin.ModelAdmin):
    """Реквизиты фирмы в КП. Оформление (светлая шапка, индиго) одно на весь сайт."""
    fields = ["company", "slogan", "logo", "contacts", "footer"]
    list_display = ["company"]

    def has_add_permission(self, request):
        return not KPTemplate.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ["pk", "created", "name", "phone", "kind", "source", "status", "total", "manager"]
    list_filter = ["status", "kind", "source", "manager"]
    search_fields = ["name", "phone", "email", "company"]
    readonly_fields = ["created", "items", "total"]


class KPItemInline(admin.TabularInline):
    model = KPItem
    extra = 0
    fields = ["section", "name", "qty", "price", "retail", "floor", "purchase"]


@admin.register(KP)
class KPAdmin(admin.ModelAdmin):
    list_display = ["__str__", "date", "to", "manager", "status"]
    list_filter = ["status", "manager"]
    search_fields = ["to"]
    inlines = [KPItemInline]
