#!/usr/bin/env python3
"""Vérifie les places Opening Session Verbier et envoie un push ntfy si dispo.

Sans état : tant qu'il y a des places, chaque run renvoie une alerte
(toutes les ~5 min sur GitHub Actions), ce qui sert de rappel.
"""
import json
import os
import urllib.request
from datetime import date

API = "https://verbier4vallees.ch/fr/shop/product/available-dates-times?activity_id=410650"
PAGE = "https://verbier4vallees.ch/fr/shop-en-ligne/activites/opening-session_activity_410650"
TOPIC = os.environ["NTFY_TOPIC"]


def push(title, msg, priority="urgent", tags="ski"):
    req = urllib.request.Request(
        f"https://ntfy.sh/{TOPIC}",
        data=msg.encode(),
        headers={"Title": title, "Priority": priority, "Click": PAGE, "Tags": tags},
    )
    urllib.request.urlopen(req, timeout=15)


req = urllib.request.Request(
    API, headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
)
with urllib.request.urlopen(req, timeout=20) as r:
    data = json.load(r)

today = date.today().isoformat()
avail = {
    s["date"]: int(s.get("available", 0))
    for s in (data.get("availabilityByDate") or {}).values()
    if s.get("date", "") >= today
}
print(avail)

open_ = {d: n for d, n in avail.items() if n > 0}
if open_:
    msg = ", ".join(f"{d}: {n} places" for d, n in sorted(open_.items()))
    push("Verbier Opening Session dispo !", msg + " - touche pour reserver")

if os.environ.get("TEST_PUSH") == "1":
    push("Test watcher Verbier", f"Ca marche. Etat actuel : {avail}", priority="default", tags="white_check_mark")
