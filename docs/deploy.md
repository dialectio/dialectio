# Деплой на Hetzner

Увесь сайт працює на одному сервері в Docker: база (PostGIS), API, сайт (Next.js), статистика (Umami) і Caddy, який сам отримує HTTPS-сертифікати.

```
https://<домен>/          → сайт
https://<домен>/api/...   → API
https://<домен>/media/... → аудіо (TTS і записи відвідувачів)
https://stats.<домен>/    → статистика Umami
```

Конфігурацію перевірено локально (10.2026): production-образи, HTTPS через Caddy, перенесення бази з дампу, карта й аудіо в браузері. Скрипт бекапу (`deploy/backup.sh`) локально не запускався: він для Linux-сервера.

## 1. Сервер і домен (робиш ти)

1. Hetzner Cloud → новий сервер: **CX22** (2 vCPU, 4 ГБ RAM, ~4 €/міс) або **CAX11** (ARM, дешевший), образ **Ubuntu 24.04**, додати свій SSH-ключ.
2. Купити домен. У DNS додати записи `A` на IP сервера для:
   - `@` (сам домен);
   - `www`;
   - `stats`.
3. Зачекати, поки DNS оновиться (зазвичай 5–30 хв): `ping <домен>` має показувати IP сервера.

## 2. Підготовка сервера

```bash
ssh root@<IP>
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
mkdir -p /srv && cd /srv
git clone https://github.com/gmisha777/dialectio.git
cd dialectio
cp .env.prod.example .env.prod
nano .env.prod   # домен, паролі (див. нижче)
```

Паролі й секрети в `.env.prod` — випадкові рядки, наприклад з `openssl rand -base64 24`. `EDITOR_TOKEN` — новий, не той, що локально.

## 3. Перенесення даних з комп'ютера

База і аудіо не лежать у git, їх треба скопіювати.

На своєму комп'ютері (PowerShell, з теки проєкту):

```powershell
docker compose exec -T db pg_dump -U dialectio -Fc -f /tmp/dialectio.dump dialectio
docker compose cp db:/tmp/dialectio.dump dialectio.dump
scp dialectio.dump root@<IP>:/srv/dialectio/
scp -r data/media root@<IP>:/srv/dialectio/data/
```

## 4. Запуск

На сервері:

```bash
cd /srv/dialectio
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"
$COMPOSE up -d db
deploy/restore-db.sh dialectio.dump     # наприкінці покаже кількість слів
$COMPOSE run --rm backend alembic upgrade head
$COMPOSE up -d --build
```

Перевірити: `https://<домен>/uk` відкривається, `https://<домен>/health` повертає `{"status":"ok"}`.

## 5. Статистика (Umami)

1. Відкрити `https://stats.<домен>`, увійти як `admin` / `umami` і **одразу змінити пароль** (Settings → Profile).
2. Settings → Websites → Add website: назва Dialectio, домен `<домен>`. Скопіювати Website ID.
3. Вписати його в `.env.prod` (`UMAMI_WEBSITE_ID=...`, `UMAMI_SRC=https://stats.<домен>/script.js`) і перезібрати сайт:
   `$COMPOSE up -d --build frontend`

## 6. Бекапи

```bash
crontab -e
# додати рядок:
0 3 * * * /srv/dialectio/deploy/backup.sh >> /srv/dialectio/backups/backup.log 2>&1
```

Щодня о 3:00 у `backups/` зберігаються дампи обох баз і архів аудіо за 14 днів. Бекап на тому ж сервері не захищає від втрати сервера, тож варто:
- увімкнути **Backups** у Hetzner Cloud (+20 % ціни сервера);
- або раз на тиждень копіювати `backups/` до себе (`scp -r root@<IP>:/srv/dialectio/backups .`).

## 7. Пошукові системи

1. [Google Search Console](https://search.google.com/search-console): додати домен (підтвердження через DNS-запис TXT), надіслати `https://<домен>/sitemap.xml`.
2. [Bing Webmaster Tools](https://www.bing.com/webmasters): імпортувати сайт із Search Console.

## Оновлення сайту

```bash
cd /srv/dialectio && git pull
$COMPOSE run --rm backend alembic upgrade head   # якщо є нові міграції
$COMPOSE up -d --build
```

Нові слова й чернетки, додані локально, переносяться так само, як у кроці 3. Але такий дамп **замінює** базу на сервері, тож внески відвідувачів, зроблені на сайті, буде втрачено. Коли сайт запрацює, редагувати варто на самому сайті (`/uk/editor`), а локальну базу вважати копією.
