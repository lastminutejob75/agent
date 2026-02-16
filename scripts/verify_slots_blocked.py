#!/usr/bin/env python3
"""
Vérifie qu'un RDV pris est bien bloqué (n'apparaît plus dans les créneaux libres).
Usage:
  python scripts/verify_slots_blocked.py                    # 3 février (aujourd'hui +1 si pas lundi)
  python scripts/verify_slots_blocked.py 2026-02-03        # date fixe
  python scripts/verify_slots_blocked.py 2026-02-03 13    # date + heure à vérifier (13h)
"""
import os
import sys
from datetime import datetime, timedelta

# Projet root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    from backend import config
    if not getattr(config, "GOOGLE_CALENDAR_ID", None) and not getattr(config, "SERVICE_ACCOUNT_FILE", None):
        print("⚠️ Google Calendar non configuré (GOOGLE_CALENDAR_ID / credentials).")
        print("   Vérifiez backend/config.py et credentials/service-account.json")
        return 1

    from backend.google_calendar import GoogleCalendarService

    # Date cible : 3 février ou argument
    if len(sys.argv) >= 2:
        try:
            target = datetime.strptime(sys.argv[1], "%Y-%m-%d")
        except ValueError:
            print("Usage: python scripts/verify_slots_blocked.py [YYYY-MM-DD] [heure]")
            return 1
    else:
        target = datetime.now() + timedelta(days=1)
        # Si demain weekend, prendre lundi
        while target.weekday() >= 5:
            target += timedelta(days=1)

    hour_to_check = int(sys.argv[2]) if len(sys.argv) >= 3 else 13
    calendar_id = getattr(config, "GOOGLE_CALENDAR_ID", None) or os.environ.get("GOOGLE_CALENDAR_ID")
    if not calendar_id:
        print("GOOGLE_CALENDAR_ID manquant.")
        return 1

    cal = GoogleCalendarService(calendar_id)

    # 1) Events ce jour-là
    day_start = target.replace(hour=9, minute=0, second=0, microsecond=0)
    day_end = target.replace(hour=18, minute=0, second=0, microsecond=0)
    try:
        events_result = cal.service.events().list(
            calendarId=calendar_id,
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except Exception as e:
        print(f"Erreur list events: {e}")
        return 1

    events = events_result.get("items", [])
    print(f"\n📅 {target.date()} — {len(events)} event(s) dans le calendrier:")
    for ev in events:
        start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", ""))
        summary = ev.get("summary", "Sans titre")
        print(f"   - {start}  {summary}")

    # 2) Créneaux libres (9h–18h)
    free = cal.get_free_slots(date=target, start_hour=9, end_hour=18, limit=50)
    print(f"\n🟢 Créneaux libres (get_free_slots): {len(free)}")
    for s in free[:15]:
        print(f"   - {s.get('start')}  {s.get('label', '')}")
    if len(free) > 15:
        print(f"   ... et {len(free) - 15} autres")

    # 3) Vérifier que l'heure demandée n'est pas dans les libres
    hour_slot = any(
        s.get("start", "").find(f"T{hour_to_check:02d}:") >= 0 or f"à {hour_to_check}h" in (s.get("label") or "")
        for s in free
    )
    if hour_slot:
        print(f"\n❌ {hour_to_check}h apparaît encore dans les créneaux libres → pas bloqué.")
        return 1
    print(f"\n✅ {hour_to_check}h n’apparaît pas dans les libres → créneau bien bloqué si un RDV existait à cette heure.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
