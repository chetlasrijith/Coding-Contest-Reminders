# src/fetchers.py
import requests
from bs4 import BeautifulSoup
from dateutil import tz
from datetime import datetime, timezone, timedelta

# ========== Codeforces (recommended: official API) ==========
def fetch_codeforces(upcoming_within_hours=72):
    """
    Uses Codeforces public API to fetch contests.
    Returns list of events: {'platform','title','start_dt'(aware UTC),'url','duration_seconds'}
    """
    out = []
    try:
        resp = requests.get("https://codeforces.com/api/contest.list", timeout=15)
        data = resp.json()
        if data.get("status") != "OK":
            return out
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for c in data["result"]:
            if c.get("phase") != "BEFORE":
                continue
            start_ts = c.get("startTimeSeconds")
            if start_ts is None:
                continue
            # filter within upcoming_within_hours
            if start_ts - now_ts > upcoming_within_hours * 3600:
                continue
            start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
            out.append({
                "platform": "Codeforces",
                "title": c.get("name"),
                "start_dt": start_dt,
                "url": f"https://codeforces.com/contests/{c.get('id')}",
                "duration_seconds": c.get("durationSeconds", 0)
            })
    except Exception as e:
        print("[ERR] fetch_codeforces:", e)
    return out

# ========== CodeChef (scrape contests page) ==========
def fetch_codechef(upcoming_within_hours=72):
    """
    Scrapes CodeChef contests page for Present/Upcoming contests.
    Returns same event dict list. times are assumed in IST if not timezone included.
    """
    out = []
    try:
        url = "https://www.codechef.com/contests"
        resp = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")

        # On CodeChef contests page there are sections with tables. We'll pick Upcoming / Present table rows.
        # Try to find tables with 'Upcoming Contests' or 'Future Contests' heading
        tables = soup.find_all("table")
        for table in tables:
            # iterate rows
            thead = table.find("thead")
            headers = [th.get_text(strip=True).lower() for th in (thead.find_all("th") if thead else [])]
            # common header detection
            if not headers:
                continue
            # expected header containing 'contest' and 'start' or 'date'
            if any("contest" in h for h in headers) and any(("start" in h) or ("date" in h) or ("time" in h) for h in headers):
                for tr in table.find("tbody").find_all("tr"):
                    cols = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                    if not cols:
                        continue
                    # Typical CodeChef table columns: Code, Contest, Start Date, Duration, End Date, Type
                    # We attempt to map using known patterns:
                    # Find title and start column by position heuristics
                    title = cols[1] if len(cols) > 1 else cols[0]
                    # start might be cols[2] or cols[1] depending on layout
                    start_text = cols[2] if len(cols) > 2 else cols[-2]
                    # try parsing start_text — CodeChef uses format like "2025-12-07 18:30:00"
                    try:
                        # If timezone not present, assume IST
                        # Try multiple parsing attempts
                        from dateutil import parser
                        start_dt = parser.parse(start_text)
                        if start_dt.tzinfo is None:
                            # assume IST
                            start_dt = start_dt.replace(tzinfo=tz.gettz("Asia/Kolkata"))
                        # filter
                        now = datetime.now(timezone.utc)
                        if (start_dt.astimezone(timezone.utc) - now).total_seconds() > upcoming_within_hours*3600:
                            continue
                        # contest url: may be in <a>
                        a = tr.find("a", href=True)
                        contest_url = f"https://www.codechef.com{a['href']}" if a and a['href'].startswith("/") else (a['href'] if a else url)
                        out.append({
                            "platform": "CodeChef",
                            "title": title,
                            "start_dt": start_dt.astimezone(timezone.utc),
                            "url": contest_url,
                            "duration_seconds": None
                        })
                    except Exception:
                        continue
    except Exception as e:
        print("[ERR] fetch_codechef:", e)
    return out

