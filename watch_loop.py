#!/usr/bin/env python3
"""Boucle de surveillance Opening Session Verbier (toutes les ~20 s).

Tourne ~5h45 dans un job GitHub Actions, puis le workflow se relance lui-même.
Surveille les deux produits (sans train / avec train). Push ntfy dès qu'une
place apparaît, puis rappel toutes les 2 min tant qu'il en reste.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import date, datetime

PRODUCTS = {
    "410650": ("Opening Session",
               "https://verbier4vallees.ch/fr/shop-en-ligne/activites/opening-session_activity_410650"),
    "426820": ("Opening Session + train",
               "https://verbier4vallees.ch/fr/shop-en-ligne/activites/opening-session-saint-nicolas-express_activity_426820"),
}
API = "https://verbier4vallees.ch/fr/shop/product/available-dates-times?activity_id={}"
TOPIC = os.environ["NTFY_TOPIC"]
INTERVAL = int(os.environ.get("INTERVAL", "20"))
DURATION = int(os.environ.get("DURATION", str(5 * 3600 + 45 * 60)))
REMIND_EVERY = 120
END_DATE = "2026-12-05"


LOGFILE = os.environ.get("LOGFILE", os.path.expanduser("~/Scripts/verbier_ventes.log"))


def log(msg):
    line = f"{datetime.now():%a %d.%m %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(LOGFILE, "a") as f:
        f.write(line + "\n")


def push(title, msg, click, priority="urgent", tags="ski", open_page=True):
    if sys.platform == "darwin":
        subprocess.run(["osascript", "-e",
                        f'display notification "{msg}" with title "{title}" sound name "Glass"'])
        if open_page:
            subprocess.run(["open", click])
    req = urllib.request.Request(
        f"https://ntfy.sh/{TOPIC}", data=msg.encode(),
        headers={"Title": title, "Priority": priority, "Click": click, "Tags": tags},
    )
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        log(f"ntfy error: {e}")


def fetch(pid):
    req = urllib.request.Request(
        API.format(pid),
        headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)
    today = date.today().isoformat()
    return {s["date"]: (int(s.get("available", 0)), int(s.get("max", 0)))
            for s in (data.get("availabilityByDate") or {}).values()
            if s.get("date", "") >= today}


def main():
    if date.today().isoformat() > END_DATE:
        log("Après la date de l'événement, rien à faire.")
        return
    if os.environ.get("TEST_PUSH") == "1":
        push("Test watcher Verbier", "Boucle 20 s démarrée", PRODUCTS["410650"][1],
             priority="urgent", tags="white_check_mark", open_page=False)

    last_alert = {}   # pid -> timestamp de la dernière alerte
    last_seen = {}
    start = time.time()
    errors = 0
    paused = False
    while time.time() - start < DURATION:
        # Pas de vente le week-end (heure locale : TZ=Europe/Zurich sur GitHub)
        if datetime.now().weekday() >= 5:
            if not paused:
                log("Week-end : pause jusqu'à lundi 00:00")
                paused = True
            time.sleep(60)
            continue
        if paused:
            log("Lundi : reprise des vérifications")
            paused = False
        for pid, (name, page) in PRODUCTS.items():
            try:
                avail = fetch(pid)
                errors = 0
            except Exception as e:
                errors += 1
                log(f"{pid} fetch error: {e}")
                continue
            if avail != last_seen.get(pid):
                log(f"{pid} {avail}")
                last_seen[pid] = avail
            open_ = {d: a for d, (a, _) in avail.items() if a > 0}
            if open_:
                if time.time() - last_alert.get(pid, 0) >= REMIND_EVERY:
                    msg = ", ".join(f"{d}: {n} places" for d, n in sorted(open_.items()))
                    push(f"{name} DISPO !", msg + " - touche pour réserver", page)
                    log(f"ALERT {pid} {msg}")
                    last_alert[pid] = time.time()
            else:
                last_alert.pop(pid, None)
        if errors >= 30:
            push("Watcher Verbier en erreur", "L'API ne répond plus depuis ~10 min",
                 PRODUCTS["410650"][1], priority="high", tags="warning")
            errors = 0
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
