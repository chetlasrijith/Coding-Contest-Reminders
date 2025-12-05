# src/scheduler_main.py
import os
import time
from datetime import timedelta, datetime
import pytz

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

from .config import TIMEZONE
from .helpers import read_contests
from .whatsaap_api import send_template
from .fetchers import fetch_all

CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "contests.csv")

# track scheduled job ids to prevent duplicates
SCHEDULED_KEYS = set()

def make_job_id(platform, title, start_dt, phone):
    return f"{platform}__{title}__{int(start_dt.timestamp())}__{phone}"

def schedule_event(scheduler, platform, title, start_dt, phone, tzinfo):
    remind_dt = start_dt - timedelta(minutes=5)
    # ensure timezone-aware
    if remind_dt.tzinfo is None:
        remind_dt = tzinfo.localize(remind_dt)
    now = datetime.now(tzinfo)
    if remind_dt <= now:
        print(f"[SKIP] {platform} - {title} remind time {remind_dt} already passed (now={now})")
        return
    job_id = make_job_id(platform, title, remind_dt, phone)
    if job_id in SCHEDULED_KEYS:
        # already scheduled
        return
    def job():
        pretty = start_dt.astimezone(tzinfo).strftime("%Y-%m-%d %H:%M %Z")
        body_title = f"{platform}: {title}"
        send_template(phone, body_title, pretty)
        # optionally remove from set after sending
        SCHEDULED_KEYS.discard(job_id)
    try:
        scheduler.add_job(job, 'date', run_date=remind_dt, id=job_id)
        SCHEDULED_KEYS.add(job_id)
        print(f"[SCHEDULED] {platform} - '{title}' at {remind_dt.isoformat()} -> {phone}")
    except Exception as e:
        print("[ERR] schedule_event:", e)

def schedule_from_fetcher(scheduler, tz, upcoming_hours=72, default_phone=None):
    # fetch events
    events = fetch_all(upcoming_within_hours=upcoming_hours)
    for ev in events:
        platform = ev.get("platform")
        title = ev.get("title")
        start_dt = ev.get("start_dt")
        url = ev.get("url")
        phone = default_phone or os.getenv("DEFAULT_PHONE")
        if not phone:
            # fallback: if contests.csv has a phone, use that — read first row
            try:
                for r in read_contests(CSV_PATH):
                    phone = r["phone"]
                    break
            except Exception:
                phone = None
        if not phone:
            print("[WARN] No phone number configured (set DEFAULT_PHONE in .env or put phone in contests.csv). Skipping.")
            return
        # normalize start_dt
        if start_dt.tzinfo is None:
            start_dt = tz.localize(start_dt)
        else:
            # keep aware but convert to tz for scheduling
            start_dt = start_dt.astimezone(tz)
        schedule_event(scheduler, platform, title, start_dt, phone, tz)

def get_default_phone():
    # prefer explicit env var, fallback to first phone in CSV
    phone = os.getenv("DEFAULT_PHONE")
    if phone:
        return phone
    try:
        for r in read_contests(CSV_PATH):
            p = r.get("phone")
            if p:
                return p
    except Exception:
        pass
    return None

def main():
    tz = pytz.timezone(TIMEZONE)
    executors = {'default': ThreadPoolExecutor(10)}
    scheduler = BackgroundScheduler(executors=executors, timezone=tz)
    scheduler.start()
    print("[STARTED] Scheduler (auto-fetch)")

    # initial scheduling from CSV (optional)
    if os.path.exists(CSV_PATH):
        for ev in read_contests(CSV_PATH):
            title = ev["title"]
            start_dt = ev["start_dt"]
            phone = ev["phone"]
            if start_dt.tzinfo is None:
                start_dt = tz.localize(start_dt)
            schedule_event(scheduler, "Manual", title, start_dt, phone, tz)

    # initial fetch-and-schedule
    schedule_from_fetcher(scheduler, tz, upcoming_hours=72)

    # schedule periodic fetch every hour
    scheduler.add_job(lambda: schedule_from_fetcher(scheduler, tz, upcoming_hours=72), 'interval', hours=1, id="fetch_every_hour")

    # Weekly reminders (user-requested):
    # - LeetCode: every Sunday at 07:55 local time
    # - CodeChef: every Wednesday at 19:55 local time
    phone = get_default_phone()
    if not phone:
        print("[WARN] No phone configured for weekly reminders (set DEFAULT_PHONE or add phone in contests.csv)")
    else:
        def weekly_leetcode():
            now_pretty = datetime.now(tz).strftime("%Y-%m-%d %H:%M %Z")
            send_template(phone, "LeetCode: Weekly Reminder", now_pretty)

        def weekly_codechef():
            now_pretty = datetime.now(tz).strftime("%Y-%m-%d %H:%M %Z")
            send_template(phone, "CodeChef: Weekly Reminder", now_pretty)

        try:
            scheduler.add_job(weekly_leetcode, 'cron', day_of_week='sun', hour=7, minute=55, id='weekly_leetcode')
            scheduler.add_job(weekly_codechef, 'cron', day_of_week='wed', hour=19, minute=55, id='weekly_codechef')
            print(f"[SCHEDULED] Weekly LeetCode reminders: Sun 07:55 -> {phone}")
            print(f"[SCHEDULED] Weekly CodeChef reminders: Wed 19:55 -> {phone}")
        except Exception as e:
            print("[ERR] scheduling weekly reminders:", e)

    try:
        while True:
            time.sleep(30)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("Scheduler stopped")

if __name__ == "__main__":
    main()
