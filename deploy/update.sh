#!/usr/bin/env bash
# Софтмонтаж — обновление сайта softmontazh.kz на сервере.
#
#   sudo bash /var/www/softmontazh.kz/deploy/update.sh             обновить до последней версии из GitHub (main)
#   sudo bash /var/www/softmontazh.kz/deploy/update.sh --rollback  вернуть версию, которая была до последнего обновления
#
# Версия — дата коммита и короткий хеш: «2026.11.17 · 8025f48» (как у платформы Esemer). Видна в выводе скрипта и в админке.
#
# Что делает:
#   1) git fetch + git reset --hard origin/main (от пользователя ubuntu) в /var/www/softmontazh.kz;
#   2) пишет файл VERSION (наружу не отдаётся, в git не попадает);
#   3) пишет строку в журнал /var/www/softmontazh-releases.log: «дата · было <хеш> · стало <хеш> · копия базы»;
#   4) если deploy/nginx.conf отличается от /etc/nginx/sites-available/softmontazh.kz —
#      ставит новый конфиг (старый сохраняет рядом как .bak-ДАТА), проверяет nginx -t и перезагружает nginx;
#      если проверка не прошла — возвращает старый конфиг и nginx не трогает;
#   5) каталог (если установлен deploy/catalog-install.sh): бэкап базы → зависимости (если менялись) →
#      миграции → статика админки → перезапуск сервиса softmontazh → проверка, что отвечает.
#
# Откат (--rollback): только сразу после обновления (второй откат подряд запрещён — следующий update.sh вернёт свежую версию).
#   Если в обновлении не было миграций базы — возвращается только код.
#   Если были — скрипт предупредит, что данные, внесённые после обновления, пропадут, спросит «да»,
#   остановит каталог и восстановит базу из копии, сделанной перед обновлением; миграции назад не крутим.
set -euo pipefail

SITE_DIR="/var/www/softmontazh.kz"
SITE_USER="ubuntu"
BRANCH="main"
LOG="/var/www/softmontazh-releases.log"
NGINX_SRC="$SITE_DIR/deploy/nginx.conf"
NGINX_DST="/etc/nginx/sites-available/softmontazh.kz"

# Скрипт лежит внутри репозитория, а git reset его заменяет — поэтому работаем из копии во /tmp.
if [[ "${SM_UPDATE_COPY:-}" != "1" ]]; then
  tmp="$(mktemp /tmp/softmontazh-update.XXXXXX.sh)"
  cp "$0" "$tmp"
  SM_UPDATE_COPY=1 exec bash "$tmp" "$@"
fi
trap 'rm -f "$0"' EXIT

if [[ $EUID -ne 0 ]]; then
  echo "Запустите через sudo: sudo bash $SITE_DIR/deploy/update.sh" >&2
  exit 1
fi

g() { sudo -u "$SITE_USER" git -C "$SITE_DIR" "$@"; }
now() { date '+%Y-%m-%d %H:%M'; }

apply_nginx() {
  if [[ ! -f "$NGINX_SRC" ]]; then
    echo "nginx: в репозитории нет deploy/nginx.conf — конфиг не трогаю."
    return 0
  fi
  if [[ -f "$NGINX_DST" ]] && cmp -s "$NGINX_SRC" "$NGINX_DST"; then
    echo "nginx: конфиг не менялся."
    return 0
  fi
  local bak="$NGINX_DST.bak-$(date '+%Y%m%d-%H%M%S')"
  [[ -f "$NGINX_DST" ]] && cp -p "$NGINX_DST" "$bak"
  cp "$NGINX_SRC" "$NGINX_DST"
  ln -sf "$NGINX_DST" /etc/nginx/sites-enabled/softmontazh.kz
  if nginx -t; then
    systemctl reload nginx
    echo "nginx: новый конфиг установлен и применён (старый — $bak)."
  else
    echo "nginx: ОШИБКА в новом конфиге — возвращаю прежний, nginx не перезагружаю." >&2
    if [[ -f "$bak" ]]; then cp -p "$bak" "$NGINX_DST"; else rm -f "$NGINX_DST"; fi
    nginx -t || true
    return 1
  fi
}

# --- каталог (Django) ---
CAT_HOME="/opt/softmontazh"

