# backend/db.py
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional

DB_PATH = "agent.db"

SLOT_TIMES = ["10:00", "14:00", "16:00"]
TARGET_MIN_SLOTS = 15  # 5 jours ouvrés * 3 slots
MAX_DAYS_AHEAD = 30  # Limite de sécurité pour éviter boucle infinie


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(days: int = 7) -> None:
    conn = get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                is_booked INTEGER DEFAULT 0,
                UNIQUE(date, time)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                contact TEXT NOT NULL,
                contact_type TEXT NOT NULL,
                motif TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(slot_id) REFERENCES slots(id)
            )
        """)
        
        # Seed slots (SKIP WEEKENDS)
        for day in range(1, days + 1):
            target_date = datetime.now() + timedelta(days=day)
            
            # Skip weekends
            if target_date.weekday() < 5:  # Lundi-Vendredi
                d = target_date.strftime("%Y-%m-%d")
                for t in SLOT_TIMES:
                    conn.execute(
                        "INSERT OR IGNORE INTO slots (date, time) VALUES (?, ?)",
                        (d, t)
                    )

        conn.commit()
    finally:
        conn.close()


def cleanup_old_slots() -> None:
    """
    Supprime les slots passés et garantit au moins TARGET_MIN_SLOTS slots futurs
    (lundi-vendredi uniquement).
    
    Logique :
    - Supprime tous les slots dont date < aujourd'hui
    - Compte les slots futurs restants
    - Crée de nouveaux slots (weekdays only) jusqu'à atteindre TARGET_MIN_SLOTS
    - Utilise BEGIN IMMEDIATE pour éviter race conditions
    
    Raises:
        Exception: Si erreur DB (rollback automatique)
    """
    conn = get_conn()
    try:
        # Lock write transaction (évite race)
        conn.execute("BEGIN IMMEDIATE")

        today = datetime.now().strftime("%Y-%m-%d")

        # Supprimer les slots passés
        conn.execute("DELETE FROM slots WHERE date < ?", (today,))

        # Compter les slots futurs (tous, pas seulement libres, car on veut garantir le nombre total)
        cur = conn.execute("SELECT COUNT(*) as c FROM slots WHERE date >= ?", (today,))
        count = int(cur.fetchone()["c"])

        missing = max(0, TARGET_MIN_SLOTS - count)
        if missing == 0:
            conn.commit()
            return

        day_offset = 1
        added = 0

        while added < missing:
            # Sécurité : évite boucle infinie (ne devrait jamais arriver avec 15 slots max)
            if day_offset > MAX_DAYS_AHEAD:
                break

            target_date = datetime.now() + timedelta(days=day_offset)

            # Weekdays only
            if target_date.weekday() < 5:
                d = target_date.strftime("%Y-%m-%d")

                for t in SLOT_TIMES:
                    if added >= missing:
                        break

                    before = conn.total_changes
                    conn.execute(
                        "INSERT OR IGNORE INTO slots (date, time) VALUES (?, ?)",
                        (d, t),
                    )
                    # On incrémente seulement si INSERT a vraiment changé qqch
                    if conn.total_changes > before:
                        added += 1

            day_offset += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def count_free_slots(limit: int = 1000) -> int:
    cleanup_old_slots()  # Nettoyer avant de compter
    conn = get_conn()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        cur = conn.execute("SELECT COUNT(*) AS c FROM slots WHERE is_booked=0 AND date >= ?", (today,))
        return int(cur.fetchone()["c"])
    finally:
        conn.close()


def list_free_slots(limit: int = 3) -> List[Dict]:
    # Nettoyer et régénérer si nécessaire
    cleanup_old_slots()
    
    conn = get_conn()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        cur = conn.execute(
            """
            SELECT id, date, time 
            FROM slots 
            WHERE is_booked=0 AND date >= ? 
            ORDER BY date ASC, time ASC 
            LIMIT ?
            """,
            (today, limit)
        )
        out = []
        for r in cur.fetchall():
            out.append({"id": int(r["id"]), "date": r["date"], "time": r["time"]})
        return out
    finally:
        conn.close()


def book_slot_atomic(
    slot_id: int,
    name: str,
    contact: str,
    contact_type: str,
    motif: str
) -> bool:
    """
    Book atomique.
    Returns False if slot already booked.
    """
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        conn.execute(
            "UPDATE slots SET is_booked=1 WHERE id=? AND is_booked=0",
            (slot_id,)
        )
        if conn.total_changes == 0:
            conn.rollback()
            return False

        conn.execute(
            """
            INSERT INTO appointments (slot_id, name, contact, contact_type, motif, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (slot_id, name, contact, contact_type, motif, datetime.utcnow().isoformat())
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
