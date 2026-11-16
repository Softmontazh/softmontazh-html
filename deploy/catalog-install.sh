#!/usr/bin/env bash
# Софтмонтаж — разовая установка каталога (Django) на сервере. Повторный запуск безопасен.
#
#   sudo bash /var/www/softmontazh.kz/deploy/catalog-install.sh
#
# Что делает:
#   1) системный пользователь softmontazh, папки /opt/softmontazh/{venv,static,data,backups};
#   2) база PostgreSQL softmontazh (вход по имени пользователя, без пароля);
#   3) /opt/softmontazh/.env с секретным ключом (создаётся один раз, наружу не выводится);
#   4) Python-окружение и зависимости из app/requirements.txt;
#   5) миграции базы, статика админки;
#   6) сервис softmontazh.service (127.0.0.1:8002, 1 воркер, до 200 МБ памяти);
#   7) расписание /etc/cron.d/softmontazh-catalog (загрузка из Barlau каждые 6 ч, ночной бэкап);
#   8) первая загрузка каталога и вход в админку.
# nginx-конфиг ставит deploy/update.sh (он уже содержит /catalog/, /api/, /admin/).
set -euo pipefail

SITE_DIR="/var/www/softmontazh.kz"
APP_DIR="$SITE_DIR/app"
HOME_DIR="/opt/softmontazh"
U="softmontazh"
DB="softmontazh"

say() { echo -e "\n== $*"; }

if [[ $EUID -ne 0 ]]; then echo "Запустите через sudo: sudo bash $0" >&2; exit 1; fi
if [[ ! -f "$APP_DIR/manage.py" ]]; then
  echo "Нет $APP_DIR/manage.py — сначала обновите сайт: sudo bash $SITE_DIR/deploy/update.sh" >&2; exit 1
fi

say "1/8 Пользователь и папки"
id "$U" >/dev/null 2>&1 || useradd --system --home-dir "$HOME_DIR" --shell /usr/sbin/nologin "$U"
install -d -o "$U" -g "$U" -m 755 "$HOME_DIR" "$HOME_DIR/static" "$HOME_DIR/data"
install -d -o "$U" -g "$U" -m 750 "$HOME_DIR/backups"
# код сайта должен читаться пользователем сервиса
chmod o+rx /var/www "$SITE_DIR" 2>/dev/null || true
sudo -u "$U" test -r "$APP_DIR/manage.py" || { echo "Пользователь $U не может читать $APP_DIR — проверьте права." >&2; exit 1; }

say "2/8 База данных"
command -v psql >/dev/null || { echo "PostgreSQL не найден." >&2; exit 1; }
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$U'" | grep -q 1 || sudo -u postgres psql -qc "CREATE ROLE $U LOGIN"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB'" | grep -q 1 || sudo -u postgres createdb -O "$U" "$DB"
sudo -u "$U" psql -d "$DB" -tAc "SELECT 1" >/dev/null || { echo "Не удаётся войти в базу как $U (peer). Проверьте pg_hba.conf: local all all peer" >&2; exit 1; }
echo "База $DB готова."

say "3/8 Настройки (.env)"
if [[ ! -f "$HOME_DIR/.env" ]]; then
  key="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"
  cat > "$HOME_DIR/.env" <<EOF
SM_SECRET_KEY=$key
SM_DB_NAME=$DB
SM_STATIC_ROOT=$HOME_DIR/static
SM_DATA_DIR=$HOME_DIR/data
SM_ALLOWED_HOSTS=softmontazh.kz,www.softmontazh.kz,127.0.0.1,localhost
PYTHONDONTWRITEBYTECODE=1
EOF
  echo "Создан $HOME_DIR/.env"
else
  echo "$HOME_DIR/.env уже есть — не трогаю."
fi
chown "$U:$U" "$HOME_DIR/.env"; chmod 600 "$HOME_DIR/.env"

say "4/8 Python-окружение"
python3 -c 'import venv, ensurepip' 2>/dev/null || apt-get install -y python3-venv
[[ -x "$HOME_DIR/venv/bin/python" ]] || sudo -u "$U" python3 -m venv "$HOME_DIR/venv"
sudo -u "$U" "$HOME_DIR/venv/bin/pip" install -q --upgrade pip
sudo -u "$U" "$HOME_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
sha256sum "$APP_DIR/requirements.txt" | cut -d' ' -f1 > "$HOME_DIR/.req-hash"
install -m 755 "$SITE_DIR/deploy/softmontazh-manage" /usr/local/bin/softmontazh-manage

say "5/8 Миграции и статика"
softmontazh-manage migrate --noinput
softmontazh-manage collectstatic --noinput -v0

say "6/8 Сервис"
install -m 644 "$SITE_DIR/deploy/softmontazh.service" /etc/systemd/system/softmontazh.service
systemctl daemon-reload
systemctl enable --now softmontazh.service
systemctl restart softmontazh.service
sleep 3
if curl -fsS -o /dev/null http://127.0.0.1:8002/api/catalog/menu; then echo "Сервис отвечает на 127.0.0.1:8002."; else
  echo "Сервис не отвечает. Журнал: journalctl -u softmontazh -n 50" >&2; exit 1; fi

say "7/8 Расписание"
install -m 644 "$SITE_DIR/deploy/softmontazh-catalog.cron" /etc/cron.d/softmontazh-catalog
echo "Загрузка из Barlau — каждые 6 часов, бэкап базы — каждую ночь (хранится 7)."

say "8/8 Первая загрузка каталога (1–2 минуты)"
nice -n 10 softmontazh-manage import_barlau || echo "Загрузка не удалась — см. сообщение выше. Повторить: sudo softmontazh-manage import_barlau" >&2

if ! softmontazh-manage shell -c "from django.contrib.auth.models import User; import sys; sys.exit(0 if User.objects.filter(is_superuser=True).exists() else 1)" 2>/dev/null; then
  if [[ -t 0 ]]; then
    echo -e "\nЗаведите вход в админку (логин, почта можно пропустить, пароль):"
    softmontazh-manage createsuperuser
  else
    echo "Вход в админку ещё не заведён: sudo softmontazh-manage createsuperuser"
  fi
fi

echo -e "\nГотово. Каталог: https://softmontazh.kz/catalog/   Админка: https://softmontazh.kz/admin/"
echo "Дальше сайт и каталог обновляются одной командой: sudo bash $SITE_DIR/deploy/update.sh"
