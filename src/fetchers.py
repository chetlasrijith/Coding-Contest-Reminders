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
            thead = table.find("thead")
            headers = [th.get_text(strip=True).lower() for th in (thead.find_all("th") if thead else [])]
            if not headers:
                continue
            # expected header containing 'contest' and some time/date column
            if any("contest" in h for h in headers) and any(("start" in h) or ("date" in h) or ("time" in h) for h in headers):
                tbody = table.find("tbody")
                if not tbody:
                    continue
                for tr in tbody.find_all("tr"):
                    cols = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                    if not cols:
                        continue
                    # prefer an <a> text for title if available
                    a = tr.find("a", href=True)
                    title = a.get_text(strip=True) if a else (cols[1] if len(cols) > 1 else cols[0])

                    # try to find a column that looks like a date/time
                    start_text = None
                    for c in cols:
                        if any(ch.isdigit() for ch in c) and (":" in c or any(m in c.lower() for m in ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"])):
                            start_text = c
                            break
                    # fallback to second/third column heuristics
                    if not start_text:
                        if len(cols) > 2:
                            start_text = cols[2]
                        elif len(cols) > 1:
                            start_text = cols[1]
                        else:
                            start_text = ""

                    # parse the start time robustly
                    try:
                        from dateutil import parser
                        # try parsing the candidate start_text first
                        try:
                            start_dt = parser.parse(start_text, fuzzy=True)
                        except Exception:
                            # try parsing the whole row text as a last resort
                            start_dt = parser.parse(tr.get_text(" ", strip=True), fuzzy=True)
                        if start_dt.tzinfo is None:
                            # assume IST if timezone missing
                            start_dt = start_dt.replace(tzinfo=tz.gettz("Asia/Kolkata"))
                        now = datetime.now(timezone.utc)
                        if (start_dt.astimezone(timezone.utc) - now).total_seconds() > upcoming_within_hours*3600:
                            continue
                        contest_url = f"https://www.codechef.com{a['href']}" if a and a['href'].startswith("/") else (a['href'] if a else url)
                        out.append({
                            "platform": "CodeChef",
                            "title": title,
                            "start_dt": start_dt.astimezone(timezone.utc),
                            "url": contest_url,
                            "duration_seconds": None
                        })
                    except Exception:
                        # skip rows we can't parse
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
        # LeetCode exposes a simple contest info JSON endpoint; try that first
        api_url = "https://leetcode.com/contest/api/info/"
        try:
            r = requests.get(api_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                data = r.json()
                # look for lists of contests in the response
                candidates = []
                if isinstance(data, dict):
                    for v in data.values():
                        if isinstance(v, list):
                            candidates.extend(v)
                from dateutil import parser
                now = datetime.now(timezone.utc)
                for item in candidates:
                    # item may be a dict with start_time / start / startTime
                    start_val = None
                    title = None
                    url_item = url
                    if isinstance(item, dict):
                        # common keys
                        for k in ("start_time", "startTime", "start", "begin_time", "epoch"): 
                            if k in item:
                                start_val = item[k]
                                break
                        for k in ("title", "name", "contest_name"): 
                            if k in item:
                                title = item[k]
                                break
                        if "url" in item:
                            url_item = item["url"]
                    # normalize start_val
                    if start_val is None:
                        continue
                    try:
                        if isinstance(start_val, (int, float)):
                            # treat as epoch seconds or milliseconds
                            sv = int(start_val)
                            if sv > 10**12:
                                dt = datetime.fromtimestamp(sv/1000, tz=timezone.utc)
                            else:
                                dt = datetime.fromtimestamp(sv, tz=timezone.utc)
                        else:
                            dt = parser.parse(str(start_val))
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                        if (dt - now).total_seconds() > upcoming_within_hours*3600:
                            continue
                        out.append({
                            "platform": "LeetCode",
                            "title": title or "LeetCode Contest",
                            "start_dt": dt,
                            "url": url_item,
                            "duration_seconds": None
                        })
                    except Exception:
                        continue
                # if we got any, return early
                if out:
                    return out
        except Exception:
            # ignore and fallback to HTML parsing
            pass

        # fallback: parse the HTML and try to extract ISO timestamps from script tags
        resp = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        scripts = soup.find_all("script")
        found = False
        import re
        for s in scripts:
            txt = s.string or s.text
            if not txt:
                continue
            # look for ISO timestamps like 2025-12-07T18:30:00Z (with optional fractional seconds)
            matches = re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", txt)
            if matches:
                from dateutil import parser
                now = datetime.now(timezone.utc)
                for m in set(matches):
                    try:
                        dt = parser.isoparse(m)
                        if (dt - now).total_seconds() > upcoming_within_hours*3600:
                            continue
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

        # last resort: try to scan visible text for 'Starts' and parse nearby date
        if not found:
            from dateutil import parser
            for item in soup.select("li, div"):
                text = item.get_text(" ", strip=True)
                if not text:
                    continue
                if "Starts" in text or "Starts in" in text or "UTC" in text:
                    try:
                        dt = parser.parse(text, fuzzy=True)
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
