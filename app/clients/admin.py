from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["__str__", "display_phone", "phone_verified", "telegram_username", "company", "n_leads", "last_seen", "blocked"]
    list_filter = ["phone_verified", "blocked"]
    search_fields = ["name", "phone", "email", "company", "telegram_username"]
    readonly_fields = ["telegram_id", "created", "last_seen", "cart"]
    fields = ["name", "phone", "phone_verified", "email", "company", "telegram_id", "telegram_username", "blocked", "note", "cart", "created", "last_seen"]

    @admin.display(description="Заявок")
    def n_leads(self, obj):
        return obj.leads.count()
