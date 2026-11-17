"""Группа «Менеджер»: только просмотр товаров (розница, пол, сколько можно уступить, наличие)."""
from django.db import migrations


def create_group(apps, schema_editor):
    from django.contrib.auth.management import create_permissions
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    g, _ = Group.objects.get_or_create(name="Менеджер")
    g.permissions.set(Permission.objects.filter(content_type__app_label="catalog", codename="view_product"))


class Migration(migrations.Migration):
    dependencies = [("catalog", "0008_manager_rules"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(create_group, migrations.RunPython.noop)]