# ========== LeetCode (scrape contests page) ==========
def fetch_leetcode(upcoming_within_hours=72):
    """
    Scrape LeetCode contests page for upcoming contests.
    LeetCode often embeds contest info in HTML or uses a GraphQL endpoint. We attempt to parse the 'Upcoming Contests' section.
    """
    out = []
    try:
        url = "https://leetcode.com/contest/"
        resp = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")

        # Try to find upcoming contest cards (class names may change)
        # Look for elements containing "Upcoming" headings and contest rows
        # Search for elements containing "Upcoming"
        upcoming_sections = []
        for tag in soup.find_all(string=lambda t: "Upcoming" in t or "upcoming" in t):
            # parent's card container
            parent = tag.find_parent()
            if parent:
                upcoming_sections.append(parent)

        # Fallback: find elements with 'upcoming-contests' in id/class
        if not upcoming_sections:
            upcoming_sections = soup.select(".upcoming-contests, .contest-card, ._2rJ3_")  # heuristic classes

        # parse from known JSON blob: many LeetCode pages embed window.__INITIAL_STATE__ with data
        # Look for script tag that contains "contestData" or "window.__INITIAL_STATE__"
        scripts = soup.find_all("script")
        found = False
        for s in scripts:
            txt = s.string
            if not txt:
                continue
            if "upcoming_contests" in txt or "contestData" in txt or "upcoming" in txt.lower():
                # try to find ISO timestamps in the script
                import re
                matches = re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d+Z", txt)
                if matches:
                    from dateutil import parser
                    for m in set(matches):
                        try:
                            dt = parser.isoparse(m)
                            now = datetime.now(timezone.utc)
                            if (dt - now).total_seconds() > upcoming_within_hours*3600:
                                continue
                            # We don't know title from matches; create a generic title
                            out.append({
                                "platform": "LeetCode",
                                "title": "LeetCode Contest",
                                "start_dt": dt,
                                "url": url,
                                "duration_seconds": None
                            })
                        except Exception:
                            continue
                    found = True
                    break

        # If we didn't find via script, attempt to parse visible contest list (best-effort)
        if not found:
            # Find li or div items that look like contest entries
            for item in soup.select("li, div"):
                text = item.get_text(" ", strip=True)
                if not text:
                    continue
                if "Starts" in text or "Starts in" in text or "UTC" in text:
                    # attempt to extract ISO-like date
                    from dateutil import parser
                    import re
                    # look for patterns like '2025-12-07 18:30' or 'Dec 07, 2025 18:30'
                    date_match = None
                    # try to find ISO timestamps
                    iso = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text)
                    if iso:
                        date_match = iso.group(0)
                    else:
                        # fallback: try to parse whole text (can be noisy)
                        try:
                            dt = parser.parse(text, fuzzy=True)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            date_match = dt.isoformat()
                        except Exception:
                            date_match = None
                    if date_match:
                        try:
                            dt = parser.parse(date_match)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            now = datetime.now(timezone.utc)
                            if (dt - now).total_seconds() > upcoming_within_hours*3600:
                                continue
                            title = text.split("\n")[0][:120]
                            out.append({
                                "platform": "LeetCode",
                                "title": title,
                                "start_dt": dt,
                                "url": url,
                                "duration_seconds": None
                            })
                        except Exception:
                            continue
    except Exception as e:
        print("[ERR] fetch_leetcode:", e)
    return out

# ========== Convenience: fetch all ==========
def fetch_all(upcoming_within_hours=72):
    events = []
    events.extend(fetch_codeforces(upcoming_within_hours=upcoming_within_hours))
    events.extend(fetch_codechef(upcoming_within_hours=upcoming_within_hours))
    events.extend(fetch_leetcode(upcoming_within_hours=upcoming_within_hours))
    # dedupe by (platform,title,start_dt)
    unique = {}
    for e in events:
        key = (e.get("platform"), e.get("title"), e.get("start_dt").isoformat() if e.get("start_dt") else "")
        if key not in unique:
            unique[key] = e
    return list(unique.values())
