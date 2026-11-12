# Софтмонтаж — сайт softmontazh.kz

Статический сайт ТОО «Софтмонтаж» (слаботочные системы, Караганда). Без сборки и фреймворков: HTML + CSS + немного JS.

## Структура
```
index.html, services.html, certificates.html, contact.html   страницы
assets/css/site.css     стили сайта
assets/js/site.js       общие шапка и подвал (меню, телефон, ссылки правятся здесь), мобильное меню, копирование реквизитов, просмотр сертификатов
assets/certificates/    сертификаты в WebP (полный размер и превью)
assets/img/             значок платформы Esemer
brand/                  фирменный стиль: логотипы, фавиконы, значки разделов, превью для соцсетей, colors.css (см. brand/README.md)
sitemap.xml, robots.txt
```

## Как править
- Пункты меню, телефон, WhatsApp, ссылки — в начале `assets/js/site.js`.
- Цвета — `brand/site/colors.css`, вёрстка — `assets/css/site.css`.
- Новый сертификат: положить `<имя>.webp` и `<имя>-thumb.webp` в `assets/certificates/` и добавить карточку в `certificates.html`.

Сайт открывается и локально (двойной клик по index.html), и на хостинге.

## Деплой (сервер)
Сайт лежит на VPS вместе с esemer.kz: папка `/var/www/softmontazh.kz` — клон этого репозитория (ветка `main`), nginx отдаёт статику.

Обновить сайт после изменений в GitHub (main):
```
sudo bash /var/www/softmontazh.kz/deploy/update.sh
```
Вернуть предыдущую версию:
```
sudo bash /var/www/softmontazh.kz/deploy/update.sh --rollback
```
- Журнал версий: `/var/www/softmontazh-releases.log` (дата · было · стало).
- Конфиг nginx хранится в `deploy/nginx.conf`; скрипт сам ставит его, если он изменился (с копией старого и проверкой `nginx -t`).
- Наружу не отдаются: `.git`, `*.md`, `*.sh`, `deploy/`, `VERSION`.
- Кэш: страницы — `no-cache`, css/js/картинки — 30 дней. После правки css/js увеличить `?v=N` в ссылках на всех страницах.
- Ограничения: сайт до ~50 МБ, картинки в WebP, видео в репозиторий не класть.
