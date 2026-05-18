"""
Injecte des rendez-vous de démonstration pour la refonte visuelle de l'agenda.

Usage:
  python3 scripts/seed_agenda_design_examples.py

Effet:
- Réserve des slots existants sur la semaine du 5 au 10 mai 2026
- Ajoute aussi quelques RDV répartis sur le mois de mai 2026
- Idempotent: si un slot ciblé est déjà réservé, le RDV est mis à jour.
"""

import sqlite3
from datetime import datetime

DB_PATH = "agent.db"
TENANT_ID = 1
RANGE_START = "2026-05-01"
RANGE_END = "2026-06-30"

# date, time, name, phone, motif
APPOINTMENTS = [
    # Semaine principale (alignée avec la maquette)
    ("2026-05-05", "08:30", "Nadia Simon", "+33644112233", "Consultation de suivi"),
    ("2026-05-05", "10:00", "Yanis Morel", "+33655223344", "Nouveau patient"),
    ("2026-05-05", "14:30", "Claire Martin", "+33610000001", "Contrôle"),
    ("2026-05-05", "16:00", "Créneau libéré", "+33000000000", "À réattribuer"),
    ("2026-05-06", "08:00", "Paul Bernard", "+33610000002", "Contrôle"),
    ("2026-05-06", "09:15", "Sophie Leroy", "+33610000004", "Consultation"),
    ("2026-05-06", "11:30", "Ahmed Bensaid", "+33610000005", "Renouvellement ordonnance"),
    ("2026-05-06", "15:15", "Martine Dubois", "+33610000006", "À confirmer"),
    ("2026-05-06", "17:00", "Jean Durand", "+33610000003", "Consultation de suivi"),
    ("2026-05-07", "09:00", "Hugo Caron", "+33666778810", "Consultation"),
    ("2026-05-07", "10:30", "Créneau ouvert", "+33000000001", "Disponible"),
    ("2026-05-07", "14:00", "Inès Robert", "+33666778811", "Suivi"),
    ("2026-05-08", "08:45", "Farid Haddad", "+33610000009", "Bilan"),
    ("2026-05-08", "10:15", "Leïla Hamel", "+33610000010", "Question avant RDV"),
    ("2026-05-08", "13:30", "Créneau récupéré", "+33000000002", "Nouveau patient"),
    ("2026-05-08", "16:30", "Marc Petit", "+33666778812", "Contrôle"),
    ("2026-05-09", "08:00", "Claire Martin", "+33610000001", "Consultation suivi"),
    ("2026-05-09", "09:15", "Paul Bernard", "+33610000002", "Contrôle"),
    ("2026-05-09", "10:30", "Créneau libéré", "+33000000000", "À réattribuer"),
    ("2026-05-09", "13:30", "Jean Durand", "+33610000003", "Douleurs thoraciques"),
    ("2026-05-09", "14:45", "Ahmed Bensaid", "+33610000005", "Renouvellement ordonnance"),
    ("2026-05-09", "16:00", "Créneau récupéré", "+33000000002", "Suite annulation"),
    ("2026-05-09", "17:15", "Martine Dubois", "+33610000006", "À confirmer"),
    ("2026-05-10", "09:30", "Urgence relative", "+33666778813", "À valider"),
    ("2026-05-10", "11:00", "Noémie Blanc", "+33666778814", "Court suivi"),
    # Semaine réellement disponible autour du 9 mai (pour remplir la vue semaine locale)
    ("2026-05-11", "08:30", "Nadia Simon", "+33644112233", "Consultation de suivi"),
    ("2026-05-11", "10:00", "Yanis Morel", "+33655223344", "Nouveau patient"),
    ("2026-05-11", "14:30", "Claire Martin", "+33610000001", "Contrôle"),
    ("2026-05-11", "16:00", "Créneau libéré", "+33000000007", "À réattribuer"),
    ("2026-05-12", "09:15", "Paul Bernard", "+33610000002", "Contrôle"),
    ("2026-05-12", "11:30", "Ahmed Bensaid", "+33610000005", "Renouvellement ordonnance"),
    ("2026-05-12", "15:15", "Martine Dubois", "+33610000006", "À confirmer"),
    ("2026-05-13", "09:00", "Hugo Caron", "+33666778810", "Consultation"),
    ("2026-05-13", "10:30", "Créneau ouvert", "+33000000008", "Disponible"),
    ("2026-05-13", "14:00", "Inès Robert", "+33666778811", "Suivi"),
    ("2026-05-14", "08:45", "Farid Haddad", "+33610000009", "Bilan"),
    ("2026-05-14", "10:15", "Leïla Hamel", "+33610000010", "Question avant RDV"),
    ("2026-05-14", "13:30", "Créneau récupéré", "+33000000009", "Nouveau patient"),
    ("2026-05-14", "16:30", "Marc Petit", "+33666778812", "Contrôle"),
    ("2026-05-15", "08:00", "Claire Martin", "+33610000001", "Suivi"),
    ("2026-05-15", "09:15", "Paul Bernard", "+33610000002", "Contrôle"),
    ("2026-05-15", "10:30", "Créneau libéré", "+33000000010", "Proposition en cours"),
    ("2026-05-15", "13:30", "Jean Durand", "+33610000003", "Douleurs thoraciques"),
    ("2026-05-15", "16:00", "Créneau récupéré", "+33000000011", "Suite annulation"),
    ("2026-05-15", "17:15", "Martine Dubois", "+33610000006", "À confirmer"),
    ("2026-05-16", "09:30", "Urgence relative", "+33666778813", "À valider"),
    ("2026-05-16", "11:00", "Noémie Blanc", "+33666778814", "Court suivi"),
    # Densification du mois
    ("2026-05-12", "08:45", "Clara Robert", "+33610000007", "Pédiatrie"),
    ("2026-05-12", "17:15", "Leïla Hamel", "+33610000010", "À confirmer"),
    ("2026-05-13", "09:00", "Fatima Benali", "+33610000008", "Bilan sanguin"),
    ("2026-05-13", "15:30", "Yanis Morel", "+33655223344", "Nouveau patient"),
    ("2026-05-14", "10:15", "Ahmed Bensaid", "+33610000005", "Ordonnance"),
    ("2026-05-15", "08:30", "Paul Bernard", "+33610000002", "Contrôle"),
    ("2026-05-16", "11:00", "Créneau sauvé", "+33000000003", "Récupéré"),
    ("2026-05-16", "16:00", "Martine Dubois", "+33610000006", "À confirmer"),
    ("2026-05-20", "10:00", "À confirmer", "+33000000004", "Rappel patient"),
    ("2026-05-20", "14:00", "Prioritaire", "+33666778815", "Question patient"),
    ("2026-05-23", "09:15", "Récupéré", "+33000000005", "Créneau récupéré"),
    ("2026-05-23", "11:45", "Nouveau patient", "+33666778816", "Première consultation"),
    ("2026-05-27", "10:30", "Prioritaire", "+33666778817", "Demande urgente"),
    ("2026-05-28", "14:45", "Récupéré", "+33000000006", "Créneau récupéré"),
]

