# backend/session_store_sqlite.py
"""
Session store persistant avec SQLite.
Résout le problème de perte de sessions quand Railway redémarre.
"""

import sqlite3
import json
import pickle
import base64
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from backend.session import Session, QualifData
from backend import config


def _slot_start_to_iso(val) -> str:
    """Convertit start (datetime ou str) en ISO pour JSON."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


class SQLiteSessionStore:
    """
    Session store persistant utilisant SQLite.
    Sauvegarde automatiquement toutes les données de session.
    """
    
    def __init__(self, db_path: str = "sessions.db"):
        """
        Initialise le store SQLite.
        
        Args:
            db_path: Chemin vers la base de données SQLite
        """
        self.db_path = db_path
        self._init_db()
        self._memory_cache: Dict[str, Session] = {}  # Cache en mémoire pour performance
    
    def _init_db(self):
        """Crée la table sessions si elle n'existe pas."""
        conn = sqlite3.connect(self.db_path)
        
        # Activer WAL mode pour meilleures performances en écriture
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")  # Plus rapide, toujours safe
        
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                conv_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                channel TEXT NOT NULL,
                customer_phone TEXT,
                
                -- Qualif data
                name TEXT,
                motif TEXT,
                pref TEXT,
                contact TEXT,
                contact_type TEXT,
                
                -- Counters
                no_match_turns INTEGER DEFAULT 0,
                confirm_retry_count INTEGER DEFAULT 0,
                contact_retry_count INTEGER DEFAULT 0,
                
                -- Partial data
                partial_phone_digits TEXT,
                
                -- Pending data (JSON serialized)
                pending_slots_json TEXT,
                pending_slot_choice INTEGER,
                pending_cancel_slot_json TEXT,
                
                -- Flags
                extracted_name INTEGER DEFAULT 0,
                extracted_motif INTEGER DEFAULT 0,
                extracted_pref INTEGER DEFAULT 0,
                motif_help_used INTEGER DEFAULT 0,
                
                -- Metadata
                last_seen_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                
                -- Full session pickle (backup)
                session_pickle TEXT,
                -- P0: slots affichés (source de vérité booking), en fin pour migration ALTER
                pending_slots_display_json TEXT
            )
        """)
        
        # Index pour performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_last_seen 
            ON sessions(last_seen_at)
        """)
        
        # Migration: ajouter colonne pending_slots_display_json si absente
        try:
            cursor.execute("ALTER TABLE sessions ADD COLUMN pending_slots_display_json TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # colonne déjà présente
        conn.close()
    
    def _serialize_session(self, session: Session) -> Dict[str, Any]:
        """Convertit une Session en dict pour SQLite."""
        return {
            "conv_id": session.conv_id,
            "state": session.state,
            "channel": session.channel,
            "customer_phone": session.customer_phone,
            
            # Qualif data
            "name": session.qualif_data.name,
            "motif": session.qualif_data.motif,
            "pref": session.qualif_data.pref,
            "contact": session.qualif_data.contact,
            "contact_type": session.qualif_data.contact_type,
            
            # Counters
            "no_match_turns": session.no_match_turns,
            "confirm_retry_count": session.confirm_retry_count,
            "contact_retry_count": session.contact_retry_count,
            
            # Partial data
            "partial_phone_digits": session.partial_phone_digits,
            
            # Pending data (JSON) - inclure source pour booking (google vs sqlite/pg)
            # start: toujours ISO string (évite json.dumps(datetime) qui échoue)
            "pending_slots_json": json.dumps([
                {
                    "idx": s.idx, "label": s.label, "slot_id": s.slot_id,
                    "start": _slot_start_to_iso(getattr(s, "start", None)),
                    "day": getattr(s, "day", ""),
                    "hour": getattr(s, "hour", 0),
                    "label_vocal": getattr(s, "label_vocal", ""),
                    "source": getattr(s, "source", "sqlite"),
                }
                for s in session.pending_slots
            ]) if session.pending_slots else None,
            "pending_slot_choice": session.pending_slot_choice,
            "pending_cancel_slot_json": json.dumps(session.pending_cancel_slot) if session.pending_cancel_slot else None,
            "pending_slots_display_json": json.dumps(getattr(session, "pending_slots_display", None) or []),
            
            # Flags
            "extracted_name": 1 if session.extracted_name else 0,
            "extracted_motif": 1 if session.extracted_motif else 0,
            "extracted_pref": 1 if session.extracted_pref else 0,
            "motif_help_used": 1 if session.motif_help_used else 0,
            
            # Metadata
            "last_seen_at": session.last_seen_at.isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            
            # Backup complet (pickle)
            "session_pickle": base64.b64encode(pickle.dumps(session)).decode('utf-8'),
        }
    
    def _deserialize_session(self, row: tuple) -> Session:
        """Reconstruit une Session depuis une row SQLite."""
        # Essayer d'abord de restaurer depuis le pickle (plus fiable)
        try:
            session_pickle = row[22] if len(row) > 22 else None
            if session_pickle:
                session = pickle.loads(base64.b64decode(session_pickle))
                # P0: Ne jamais préférer le cache au pickle DB — la DB est la source de vérité
                # (évite session stale sans pending_slots_display → "problème technique")
                return session
        except Exception as e:
            print(f"⚠️ Could not unpickle session: {e}")
        
        # Sinon reconstruire depuis les colonnes
        session = Session(conv_id=row[0])
        session.state = row[1]
        session.channel = row[2]
        session.customer_phone = row[3]
        
        # Qualif data
        session.qualif_data = QualifData(
            name=row[4],
            motif=row[5],
            pref=row[6],
            contact=row[7],
            contact_type=row[8],
        )
        
        # Counters
        session.no_match_turns = row[9] or 0
        session.confirm_retry_count = row[10] or 0
        session.contact_retry_count = row[11] or 0
        
        # Partial data
        session.partial_phone_digits = row[12] or ""
        
        # Pending data (JSON) - recréer les SlotDisplay
        if row[13]:  # pending_slots_json
            try:
                from backend.prompts import SlotDisplay
                slots_data = json.loads(row[13])
                session.pending_slots = [
                    SlotDisplay(
                        idx=s["idx"], label=s["label"], slot_id=s["slot_id"],
                        start=s.get("start", ""), day=s.get("day", ""),
                        hour=s.get("hour", 0), label_vocal=s.get("label_vocal", ""),
                        source=s.get("source", "sqlite"),
                    )
                    for s in slots_data
                ]
                # Aussi remplir les pending_slot_ids et labels pour compatibilité
                session.pending_slot_ids = [s.slot_id for s in session.pending_slots]
                session.pending_slot_labels = [s.label for s in session.pending_slots]
            except Exception as e:
                print(f"⚠️ Error deserializing pending_slots: {e}")
                session.pending_slots = []
        
        session.pending_slot_choice = row[14]

        if row[15]:  # pending_cancel_slot_json
            try:
                session.pending_cancel_slot = json.loads(row[15])
            except Exception:
                session.pending_cancel_slot = None

        # Flags
        session.extracted_name = bool(row[16])
        session.extracted_motif = bool(row[17])
        session.extracted_pref = bool(row[18])
        session.motif_help_used = bool(row[19])

        # Metadata
        if row[20]:  # last_seen_at
            try:
                session.last_seen_at = datetime.fromisoformat(row[20])
            except Exception:
                pass

        # P0: slots affichés (colonne en fin de table pour compat migration)
        if len(row) > 23 and row[23]:
            try:
                session.pending_slots_display = json.loads(row[23])
            except Exception:
                session.pending_slots_display = []
        else:
            session.pending_slots_display = []

        return session
    
    def save(self, session: Session) -> None:
        """Sauvegarde une session dans SQLite."""
        import time
        t_start = time.time()
        
        # Mettre à jour le cache mémoire
        self._memory_cache[session.conv_id] = session
        
        # Sauvegarder dans SQLite
        data = self._serialize_session(session)
        print(f"💾 Saving session {session.conv_id}: state={session.state}, name={session.qualif_data.name}, pending_slots={len(session.pending_slots or [])}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO sessions (
                conv_id, state, channel, customer_phone,
                name, motif, pref, contact, contact_type,
                no_match_turns, confirm_retry_count, contact_retry_count,
                partial_phone_digits,
                pending_slots_json, pending_slot_choice, pending_cancel_slot_json,
                extracted_name, extracted_motif, extracted_pref, motif_help_used,
                last_seen_at, created_at, session_pickle, pending_slots_display_json
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?
            )
        """, (
            data["conv_id"], data["state"], data["channel"], data["customer_phone"],
            data["name"], data["motif"], data["pref"], data["contact"], data["contact_type"],
            data["no_match_turns"], data["confirm_retry_count"], data["contact_retry_count"],
            data["partial_phone_digits"],
            data["pending_slots_json"], data["pending_slot_choice"], data["pending_cancel_slot_json"],
            data["extracted_name"], data["extracted_motif"], data["extracted_pref"], data["motif_help_used"],
            data["last_seen_at"], data["created_at"], data["session_pickle"], data["pending_slots_display_json"]
        ))
        
        conn.commit()
        conn.close()
        
        elapsed_ms = (time.time() - t_start) * 1000
        print(f"💾 Session saved in {elapsed_ms:.0f}ms")
    
    def get(self, conv_id: str) -> Optional[Session]:
        """Récupère une session depuis SQLite."""
        import time
        t_start = time.time()
        
        # Check cache mémoire d'abord (RAPIDE)
        if conv_id in self._memory_cache:
            elapsed = (time.time() - t_start) * 1000
            print(f"💾 Session {conv_id} from MEMORY cache ({elapsed:.0f}ms)")
            return self._memory_cache[conv_id]
        
        # Sinon chercher dans SQLite (LENT)
        t_db_start = time.time()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM sessions WHERE conv_id = ?", (conv_id,))
        row = cursor.fetchone()
        conn.close()
        
        elapsed_db = (time.time() - t_db_start) * 1000
        
        if not row:
            print(f"💾 Session {conv_id} NOT FOUND in SQLite ({elapsed_db:.0f}ms)")
            return None
        
        session = self._deserialize_session(row)
        elapsed_total = (time.time() - t_start) * 1000
        print(f"💾 Loaded {conv_id} from SQLite ({elapsed_total:.0f}ms): state={session.state}, name={session.qualif_data.name}, pending_slots={len(session.pending_slots or [])}")
        self._memory_cache[conv_id] = session
        return session
    
    def get_or_create(self, conv_id: str) -> Session:
        """Récupère ou crée une session."""
        session = self.get(conv_id)
        if session is None:
            session = Session(conv_id=conv_id)
            self.save(session)
        return session
    
    def delete(self, conv_id: str) -> None:
        """Supprime une session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE conv_id = ?", (conv_id,))
        conn.commit()
        conn.close()
        
        if conv_id in self._memory_cache:
            del self._memory_cache[conv_id]
    
    def cleanup_old_sessions(self, hours: int = 24) -> int:
        """
        Supprime les sessions plus vieilles que X heures.
        
        Returns:
            Nombre de sessions supprimées
        """
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE last_seen_at < ?", (cutoff,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"🧹 Cleaned up {deleted} old sessions")
        return deleted
