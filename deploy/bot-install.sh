#!/usr/bin/env bash
# Софтмонтаж — подключение Telegram-бота @sm_salebot (разово; повторный запуск — сменить токен).
#   sudo bash /var/www/softmontazh.kz/deploy/bot-install.sh
# Токен вводится скрыто, пишется только в /opt/softmontazh/.env (права 600), на экран и в журналы не выводится.
set -euo pipefail
SITE_DIR="/var/www/softmontazh.kz"; ENV="/opt/softmontazh/.env"
[[ $EUID -eq 0 ]] || { echo "Запустите через sudo" >&2; exit 1; }
[[ -f "$ENV" ]] || { echo "Сначала установите каталог: deploy/catalog-install.sh" >&2; exit 1; }

setenv() {  # setenv KEY VALUE — заменить или добавить строку в .env
  local k="$1" v="$2"
  if grep -q "^$k=" "$ENV"; then sed -i "s|^$k=.*|$k=$v|" "$ENV"; else echo "$k=$v" >> "$ENV"; fi
}

echo "Токен бота из @BotFather (ввод не отображается):"
read -rs TOKEN; echo
[[ "$TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]] || { echo "Это не похоже на токен бота." >&2; exit 1; }
setenv BOT_TOKEN "$TOKEN"; unset TOKEN
setenv BOT_USERNAME "sm_salebot"
setenv BOT_MODE "webhook"
setenv BOT_PORT "8003"
setenv BOT_WEBHOOK_BASE "https://softmontazh.kz"
grep -q "^BOT_WEBHOOK_SECRET=" "$ENV" || setenv BOT_WEBHOOK_SECRET "$(python3 -c 'import secrets;print(secrets.token_hex(24))')"
grep -q "^BOT_WEBHOOK_PATH=" "$ENV" || setenv BOT_WEBHOOK_PATH "$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')"
chmod 600 "$ENV"; chown softmontazh:softmontazh "$ENV"

install -m 644 "$SITE_DIR/deploy/softmontazh-bot.service" /etc/systemd/system/softmontazh-bot.service
systemctl daemon-reload
systemctl enable softmontazh-bot >/dev/null
systemctl restart softmontazh softmontazh-bot
sleep 4
if systemctl is-active --quiet softmontazh-bot; then
  journalctl -u softmontazh-bot -n 5 --no-pager | grep -E "запущен|ERROR|Error" || true
  echo
  echo "Бот работает. Дальше:"
  echo "  1) Добавьте @sm_salebot в группу менеджеров и сделайте админом (чтобы мог убирать уволенных)."
  echo "  2) На сайте: Кабинет → «Код для группы» → отправьте в группе /bind КОД."
  echo "  3) Каждый менеджер: Кабинет → «Подключить Telegram»."
else
  echo "Бот не запустился. Журнал:" >&2
  journalctl -u softmontazh-bot -n 30 --no-pager >&2
  exit 1
fi
