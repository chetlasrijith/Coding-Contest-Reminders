import csv
from dateutil import parser
from datetime import datetime, timezone

def read_contests(csv_path):
    """
    Yield dicts: {title, start_dt (aware), phone}
    """
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("title"): 
                continue
            title = row["title"].strip()
            start_iso = row["start_iso"].strip()
            phone = row["phone"].strip()
            try:
                start_dt = parser.isoparse(start_iso)
            except Exception as e:
                print(f"[ERR] invalid date '{start_iso}' for {title}: {e}")
                continue
            yield {"title": title, "start_dt": start_dt, "phone": phone}
