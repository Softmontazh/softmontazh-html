#!/usr/bin/env bash
# Софтмонтаж — обновление сайта softmontazh.kz на сервере.
#
#   sudo bash /var/www/softmontazh.kz/deploy/update.sh             обновить до последней версии из GitHub (main)
#   sudo bash /var/www/softmontazh.kz/deploy/update.sh --rollback  вернуть версию, которая была до последнего обновления
#
# Что делает:
#   1) git fetch + git reset --hard origin/main (от пользователя ubuntu) в /var/www/softmontazh.kz;
#   2) пишет строку в журнал /var/www/softmontazh-releases.log (вне папки сайта);
#   3) пишет файл VERSION (дата · короткий хеш), наружу он не отдаётся;
#   4) если deploy/nginx.conf отличается от /etc/nginx/sites-available/softmontazh.kz —
#      ставит новый конфиг (старый сохраняет рядом как .bak-ДАТА), проверяет nginx -t и перезагружает nginx;
#      если проверка не прошла — возвращает старый конфиг и nginx не трогает.
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

write_version() {
  local short; short="$(g rev-parse --short HEAD)"
  echo "$(now) · $short" > "$SITE_DIR/VERSION"
  chown "$SITE_USER":"$SITE_USER" "$SITE_DIR/VERSION" 2>/dev/null || true
  echo "Работает версия: $(g log -1 --format='%h · %ad · %s' --date=format:'%d.%m.%Y %H:%M')"
}

before="$(g rev-parse HEAD)"

if [[ "${1:-}" == "--rollback" ]]; then
  if [[ ! -s "$LOG" ]]; then
    echo "Журнал $LOG пуст — откатывать не к чему." >&2
    exit 1
  fi
  target="$(tail -n 1 "$LOG" | sed -n 's/.*было \([0-9a-f]\{7,40\}\).*/\1/p')"
  if [[ -z "$target" ]]; then
    echo "Не нашёл хеш в последней строке журнала:" >&2
    tail -n 1 "$LOG" >&2
    exit 1
  fi
  echo "Откат: $(g rev-parse --short HEAD) → ${target:0:7}"
  g reset --hard "$target"
  echo "$(now) · было $before · стало $(g rev-parse HEAD) · откат" >> "$LOG"
  apply_nginx || true
  write_version
  exit 0
fi

echo "Обновление сайта из GitHub ($BRANCH)…"
g fetch --quiet origin "$BRANCH"
g reset --hard "origin/$BRANCH"
after="$(g rev-parse HEAD)"

if [[ "$before" == "$after" ]]; then
  echo "Новых изменений нет."
else
  echo "$(now) · было $before · стало $after · обновление" >> "$LOG"
fi

apply_nginx || echo "Внимание: сайт обновлён, но новый конфиг nginx не применён (см. ошибку выше)." >&2
write_version