apply_catalog() {
  if [[ ! -x "$CAT_HOME/venv/bin/python" ]]; then
    if [[ -f "$SITE_DIR/app/manage.py" ]]; then
      echo "Каталог: ещё не установлен — один раз выполните: sudo bash $SITE_DIR/deploy/catalog-install.sh"
    fi
    return 0
  fi
  echo "Каталог: обновляю…"
  local ts; ts="$(date '+%Y%m%d-%H%M%S')"
  if [[ "${SKIP_DUMP:-}" != "1" ]]; then
    DUMP="$CAT_HOME/backups/pre-update-$ts.dump"
    sudo -u softmontazh pg_dump -Fc softmontazh > "$DUMP" && chown softmontazh: "$DUMP"
  fi
  ls -1t "$CAT_HOME"/backups/pre-update-*.dump 2>/dev/null | tail -n +11 | xargs -r rm -f
  local h; h="$(sha256sum "$SITE_DIR/app/requirements.txt" | cut -d' ' -f1)"
  if [[ "$h" != "$(cat "$CAT_HOME/.req-hash" 2>/dev/null)" ]]; then
    sudo -u softmontazh "$CAT_HOME/venv/bin/pip" install -q -r "$SITE_DIR/app/requirements.txt" && echo "$h" > "$CAT_HOME/.req-hash"
  fi
  install -m 755 "$SITE_DIR/deploy/softmontazh-manage" /usr/local/bin/softmontazh-manage
  install -d -o softmontazh -g softmontazh -m 755 "$CAT_HOME/media"
  if ! cmp -s "$SITE_DIR/deploy/softmontazh.service" /etc/systemd/system/softmontazh.service; then
    install -m 644 "$SITE_DIR/deploy/softmontazh.service" /etc/systemd/system/softmontazh.service && systemctl daemon-reload
  fi
  cmp -s "$SITE_DIR/deploy/softmontazh-catalog.cron" /etc/cron.d/softmontazh-catalog || install -m 644 "$SITE_DIR/deploy/softmontazh-catalog.cron" /etc/cron.d/softmontazh-catalog
  softmontazh-manage migrate --noinput
  softmontazh-manage collectstatic --noinput -v0
  systemctl restart softmontazh
  if [[ -f /etc/systemd/system/softmontazh-bot.service ]]; then
    if ! cmp -s "$SITE_DIR/deploy/softmontazh-bot.service" /etc/systemd/system/softmontazh-bot.service; then
      install -m 644 "$SITE_DIR/deploy/softmontazh-bot.service" /etc/systemd/system/softmontazh-bot.service && systemctl daemon-reload
    fi
    systemctl restart softmontazh-bot && echo "Бот @sm_salebot: перезапущен (webhook ставится заново)."
  fi
  sleep 3
  if curl -fsS -o /dev/null http://127.0.0.1:8002/api/catalog/menu; then
    CATALOG_OK=1
    echo "Каталог: работает${DUMP:+ (копия базы перед обновлением — $DUMP)}."
  else
    echo "Каталог: НЕ ОТВЕЧАЕТ после обновления. Журнал: journalctl -u softmontazh -n 50. Откат: sudo bash $SITE_DIR/deploy/update.sh --rollback" >&2
    return 1
  fi
}

write_version() {
  g log -1 --format='%cd · %h' --date=format:'%Y.%m.%d' > "$SITE_DIR/VERSION"
  chown "$SITE_USER":"$SITE_USER" "$SITE_DIR/VERSION" 2>/dev/null || true
}

finish() {
  local v; v="$(cat "$SITE_DIR/VERSION")"
  if [[ ! -x "$CAT_HOME/venv/bin/python" || "${CATALOG_OK:-}" == "1" ]]; then
    echo "Работает версия: $v"
  else
    echo "Версия $v — код на месте, но каталог не отвечает. Последние строки журнала сервиса:" >&2
    journalctl -u softmontazh -n 30 --no-pager >&2 || true
    exit 1
  fi
}

DUMP=""; CATALOG_OK=""
before="$(g rev-parse HEAD)"

if [[ "${1:-}" == "--rollback" ]]; then
  if [[ ! -s "$LOG" ]]; then
    echo "Журнал $LOG пуст — откатывать не к чему." >&2
    exit 1
  fi
  last="$(tail -n 1 "$LOG")"
  if [[ "$last" == *"· откат"* ]]; then
    echo "Последнее действие уже было откатом. Второй откат подряд не делаю — чтобы вернуть свежую версию, запустите обычное обновление." >&2
    exit 1
  fi
  target="$(sed -n 's/.*было \([0-9a-f]\{7,40\}\).*/\1/p' <<<"$last")"
  from="$(sed -n 's/.*стало \([0-9a-f]\{7,40\}\).*/\1/p' <<<"$last")"
  dump="$(sed -n 's/.*копия базы \(\/[^ ]*\.dump\).*/\1/p' <<<"$last")"
  if [[ -z "$target" ]]; then
    echo "Не нашёл хеш в последней строке журнала:" >&2; echo "$last" >&2; exit 1
  fi
  echo "Откат: $(g rev-parse --short HEAD) → ${target:0:7}"
  migs="$(g diff --name-only "$target" "${from:-HEAD}" -- 'app/*/migrations/*.py' || true)"
  if [[ -n "$migs" && -x "$CAT_HOME/venv/bin/python" ]]; then
    echo "В этом обновлении менялась база каталога:"; echo "$migs" | sed 's/^/  /'
    if [[ -z "$dump" || ! -f "$dump" ]]; then
      echo "Копии базы перед обновлением не нашёл — откатить безопасно нельзя. Код не трогаю." >&2; exit 1
    fi
    echo "База будет восстановлена из копии $dump."
    echo "Всё, что изменили в каталоге и админке ПОСЛЕ обновления (наценки, скидки, правки товаров), пропадёт;"
    echo "цены и остатки Barlau подтянутся сами при следующей загрузке."
    read -r -p "Откатить? Напишите «да»: " ans
    if [[ "$ans" != "да" ]]; then echo "Отменено."; exit 1; fi
    systemctl stop softmontazh
    sudo -u softmontazh pg_restore --clean --if-exists --no-owner -d softmontazh "$dump" || echo "pg_restore: были предупреждения — обычно не страшно, проверьте каталог."
    echo "База восстановлена."
  fi
  g reset --hard "$target"
  write_version
  echo "$(now) · было $before · стало $(g rev-parse HEAD) · откат" >> "$LOG"
  apply_nginx || true
  SKIP_DUMP=1 apply_catalog || true
  finish
  exit 0
fi

echo "Обновление сайта из GitHub ($BRANCH)…"
g fetch --quiet origin "$BRANCH"
g reset --hard "origin/$BRANCH"
after="$(g rev-parse HEAD)"
write_version

apply_nginx || echo "Внимание: сайт обновлён, но новый конфиг nginx не применён (см. ошибку выше)." >&2
apply_catalog || echo "Внимание: сайт обновлён, но каталог после обновления не отвечает (см. выше)." >&2

if [[ "$before" == "$after" ]]; then
  echo "Новых изменений нет."
else
  echo "$(now) · было $before · стало $after · копия базы ${DUMP:-нет}" >> "$LOG"
fi
finish