EXTRA_SCENARIOS = [
    ("Claire Martin", "Consultation de suivi"),
    ("Paul Bernard", "Controle annuel"),
    ("Jean Durand", "Douleurs thoraciques - urgent"),
    ("Sophie Leroy", "Documents demandés avant RDV"),
    ("Ahmed Bensaid", "Renouvellement ordonnance"),
    ("Martine Dubois", "A confirmer"),
    ("Nadia Simon", "Bilan"),
    ("Yanis Morel", "Première consultation"),
    ("Farid Haddad", "Question patient prioritaire"),
    ("Leïla Hamel", "Documents demandés"),
    ("Créneau libéré", "A réattribuer"),
    ("Créneau récupéré", "Créneau récupéré"),
    ("Camille Roux", "Suivi post-consultation"),
    ("Antoine Lemaire", "Documents demandés avant bilan"),
    ("Nora Chevalier", "Renouvellement ordonnance"),
    ("Eva Gautier", "Question pratique patient"),
    ("Omar Rahim", "A confirmer - rappel vocal"),
    ("Sonia Perret", "Controle et orientation"),
    ("Mathis Delorme", "Demande prioritaire"),
]


def ensure_client(cur, phone: str, name: str, booking_iso: str, motif: str) -> None:
    now = datetime.utcnow().isoformat()
    existing = cur.execute(
        "SELECT phone FROM cabinet_clients WHERE tenant_id = ? AND phone = ?",
        (TENANT_ID, phone),
    ).fetchone()
    if existing:
        cur.execute(
            """
            UPDATE cabinet_clients
            SET display_name = ?, validated_name = ?, validation_status = 'validated',
                last_booking_start = ?, last_booking_motif = ?, updated_at = ?
            WHERE tenant_id = ? AND phone = ?
            """,
            (name, name, booking_iso, motif, now, TENANT_ID, phone),
        )
        return
    cur.execute(
        """
        INSERT INTO cabinet_clients (
          tenant_id, phone, raw_name, validated_name, display_name, validation_status,
          last_booking_start, last_booking_motif, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 'validated', ?, ?, ?, ?)
        """,
        (TENANT_ID, phone, name, name, name, booking_iso, motif, now, now),
    )


