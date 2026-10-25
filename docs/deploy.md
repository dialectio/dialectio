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

Заповни також `IMPRINT_NAME`, `IMPRINT_ADDRESS` (рядки розділяй `
`) та `IMPRINT_EMAIL`: це сторінка Impressum (`/imprint`). Для сайту з німецькою версією й рекламою вона обов'язкова за §5 DDG. Ці дані лишаються лише на сервері, у git їх немає.

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

Вхід через Google: у [Google Cloud Console](https://console.cloud.google.com/apis/credentials) (акаунт dialectio.team@gmail.com) у клієнті OAuth додати redirect URI `https://<домен>/api/auth/google/callback`, на екрані згоди вказати домен і опублікувати застосунок (Publish app), а `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` вписати в `.env.prod`.

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

Щодня о 3:00 у `backups/` зберігаються дампи обох баз і архів аудіо за 14 днів. Бекап на тому ж сервері не захищає від втрати сервера, тому копії варто відправляти ще й деінде:

1. Замовити **Hetzner Storage Box** (BX11, ~3,5 €/міс, 1 ТБ) і в його налаштуваннях увімкнути SSH.
2. На сервері створити ключ і додати його до Storage Box:
   ```bash
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
   cat ~/.ssh/id_ed25519.pub | ssh -p 23 u123456@u123456.your-storagebox.de install-ssh-key
   ```
3. У `.env.prod` вписати `BACKUP_REMOTE=u123456@u123456.your-storagebox.de:dialectio`.
4. Перевірити: `deploy/backup.sh` — наприкінці має з'явитися `copied to ...`.

Додатково можна ввімкнути **Backups** у Hetzner Cloud (+20 % ціни сервера): це знімок усього сервера.

## 7. Моніторинг

[UptimeRobot](https://uptimerobot.com) (безкоштовно, 50 перевірок): додати HTTP-монітор на `https://<домен>/health` з інтервалом 5 хвилин і сповіщенням на email чи в Telegram. Адреса `/health` перевіряє і API, і базу: якщо щось ляже, прийде лист.

Щотижневий звіт на пошту проєкту (`REPORT_TO`, за замовчуванням dialectio.team@gmail.com): трафік з Umami, пошуки без результату, спільнота, що чекає на перевірку, диск. Запуск щопонеділка о 9:00 за Києвом:

```bash
cat > /etc/cron.d/dialectio-report <<'CRON'
CRON_TZ=Europe/Kyiv
0 9 * * 1 root cd /srv/dialectio && docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T backend python -m app.report >> /var/log/dialectio-report.log 2>&1
CRON
```

Перевірити вручну: `$COMPOSE exec backend python -m app.report --print` (без листа) або без `--print` (з листом).

## 8. Пошукові системи

1. [Google Search Console](https://search.google.com/search-console): додати домен (підтвердження через DNS-запис TXT), надіслати `https://<домен>/sitemap.xml`.
2. [Bing Webmaster Tools](https://www.bing.com/webmasters): імпортувати сайт із Search Console.

## Оновлення сайту

```bash
cd /srv/dialectio && git pull
$COMPOSE run --rm backend alembic upgrade head   # якщо є нові міграції
$COMPOSE up -d --build
```

Нові слова й чернетки, додані локально, переносяться так само, як у кроці 3. Але такий дамп **замінює** базу на сервері, тож внески відвідувачів, зроблені на сайті, буде втрачено. Коли сайт запрацює, редагувати варто на самому сайті (`/uk/editor`), а локальну базу вважати копією.
