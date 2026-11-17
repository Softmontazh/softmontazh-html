from django.core.management.base import BaseCommand

from catalog.importer import is_due, run_import
from catalog.models import SiteSettings


class Command(BaseCommand):
    help = "Загрузить каталог из выгрузок Barlau (Excel + YML)."

    def add_arguments(self, p):
        p.add_argument("--auto", action="store_true",
                       help="Для cron: проверить, пора ли (частота из админки) или нажата кнопка «Обновить сейчас».")
        p.add_argument("--force", action="store_true", help="Загрузить, даже если выгрузка не менялась.")
        p.add_argument("--excel", help="Взять Excel из файла, а не по ссылке.")
        p.add_argument("--yml", help="Взять YML из файла, а не по ссылке.")

    def handle(self, *a, **o):
        s = SiteSettings.get()
        manual = s.import_requested
        if o["auto"] and not is_due(s):
            return
        source = "file" if (o["excel"] or o["yml"]) else ("manual" if (manual or not o["auto"]) else "cron")
        run = run_import(source=source, excel_file=o["excel"], yml_file=o["yml"], force=o["force"] or manual or not o["auto"])
        if run is None:
            self.stdout.write("Выгрузка не изменилась — база не трогалась.")
            return
        self.stdout.write(run.log)
        if run.status != "ok":
            raise SystemExit(1)
