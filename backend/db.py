# backend/db.py
from __future__ import annotations

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Utiliser /tmp sur Vercel, sinon le répertoire courant
DB_PATH = os.environ.get('DB_PATH', 'agent.db')

SLOT_TIMES = ["10:00", "14:00", "16:00"]
TARGET_MIN_SLOTS = 15  # 5 jours ouvrés * 3 slots
MAX_DAYS_AHEAD = 30  # Limite de sécurité pour éviter boucle infinie


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
                booked INTEGER DEFAULT 0,
                UNIQUE(date, time)
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                contact TEXT NOT NULL,
                motif TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(slot_id) REFERENCES slots(id)
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS faq (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                answer TEXT NOT NULL
            )
        """)
        
        conn.commit()
        
        # Seed slots si nécessaire
        _seed_slots_if_needed(conn, days)
        
    finally:
        conn.close()


def _seed_slots_if_needed(conn: sqlite3.Connection, days: int) -> None:
    """Génère des slots pour les N prochains jours si nécessaire."""
    today = datetime.now().date()
    existing = conn.execute("SELECT COUNT(*) as count FROM slots WHERE date >= ?", (today.isoformat(),)).fetchone()
    
    if existing and existing["count"] >= TARGET_MIN_SLOTS:
        return
    
    # Générer slots pour les prochains jours
    generated = 0
    current_date = today
    days_checked = 0
    
    while generated < TARGET_MIN_SLOTS and days_checked < MAX_DAYS_AHEAD:
        # Ignorer weekends (samedi=5, dimanche=6)
        if current_date.weekday() < 5:  # Lundi à Vendredi
            for time in SLOT_TIMES:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO slots (date, time) VALUES (?, ?)",
                        (current_date.isoformat(), time)
                    )
                    generated += 1
                except sqlite3.IntegrityError:
                    pass  # Déjà existant
        
        current_date += timedelta(days=1)
        days_checked += 1
    
    conn.commit()


def list_free_slots(limit: int = 30) -> List[Dict]:
    conn = get_conn()
    try:
        today = datetime.now().date().isoformat()
        rows = conn.execute("""
            SELECT id, date, time 
            FROM slots 
            WHERE date >= ? AND booked = 0 
            ORDER BY date, time 
            LIMIT ?
        """, (today, limit)).fetchall()
        
        return [{"id": r["id"], "date": r["date"], "time": r["time"]} for r in rows]
    finally:
        conn.close()


def count_free_slots() -> int:
    conn = get_conn()
    try:
        today = datetime.now().date().isoformat()
        row = conn.execute("""
            SELECT COUNT(*) as count 
            FROM slots 
            WHERE date >= ? AND booked = 0
        """, (today,)).fetchone()
        return row["count"] if row else 0
    finally:
        conn.close()


def book_slot_atomic(slot_id: int, name: str, contact: str, motif: Optional[str] = None) -> bool:
    """
    Réserve un slot de manière atomique (évite double booking).
    Returns True si réservé, False si déjà pris.
    """
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        
        # Vérifier que le slot est libre
        slot = conn.execute("SELECT booked FROM slots WHERE id = ?", (slot_id,)).fetchone()
        if not slot or slot["booked"] != 0:
            conn.rollback()
            return False
        
        # Réserver
        conn.execute("UPDATE slots SET booked = 1 WHERE id = ?", (slot_id,))
        
        # Créer appointment
        conn.execute("""
            INSERT INTO appointments (slot_id, name, contact, motif)
            VALUES (?, ?, ?, ?)
        """, (slot_id, name, contact, motif))
        
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def load_faq() -> List[Dict]:
    """Charge toutes les FAQ depuis la DB."""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT id, question, answer FROM faq").fetchall()
        return [{"id": r["id"], "question": r["question"], "answer": r["answer"]} for r in rows]
    finally:
        conn.close()


def seed_faq() -> None:
    """Seed FAQ de base (V1)."""
    conn = get_conn()
    try:
        faqs = [
            ("FAQ_HORAIRES", "Quels sont vos horaires ?", "Nos horaires sont de 9h à 18h du lundi au vendredi."),
            ("FAQ_ADRESSE", "Où êtes-vous situés ?", "Nous sommes situés au 123 rue de la République, 75001 Paris."),
            ("FAQ_CONTACT", "Comment vous contacter ?", "Vous pouvez nous contacter par téléphone au 01 23 45 67 89 ou par email à contact@example.com."),
        ]
        
        for faq_id, question, answer in faqs:
            conn.execute("""
                INSERT OR REPLACE INTO faq (id, question, answer)
                VALUES (?, ?, ?)
            """, (faq_id, question, answer))
        
        conn.commit()
    finally:
        conn.close()
