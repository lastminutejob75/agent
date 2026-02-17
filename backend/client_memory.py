"""
Mémoire client persistante - inspiré du pattern Clawdbot.

Ce module gère la reconnaissance des clients récurrents et leur historique.
Permet de personnaliser l'accueil : "Bonjour M. Dupont, toujours pour un contrôle ?"
"""

from __future__ import annotations

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Client:
    """Représente un client dans la mémoire."""
    id: int
    phone: Optional[str]
    name: str
    email: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_contact: datetime = field(default_factory=datetime.utcnow)
    total_bookings: int = 0
    last_motif: Optional[str] = None
    preferred_time: Optional[str] = None  # "matin" ou "aprem"
    notes: Optional[str] = None


@dataclass
class BookingHistory:
    """Historique d'un RDV."""
    id: int
    client_id: int
    slot_label: str
    motif: str
    status: str  # "confirmed", "cancelled", "completed", "no_show"
    created_at: datetime
    completed_at: Optional[datetime] = None


class ClientMemory:
    """
    Gestionnaire de mémoire client.
    
    Usage:
        memory = ClientMemory()
        
        # Reconnaître un client
        client = memory.get_by_phone("0612345678")
        if client:
            greeting = memory.get_personalized_greeting(client)
            # "Bonjour M. Dupont, toujours pour un contrôle ?"
        
        # Créer/mettre à jour un client
        client = memory.get_or_create(phone="0612345678", name="Jean Dupont")
        
        # Enregistrer un RDV
        memory.record_booking(client.id, slot_label="Lundi 10h", motif="contrôle")
    """
    
    def __init__(self, db_path: str = "data/clients.db"):
        """
        Initialise la mémoire client.
        
        Args:
            db_path: Chemin vers la base SQLite
        """
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self) -> None:
        """Crée les tables si elles n'existent pas."""
        # Créer le dossier data si nécessaire
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table clients
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE,
                name TEXT NOT NULL,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_contact TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_bookings INTEGER DEFAULT 0,
                last_motif TEXT,
                preferred_time TEXT,
                notes TEXT
            )
        """)
        
        # Index sur phone pour recherche rapide
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_clients_phone ON clients(phone)
        """)
        
        # Table historique des RDV
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS booking_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                slot_label TEXT NOT NULL,
                motif TEXT,
                status TEXT DEFAULT 'confirmed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id)
            )
        """)
        
        # Index sur client_id
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_client ON booking_history(client_id)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Client memory initialized at {self.db_path}")
    
    # ============================================
    # CRUD Clients
    # ============================================
    
    def get_by_phone(self, phone: str) -> Optional[Client]:
        """
        Récupère un client par son numéro de téléphone.
        
        Args:
            phone: Numéro normalisé (ex: "0612345678")
            
        Returns:
            Client ou None si non trouvé
        """
        from backend import config
        config._sqlite_guard("client_memory.get_by_phone")
        phone_normalized = self._normalize_phone(phone)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM clients WHERE phone = ?",
            (phone_normalized,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return self._row_to_client(row)
        return None
    
    def get_by_name(self, name: str) -> Optional[Client]:
        """
        Récupère un client par son nom (recherche approximative).
        
        Args:
            name: Nom du client
            
        Returns:
            Client ou None si non trouvé
        """
        from backend import config
        config._sqlite_guard("client_memory.get_by_name")
        name_lower = name.lower().strip()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Recherche exacte d'abord
        cursor.execute(
            "SELECT * FROM clients WHERE LOWER(name) = ?",
            (name_lower,)
        )
        row = cursor.fetchone()
        
        # Si pas trouvé, recherche partielle
        if not row:
            cursor.execute(
                "SELECT * FROM clients WHERE LOWER(name) LIKE ?",
                (f"%{name_lower}%",)
            )
            row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return self._row_to_client(row)
        return None
    
    def get_or_create(
        self,
        phone: Optional[str] = None,
        name: str = "",
        email: Optional[str] = None
    ) -> Client:
        """
        Récupère ou crée un client.
        
        Args:
            phone: Numéro de téléphone
            name: Nom du client
            email: Email du client
            
        Returns:
            Client existant ou nouvellement créé
        """
        from backend import config
        config._sqlite_guard("client_memory.get_or_create")
        # Essayer de trouver par téléphone d'abord
        if phone:
            existing = self.get_by_phone(phone)
            if existing:
                # Mettre à jour le nom si fourni
                if name and name != existing.name:
                    self._update_client(existing.id, name=name)
                    existing.name = name
                return existing
        
        # Essayer par nom ensuite
        if name:
            existing = self.get_by_name(name)
            if existing:
                # Mettre à jour le téléphone si fourni
                if phone and phone != existing.phone:
                    self._update_client(existing.id, phone=self._normalize_phone(phone))
                    existing.phone = self._normalize_phone(phone)
                return existing
        
        # Créer un nouveau client
        return self._create_client(phone, name, email)
    
    def _create_client(
        self,
        phone: Optional[str],
        name: str,
        email: Optional[str] = None
    ) -> Client:
        """Crée un nouveau client."""
        phone_normalized = self._normalize_phone(phone) if phone else None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO clients (phone, name, email, created_at, last_contact)
            VALUES (?, ?, ?, ?, ?)
            """,
            (phone_normalized, name, email, datetime.utcnow(), datetime.utcnow())
        )
        
        client_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Created new client: {name} (id={client_id})")
        
        return Client(
            id=client_id,
            phone=phone_normalized,
            name=name,
            email=email
        )
    
    def _update_client(self, client_id: int, **kwargs) -> None:
        """Met à jour un client."""
        from backend import config
        config._sqlite_guard("client_memory._update_client")
        if not kwargs:
            return
        
        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [client_id]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            f"UPDATE clients SET {set_clause} WHERE id = ?",
            values
        )
        
        conn.commit()
        conn.close()
    
    # ============================================
    # Historique & Stats
    # ============================================
    
    def record_booking(
        self,
        client_id: int,
        slot_label: str,
        motif: str,
        status: str = "confirmed"
    ) -> int:
        """
        Enregistre un nouveau RDV dans l'historique.
        
        Args:
            client_id: ID du client
            slot_label: Label du créneau (ex: "Lundi 10h")
            motif: Motif du RDV
            status: Statut initial
            
        Returns:
            ID du booking créé
        """
        from backend import config
        config._sqlite_guard("client_memory.record_booking")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Créer le booking
        cursor.execute(
            """
            INSERT INTO booking_history (client_id, slot_label, motif, status, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (client_id, slot_label, motif, status, datetime.utcnow())
        )
        booking_id = cursor.lastrowid
        
        # Mettre à jour le client
        cursor.execute(
            """
            UPDATE clients 
            SET total_bookings = total_bookings + 1,
                last_contact = ?,
                last_motif = ?
            WHERE id = ?
            """,
            (datetime.utcnow(), motif, client_id)
        )
        
        conn.commit()
        conn.close()
        
        logger.info(f"Recorded booking for client {client_id}: {slot_label} ({motif})")
        
        return booking_id
    
    def get_history(self, client_id: int, limit: int = 10) -> List[BookingHistory]:
        """
        Récupère l'historique des RDV d'un client.
        
        Args:
            client_id: ID du client
            limit: Nombre max de résultats
            
        Returns:
            Liste des RDV (plus récent en premier)
        """
        from backend import config
        config._sqlite_guard("client_memory.get_history")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT * FROM booking_history 
            WHERE client_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (client_id, limit)
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_booking(row) for row in rows]
    
    def is_returning_client(self, phone: str) -> bool:
        """
        Vérifie si c'est un client récurrent (> 1 RDV).
        
        Args:
            phone: Numéro de téléphone
            
        Returns:
            True si client récurrent
        """
        client = self.get_by_phone(phone)
        return client is not None and client.total_bookings >= 1
    
    # ============================================
    # Personnalisation
    # ============================================
    
    def get_personalized_greeting(
        self,
        client: Client,
        channel: str = "vocal"
    ) -> Optional[str]:
        """
        Génère un greeting personnalisé pour un client récurrent.
        
        Args:
            client: Client reconnu
            channel: Canal (vocal/web)
            
        Returns:
            Greeting personnalisé ou None si client inconnu
        """
        if not client or client.total_bookings == 0:
            return None
        
        # Pas de prénom ; marqueur de reconnaissance pour client connu
        # Greeting selon le dernier motif
        if client.last_motif:
            if channel == "vocal":
                return f"Rebonjour. Je vous retrouve. Toujours pour {client.last_motif} ?"
            return f"Bonjour ! Vous souhaitez prendre un nouveau rendez-vous pour {client.last_motif} ?"
        
        # Greeting générique avec reconnaissance
        if channel == "vocal":
            return "Rebonjour. Je vous retrouve, comment puis-je vous aider ?"
        return "Bonjour ! Comment puis-je vous aider ?"
    
    def get_preferred_time_suggestion(self, client: Client) -> Optional[str]:
        """
        Suggère un créneau basé sur les préférences du client.
        
        Args:
            client: Client
            
        Returns:
            Suggestion de créneau ou None
        """
        if not client.preferred_time:
            return None
        
        if client.preferred_time == "matin":
            return "Vous préférez habituellement le matin, c'est toujours le cas ?"
        elif client.preferred_time == "aprem":
            return "Vous préférez habituellement l'après-midi, c'est toujours le cas ?"
        
        return None
    
    # ============================================
    # Rapports quotidiens (clients avec email)
    # ============================================

    def get_clients_with_email(self) -> List[tuple]:
        """
        Liste des clients ayant un email (pour envoi rapport quotidien).
        Returns: List[(id, name, email), ...]
        """
        from backend import config
        config._sqlite_guard("client_memory.get_clients_with_email")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, email FROM clients WHERE email IS NOT NULL AND email != ''"
        )
        rows = cursor.fetchall()
        conn.close()
        return [(r[0], r[1], r[2]) for r in rows]

    # ============================================
    # Stats pour rapports
    # ============================================
    
    def get_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Récupère les stats clients sur une période.
        
        Args:
            days: Nombre de jours à analyser
            
        Returns:
            Dict avec les stats
        """
        from backend import config
        config._sqlite_guard("client_memory.get_stats")
        since = datetime.utcnow() - timedelta(days=days)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total clients
        cursor.execute("SELECT COUNT(*) FROM clients")
        total_clients = cursor.fetchone()[0]
        
        # Nouveaux clients
        cursor.execute(
            "SELECT COUNT(*) FROM clients WHERE created_at >= ?",
            (since,)
        )
        new_clients = cursor.fetchone()[0]
        
        # Clients actifs (au moins 1 RDV dans la période)
        cursor.execute(
            """
            SELECT COUNT(DISTINCT client_id) FROM booking_history 
            WHERE created_at >= ?
            """,
            (since,)
        )
        active_clients = cursor.fetchone()[0]
        
        # Total bookings
        cursor.execute(
            "SELECT COUNT(*) FROM booking_history WHERE created_at >= ?",
            (since,)
        )
        total_bookings = cursor.fetchone()[0]
        
        # Top clients
        cursor.execute(
            """
            SELECT c.name, COUNT(b.id) as count
            FROM clients c
            JOIN booking_history b ON c.id = b.client_id
            WHERE b.created_at >= ?
            GROUP BY c.id
            ORDER BY count DESC
            LIMIT 5
            """,
            (since,)
        )
        top_clients = cursor.fetchall()
        
        conn.close()
        
        return {
            "total_clients": total_clients,
            "new_clients": new_clients,
            "active_clients": active_clients,
            "total_bookings": total_bookings,
            "top_clients": [{"name": r[0], "bookings": r[1]} for r in top_clients],
            "period_days": days,
        }
    
    # ============================================
    # Helpers
    # ============================================
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalise un numéro de téléphone."""
        if not phone:
            return ""
        
        # Enlever espaces, tirets, points
        phone = phone.replace(" ", "").replace("-", "").replace(".", "")
        
        # Convertir +33 en 0
        if phone.startswith("+33"):
            phone = "0" + phone[3:]
        elif phone.startswith("33"):
            phone = "0" + phone[2:]
        
        return phone
    
    def _row_to_client(self, row: tuple) -> Client:
        """Convertit une row SQLite en Client."""
        return Client(
            id=row[0],
            phone=row[1],
            name=row[2],
            email=row[3],
            created_at=datetime.fromisoformat(row[4]) if row[4] else datetime.utcnow(),
            last_contact=datetime.fromisoformat(row[5]) if row[5] else datetime.utcnow(),
            total_bookings=row[6] or 0,
            last_motif=row[7],
            preferred_time=row[8],
            notes=row[9],
        )
    
    def _row_to_booking(self, row: tuple) -> BookingHistory:
        """Convertit une row SQLite en BookingHistory."""
        return BookingHistory(
            id=row[0],
            client_id=row[1],
            slot_label=row[2],
            motif=row[3],
            status=row[4],
            created_at=datetime.fromisoformat(row[5]) if row[5] else datetime.utcnow(),
            completed_at=datetime.fromisoformat(row[6]) if row[6] else None,
        )


# ============================================
# Hybride PG / SQLite (multi-tenant)
# ============================================

class HybridClientMemory:
    """
    Délègue à PG (tenant_clients / tenant_booking_history) quand USE_PG_TENANTS
    et tenant_id connu, sinon à ClientMemory SQLite.
    Toutes les méthodes CRUD acceptent tenant_id optionnel (sinon lu depuis current_tenant_id).
    """

    def __init__(self) -> None:
        self._sqlite = ClientMemory()

    def _resolve_tenant(self, tenant_id: Optional[int]) -> Optional[int]:
        if tenant_id is not None:
            return tenant_id
        try:
            from backend.tenant_routing import current_tenant_id
            t = current_tenant_id.get()
            if t and str(t).strip():
                return int(t)
        except Exception:
            pass
        return None

    def _use_pg(self, tenant_id: Optional[int]) -> bool:
        from backend import config
        if not config.USE_PG_TENANTS or tenant_id is None:
            return False
        try:
            from backend import client_memory_pg
            return bool(client_memory_pg._pg_url())
        except Exception:
            return False

    def get_by_phone(self, phone: str, tenant_id: Optional[int] = None) -> Optional[Client]:
        tid = self._resolve_tenant(tenant_id)
        if self._use_pg(tid):
            from backend import client_memory_pg
            return client_memory_pg.pg_get_client_by_phone(tid, phone)
        return self._sqlite.get_by_phone(phone)

    def get_by_name(self, name: str, tenant_id: Optional[int] = None) -> Optional[Client]:
        tid = self._resolve_tenant(tenant_id)
        if self._use_pg(tid):
            from backend import client_memory_pg
            return client_memory_pg.pg_get_client_by_name(tid, name)
        return self._sqlite.get_by_name(name)

    def get_or_create(
        self,
        phone: Optional[str] = None,
        name: str = "",
        email: Optional[str] = None,
        tenant_id: Optional[int] = None,
    ) -> Client:
        tid = self._resolve_tenant(tenant_id)
        if self._use_pg(tid):
            from backend import client_memory_pg
            return client_memory_pg.pg_get_or_create_client(tid, phone=phone, name=name, email=email)
        return self._sqlite.get_or_create(phone=phone, name=name, email=email)

    def record_booking(
        self,
        client_id: int,
        slot_label: str,
        motif: str,
        status: str = "confirmed",
        tenant_id: Optional[int] = None,
    ) -> int:
        tid = self._resolve_tenant(tenant_id)
        if self._use_pg(tid):
            from backend import client_memory_pg
            return client_memory_pg.pg_record_booking(tid, client_id, slot_label, motif, status)
        return self._sqlite.record_booking(client_id, slot_label, motif, status)

    def get_history(
        self,
        client_id: int,
        limit: int = 10,
        tenant_id: Optional[int] = None,
    ) -> List[BookingHistory]:
        tid = self._resolve_tenant(tenant_id)
        if self._use_pg(tid):
            from backend import client_memory_pg
            return client_memory_pg.pg_get_history(tid, client_id, limit)
        return self._sqlite.get_history(client_id, limit)

    def is_returning_client(self, phone: str, tenant_id: Optional[int] = None) -> bool:
        client = self.get_by_phone(phone, tenant_id=tenant_id)
        return client is not None and client.total_bookings >= 1

    def get_personalized_greeting(
        self,
        client: Client,
        channel: str = "vocal",
    ) -> Optional[str]:
        return self._sqlite.get_personalized_greeting(client, channel=channel)

    def get_preferred_time_suggestion(self, client: Client) -> Optional[str]:
        return self._sqlite.get_preferred_time_suggestion(client)

    def get_clients_with_email(self, tenant_id: Optional[int] = None) -> List[tuple]:
        tid = self._resolve_tenant(tenant_id)
        if self._use_pg(tid):
            from backend import client_memory_pg
            return client_memory_pg.pg_get_clients_with_email(tid)
        return self._sqlite.get_clients_with_email()

    def get_stats(self, days: int = 30, tenant_id: Optional[int] = None) -> Dict[str, Any]:
        tid = self._resolve_tenant(tenant_id)
        if self._use_pg(tid):
            from backend import client_memory_pg
            return client_memory_pg.pg_get_stats(tid, days)
        return self._sqlite.get_stats(days)


# ============================================
# Singleton pour usage global
# ============================================

_memory_instance: Optional[HybridClientMemory] = None


def get_client_memory() -> HybridClientMemory:
    """Récupère l'instance singleton (HybridClientMemory : PG si tenant_id, sinon SQLite)."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = HybridClientMemory()
    return _memory_instance
