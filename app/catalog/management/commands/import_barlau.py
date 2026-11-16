from django.core.management.base import BaseCommand

from catalog.importer import run_import
from catalog.models import SiteSettings


class Command(BaseCommand):
    help = "Загрузить каталог из выгрузок Barlau (Excel + YML)."

    def add_arguments(self, p):
        p.add_argument("--if-requested", action="store_true", help="Только если в админке нажали «Обновить сейчас».")
        p.add_argument("--excel", help="Взять Excel из файла, а не по ссылке.")
        p.add_argument("--yml", help="Взять YML из файла, а не по ссылке.")

    def handle(self, *a, **o):
        if o["if_requested"] and not SiteSettings.get().import_requested:
            return
        source = "file" if (o["excel"] or o["yml"]) else ("manual" if o["if_requested"] else "cron")
        run = run_import(source=source, excel_file=o["excel"], yml_file=o["yml"])
        self.stdout.write(run.log)
        if run.status != "ok":
            raise SystemExit(1)