def upsert_appointment(cur, date: str, time: str, name: str, phone: str, motif: str) -> bool:
    slot = cur.execute(
        "SELECT id, is_booked FROM slots WHERE tenant_id = ? AND date = ? AND time = ? LIMIT 1",
        (TENANT_ID, date, time),
    ).fetchone()
    if not slot:
        return False
    slot_id = int(slot["id"])
    existing = cur.execute(
        "SELECT id FROM appointments WHERE tenant_id = ? AND slot_id = ? LIMIT 1",
        (TENANT_ID, slot_id),
    ).fetchone()
    if existing:
        cur.execute(
            """
            UPDATE appointments
            SET name = ?, contact = ?, motif = ?, contact_type = 'phone'
            WHERE tenant_id = ? AND slot_id = ?
            """,
            (name, phone, motif, TENANT_ID, slot_id),
        )
    else:
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO appointments (tenant_id, slot_id, name, contact, contact_type, motif, created_at)
            VALUES (?, ?, ?, ?, 'phone', ?, ?)
            """,
            (TENANT_ID, slot_id, name, phone, motif, now),
        )
    cur.execute(
        "UPDATE slots SET is_booked = 1 WHERE tenant_id = ? AND id = ?",
        (TENANT_ID, slot_id),
    )
    booking_iso = f"{date}T{time}:00"
    ensure_client(cur, phone, name, booking_iso, motif)
    return True


def reset_range(cur, date_start: str, date_end: str) -> None:
    # Réinitialise les RDV sur la plage de démo pour éviter l'effet "copié-collé"
    # et repartir proprement avec une distribution cohérente.
    cur.execute(
        """
        DELETE FROM appointments
        WHERE tenant_id = ?
          AND slot_id IN (
            SELECT id FROM slots
            WHERE tenant_id = ? AND date BETWEEN ? AND ?
          )
        """,
        (TENANT_ID, TENANT_ID, date_start, date_end),
    )
    cur.execute(
        """
        UPDATE slots
        SET is_booked = 0
        WHERE tenant_id = ? AND date BETWEEN ? AND ?
        """,
        (TENANT_ID, date_start, date_end),
    )


def target_per_day(date_str: str) -> int:
    wd = datetime.fromisoformat(date_str).weekday()  # Mon=0 ... Sun=6
    if wd <= 4:
        return 12  # jours ouvrés bien remplis
    if wd == 5:
        return 7   # samedi plus léger
    return 3       # dimanche minimal


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    inserted = 0
    missing_slots = 0

    reset_range(cur, RANGE_START, RANGE_END)

    # 1) Injecte d'abord les RDV "maquette" (références visuelles clés).
    for date, time, name, phone, motif in APPOINTMENTS:
        ok = upsert_appointment(cur, date, time, name, phone, motif)
        if ok:
            inserted += 1
        else:
            missing_slots += 1

    # 2) Puis complète chaque jour avec une densité équilibrée et des motifs variés.
    extra_added = 0
    all_slots = cur.execute(
        """
        SELECT date, time
        FROM slots
        WHERE tenant_id = ?
          AND date BETWEEN ? AND ?
          AND is_booked = 0
        ORDER BY date, time
        """,
        (TENANT_ID, RANGE_START, RANGE_END),
    ).fetchall()

    by_date = {}
    for row in all_slots:
        by_date.setdefault(row["date"], []).append(row["time"])

    for date_str in sorted(by_date.keys()):
        current = cur.execute(
            """
            SELECT COUNT(*) c
            FROM appointments a
            JOIN slots s ON s.id = a.slot_id
            WHERE a.tenant_id = ? AND s.date = ?
            """,
            (TENANT_ID, date_str),
        ).fetchone()["c"]
        target = target_per_day(date_str)
        need = max(0, target - current)
        if need == 0:
            continue
        day_slots = by_date[date_str][:need]
        date_seed = int(date_str.replace("-", ""))
        for i, time_str in enumerate(day_slots):
            scenario_idx = (date_seed + i * 3) % len(EXTRA_SCENARIOS)
            name, motif = EXTRA_SCENARIOS[scenario_idx]
            phone = f"+3388{date_str[5:7]}{date_str[8:10]}{i:03d}"
            if "Créneau" in name:
                phone = f"+3399{date_str[5:7]}{date_str[8:10]}{i:03d}"
            ok = upsert_appointment(cur, date_str, time_str, name, phone, motif)
            if ok:
                inserted += 1
                extra_added += 1
            else:
                missing_slots += 1
    conn.commit()

    week_count = cur.execute(
        """
        SELECT COUNT(*) c
        FROM appointments a JOIN slots s ON s.id = a.slot_id
        WHERE a.tenant_id = ? AND s.date BETWEEN '2026-05-05' AND '2026-05-12'
        """,
        (TENANT_ID,),
    ).fetchone()["c"]
    month_count = cur.execute(
        """
        SELECT COUNT(*) c
        FROM appointments a JOIN slots s ON s.id = a.slot_id
        WHERE a.tenant_id = ? AND s.date LIKE '2026-05-%'
        """,
        (TENANT_ID,),
    ).fetchone()["c"]
    print(f"OK: {inserted} rendez-vous injectés/maj")
    print(f"Ajouts massifs: {extra_added}")
    print(f"Slots manquants: {missing_slots}")
    print(f"RDV semaine 5-12 mai: {week_count}")
    print(f"RDV mai 2026: {month_count}")
    conn.close()


if __name__ == "__main__":
    main()
