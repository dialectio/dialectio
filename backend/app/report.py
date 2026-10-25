"""The weekly report to the project mailbox: traffic, search wishes, community, server.

    python -m app.report              # the last 7 days, emailed to REPORT_TO
    python -m app.report --days 30 --print   # print instead of emailing

On the server it runs from cron every Monday (see docs/deploy.md). Traffic comes from Umami's
database (same PostgreSQL server, database "umami"); without it, that part is skipped.
"""

import argparse
import shutil
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app import mail
from app.config import MEDIA_DIR, settings
from app.db.session import SessionLocal

TOP = 10

COMMUNITY = text("""
    SELECT
      (SELECT count(*) FROM app_user) AS members,
      (SELECT count(*) FROM app_user WHERE created_at > :since) AS new_members,
      (SELECT count(*) FROM vote WHERE created_at > :since) AS votes,
      (SELECT count(DISTINCT voter) FROM vote WHERE created_at > :since) AS voters,
      (SELECT count(*) FROM gold_answer WHERE created_at > :since) AS control_answers,
      (SELECT count(*) FROM speaker_test WHERE passed AND started_at > :since) AS tests_passed,
      (SELECT count(*) FROM speaker_test WHERE started_at > :since) AS tests,
      (SELECT count(*) FROM form WHERE status = 'submitted') AS submissions_waiting,
      (SELECT count(*) FROM report WHERE NOT resolved) AS open_reports,
      (SELECT count(*) FROM expert_role WHERE status = 'applied') AS applications,
      (SELECT count(*) FROM expert_role WHERE status = 'expert') AS experts,
      (SELECT count(*) FROM form_change WHERE created_at > :since) AS word_changes,
      pg_size_pretty(pg_database_size(current_database())) AS database_size
""")

MISSING = text("""
    SELECT query, count FROM missing_search WHERE last_seen > :since
    ORDER BY count DESC, last_seen DESC LIMIT :top
""")

PAGEVIEWS = text("""
    SELECT count(*) AS views, count(DISTINCT session_id) AS visitors
    FROM website_event WHERE event_type = 1 AND created_at > :since
""")
TOP_PAGES = text("""
    SELECT url_path, count(*) AS views FROM website_event
    WHERE event_type = 1 AND created_at > :since
    GROUP BY url_path ORDER BY views DESC LIMIT :top
""")
COUNTRIES = text("""
    SELECT coalesce(s.country, '?') AS country, count(DISTINCT e.session_id) AS visitors
    FROM website_event e JOIN session s ON s.session_id = e.session_id
    WHERE e.event_type = 1 AND e.created_at > :since
    GROUP BY 1 ORDER BY visitors DESC LIMIT :top
""")
REFERRERS = text("""
    SELECT referrer_domain, count(DISTINCT session_id) AS visitors FROM website_event
    WHERE event_type = 1 AND created_at > :since AND referrer_domain IS NOT NULL
      AND referrer_domain <> '' AND referrer_domain NOT LIKE '%dialectio.org'
    GROUP BY 1 ORDER BY visitors DESC LIMIT :top
""")
LOCALES = text("""
    SELECT split_part(url_path, '/', 2) AS locale, count(*) AS views FROM website_event
    WHERE event_type = 1 AND created_at > :since
    GROUP BY 1 ORDER BY views DESC
""")


def table(rows: list, empty: str = "  —") -> list[str]:
    return [f"  {a}: {b}" for a, b in rows] or [empty]


def traffic(since: datetime) -> list[str]:
    url = make_url(settings.database_url).set(database="umami")
    engine = create_engine(url, pool_pre_ping=True)
    params = {"since": since, "top": TOP}
    try:
        with engine.connect() as db:
            totals = db.execute(PAGEVIEWS, params).one()
            pages = db.execute(TOP_PAGES, params).all()
            countries = db.execute(COUNTRIES, params).all()
            referrers = db.execute(REFERRERS, params).all()
            locales = db.execute(LOCALES, params).all()
    except SQLAlchemyError as error:
        return ["ТРАФІК", f"  (Umami недоступний: {type(error).__name__})", ""]
    finally:
        engine.dispose()
    return [
        "ТРАФІК (Umami)",
        f"  Переглядів: {totals.views}, відвідувачів: {totals.visitors}",
        "  За мовою сайту: "
        + (", ".join(f"/{loc or '-'} {views}" for loc, views in locales) or "—"),
        "",
        "Найпопулярніші сторінки:",
        *table(pages),
        "",
        "Країни (відвідувачі):",
        *table(countries),
        "",
        "Звідки прийшли (відвідувачі):",
        *table(referrers),
        "",
    ]


def build(days: int) -> tuple[str, str]:
    """The report's subject and text."""
    now = datetime.now(UTC)
    since = now - timedelta(days=days)
    params = {"since": since, "top": TOP}
    with SessionLocal() as session:
        c = session.execute(COMMUNITY, params).mappings().one()
        missing = session.execute(MISSING, params).all()
    disk = shutil.disk_usage(MEDIA_DIR if MEDIA_DIR.exists() else "/")
    lines = [
        f"Dialectio, {since:%d.%m}–{now:%d.%m.%Y} ({days} дн.)",
        "",
        *traffic(since),
        "ШУКАЛИ Й НЕ ЗНАЙШЛИ (додати ці слова?)",
        *table(missing),
        "",
        "СПІЛЬНОТА",
        f"  Учасників: {c['members']} (+{c['new_members']})",
        f"  Голосів: {c['votes']} від {c['voters']} людей; "
        f"контрольних відповідей: {c['control_answers']}",
        f"  Тести носія: пройдено {c['tests_passed']} з {c['tests']}",
        f"  Чекають на перевірку: надісланих слів {c['submissions_waiting']}, "
        f"повідомлень про помилки {c['open_reports']}, заявок експертів {c['applications']}",
        f"  Експертів: {c['experts']}; змін слів редакцією й експертами: {c['word_changes']}",
        "",
        "СЕРВЕР",
        f"  База: {c['database_size']}; вільно на диску {disk.free / 2**30:.1f} "
        f"з {disk.total / 2**30:.1f} ГБ",
        "",
        "Пошуковики: https://search.google.com/search-console і https://www.bing.com/webmasters",
        "Статистика: https://stats.dialectio.org",
    ]
    attention = c["submissions_waiting"] + c["open_reports"] + c["applications"]
    waiting = f" ({attention} чекають на перевірку)" if attention else ""
    subject = f"Dialectio: звіт за тиждень{waiting}"
    return subject, "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--print", action="store_true", help="print instead of emailing")
    args = parser.parse_args()
    subject, body = build(args.days)
    if args.print:
        print(subject, body, sep="\n\n")
        return
    if not mail.deliver(settings.report_to, subject, body, None, "report"):
        sys.exit(1)


if __name__ == "__main__":
    main()
