from django.contrib import admin, messages

from .models import TgChat, TgEvent, TgOutbox, TgUser
from .services.outbox import enqueue_kick


@admin.register(TgUser)
class TgUserAdmin(admin.ModelAdmin):
    list_display = ["user", "username", "name", "telegram_id", "active", "linked_at"]
    list_filter = ["active"]
    readonly_fields = ["user", "telegram_id", "username", "name", "linked_at"]
    actions = ["disable_and_kick"]

    @admin.action(description="Отключить от бота и убрать из групп менеджеров")
    def disable_and_kick(self, request, qs):
        n = 0
        for t in qs.filter(active=True):
            t.active = False
            t.save(update_fields=["active"])
            enqueue_kick(t.telegram_id)
            n += 1
        self.message_user(request, f"Отключено: {n}. Из групп уберёт бот (нужны права админа группы).", messages.SUCCESS)

    def save_model(self, request, obj, form, change):
        was = TgUser.objects.filter(pk=obj.pk, active=True).exists() if obj.pk else False
        super().save_model(request, obj, form, change)
        if was and not obj.active:
            enqueue_kick(obj.telegram_id)

    def has_add_permission(self, request):
        return False


@admin.register(TgChat)
class TgChatAdmin(admin.ModelAdmin):
    list_display = ["title", "chat_id", "active", "bound_by", "bound_at"]
    list_editable = ["active"]
    readonly_fields = ["chat_id", "bound_by", "bound_at"]

    def has_add_permission(self, request):
        return False


@admin.register(TgOutbox)
class TgOutboxAdmin(admin.ModelAdmin):
    list_display = ["created", "kind", "chat_id", "status", "attempts", "error", "sent_at"]
    list_filter = ["status", "kind"]
    readonly_fields = [f.name for f in TgOutbox._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(TgEvent)
class TgEventAdmin(admin.ModelAdmin):
    list_display = ["created", "user", "telegram_id", "action", "obj", "ok"]
    list_filter = ["ok", "action"]
    readonly_fields = [f.name for f in TgEvent._meta.fields]

    def has_add_permission(self, request):
        return False
