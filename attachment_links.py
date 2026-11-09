"""Attachment links for every item, for the download buttons on the site.

Legistar does not let other sites read its API from a visitor's browser, so the
daily run lists each item's attachments from the public Legistar API and writes
them to attachment_links.json. index.html loads that file when a card is opened
and shows one button per attachment, linking to the file on Legistar's server.

attachment_links.json:
  {"base": "https://cincinnatioh.legistar1.com/cincinnatioh/attachments/",
   "checked": {matter_id: "YYYY-MM-DD"},
   "links": {matter_id: [[name, url], ...]},
   "failed": {matter_id: "YYYY-MM-DD"}}
A url starting with "~" is the base plus the rest. Items with no attachment have a
"checked" date and no "links" entry. An item whose API call failed is kept in
"failed" and tried again at the end of later backfills, so it cannot hold up the rest.

Each run re-lists items introduced in the last RECENT_DAYS whose last check is
RECHECK_DAYS or more old (attachments are often added after an item first
appears), then lists up to BACKFILL_LIMIT items never checked, newest first.
"""
import json
import os
import time
from datetime import datetime, timedelta

import attachments as att

LINKS_FILE = "attachment_links.json"
BASE = "https://cincinnatioh.legistar1.com/cincinnatioh/attachments/"
RECENT_DAYS = 90
RECHECK_DAYS = 2
BACKFILL_LIMIT = 2500
DELAY = 0.1           # seconds between API calls
MAX_ERRORS = 25       # stop the run after this many failed calls in a row


def load(path=None):
    path = path or LINKS_FILE
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    for key in ("checked", "links", "failed"):
        data.setdefault(key, {})
    data["base"] = BASE
    return data


def save(data, path=None):
    path = path or LINKS_FILE
    data["base"] = BASE
    for key in ("checked", "links", "failed"):
        data[key] = dict(sorted(data[key].items(), key=lambda kv: int(kv[0])))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def compact(url):
    return "~" + url[len(BASE):] if url.startswith(BASE) else url


def due_ids(rows, checked, failed, today, backfill_limit):
    """Matter ids to list this run: recent items due a recheck, then unchecked backfill
    (newest first; items that failed before go last)."""
    recent_from = (today - timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%d")
    recheck_before = (today - timedelta(days=RECHECK_DAYS - 1)).strftime("%Y-%m-%d")
    by_date = sorted(rows, key=lambda r: (r.get("intro_date") or "", r["matter_id"]), reverse=True)
    recent = [r["matter_id"] for r in by_date
              if (r.get("intro_date") or "")[:10] >= recent_from
              and checked.get(r["matter_id"], "") < recheck_before]
    recent_set = set(recent)
    unchecked = [r["matter_id"] for r in by_date
                 if r["matter_id"] not in checked and r["matter_id"] not in recent_set]
    backfill = ([m for m in unchecked if m not in failed] + [m for m in unchecked if m in failed])
    return recent, backfill[:backfill_limit]


def update_links(rows, api_base, today=None, backfill_limit=BACKFILL_LIMIT, lister=None):
    """List attachments for the items that are due and save LINKS_FILE. Returns a summary."""
    lister = lister or att.list_attachments
    today = today or datetime.utcnow()
    data = load()
    checked, links, failed = data["checked"], data["links"], data["failed"]
    ids = {r["matter_id"] for r in rows if r.get("matter_id")}
    for store in (checked, links, failed):                    # items no longer on the site
        for mid in [m for m in store if m not in ids]:
            store.pop(mid)
    recent, backfill = due_ids([r for r in rows if r.get("matter_id")], checked, failed,
                               today, backfill_limit)
    stamp = today.strftime("%Y-%m-%d")
    done = errors = in_a_row = 0
    for mid in recent + backfill:
        try:
            found = sorted(lister(api_base, mid), key=lambda a: a[3])
        except Exception:
            failed[mid] = today.strftime("%Y-%m-%d")
            errors += 1
            in_a_row += 1
            if in_a_row >= MAX_ERRORS:
                break
            continue
        in_a_row = 0
        if found:
            links[mid] = [[(name or "Attachment"), compact(url)] for _, name, url, _ in found]
        else:
            links.pop(mid, None)
        checked[mid] = stamp
        failed.pop(mid, None)
        done += 1
        time.sleep(DELAY)
    save(data)
    return {"recent_due": len(recent), "backfill_due": len(backfill), "listed": done,
            "errors": errors, "with_links": len(links), "checked": len(checked), "items": len(ids)}
