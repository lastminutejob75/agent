"""
Rapport quotidien automatique - inspiré du pattern Clawdbot.

Ce module génère des rapports d'activité et les envoie au gérant.
Supporte plusieurs canaux de notification (SMS, WhatsApp, Email, Telegram).

Configuration via variables d'environnement:
    REPORT_CHANNEL=telegram|sms|whatsapp|email
    
    Pour Telegram:
        TELEGRAM_BOT_TOKEN=xxx
        TELEGRAM_OWNER_ID=xxx
    
    Pour SMS/WhatsApp (Twilio):
        TWILIO_ACCOUNT_SID=xxx
        TWILIO_AUTH_TOKEN=xxx
        TWILIO_PHONE_NUMBER=+33xxx (pour SMS)
        TWILIO_WHATSAPP_NUMBER=+14155238886 (pour WhatsApp)
        OWNER_PHONE_NUMBER=+33xxx
    
    Pour Email (SMTP):
        SMTP_HOST=smtp.gmail.com
        SMTP_PORT=587
        SMTP_EMAIL=xxx
        SMTP_PASSWORD=xxx
        OWNER_EMAIL=xxx

Peut être déclenché par cron job ou manuellement.
"""

from __future__ import annotations

import os
import logging
import smtplib
from abc import ABC, abstractmethod
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================
# Canaux de notification (multi-canal)
# ============================================

class NotificationChannel(ABC):
    """Interface abstraite pour tous les canaux de notification."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nom du canal pour les logs."""
        pass
    
    @abstractmethod
    def send(self, message: str, subject: Optional[str] = None) -> bool:
        """
        Envoie un message via ce canal.
        
        Args:
            message: Contenu du message
            subject: Sujet (pour email uniquement)
            
        Returns:
            True si envoyé avec succès
        """
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Vérifie si le canal est correctement configuré."""
        pass


class TelegramChannel(NotificationChannel):
    """Envoi par Telegram Bot."""
    
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_OWNER_ID")
    
    @property
    def name(self) -> str:
        return "telegram"
    
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)
    
    def send(self, message: str, subject: Optional[str] = None) -> bool:
        import requests
        
        if not self.is_configured():
            logger.warning("Telegram not configured (missing TELEGRAM_BOT_TOKEN or TELEGRAM_OWNER_ID)")
            return False
        
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"📱 Telegram envoyé")
                logger.info("Report sent via Telegram")
                return True
            else:
                logger.error(f"Telegram error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Telegram failed: {e}")
            return False


class SMSChannel(NotificationChannel):
    """Envoi par SMS via Twilio."""
    
    def __init__(self):
        from backend.services.sms_service import sms_is_configured
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.to_number = os.getenv("OWNER_PHONE_NUMBER")
        self._auth_ready = sms_is_configured()
    
    @property
    def name(self) -> str:
        return "sms"
    
    def is_configured(self) -> bool:
        return bool(self._auth_ready and self.to_number)
    
    def send(self, message: str, subject: Optional[str] = None) -> bool:
        if not self.is_configured():
            logger.warning("SMS not configured (missing Twilio credentials)")
            return False
        
        try:
            from backend.services.sms_service import get_twilio_client

            client = get_twilio_client()
            if client is None:
                logger.warning("SMS not configured (missing Twilio credentials)")
                return False
            
            # Tronquer si trop long pour SMS (160 chars)
            if len(message) > 1600:
                message = message[:1550] + "\n\n[...tronqué]"
            
            msg = client.messages.create(
                body=message,
                from_=self.from_number,
                to=self.to_number
            )
            
            print(f"📱 SMS envoyé: {msg.sid}")
            logger.info(f"Report sent via SMS: {msg.sid}")
            return True
            
        except ImportError:
            logger.error("Twilio not installed. Run: pip install twilio")
            return False
        except Exception as e:
            logger.error(f"SMS failed: {e}")
            return False


class WhatsAppChannel(NotificationChannel):
    """Envoi par WhatsApp via Twilio."""
    
    def __init__(self):
        from backend.services.sms_service import twilio_auth_configured
        self.from_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "+14155238886")  # Sandbox par défaut
        self.to_number = os.getenv("OWNER_PHONE_NUMBER")
        self._auth_ready = twilio_auth_configured()
    
    @property
    def name(self) -> str:
        return "whatsapp"
    
    def is_configured(self) -> bool:
        return bool(self._auth_ready and self.to_number)
    
    def send(self, message: str, subject: Optional[str] = None) -> bool:
        if not self.is_configured():
            logger.warning("WhatsApp not configured (missing Twilio credentials)")
            return False
        
        try:
            from backend.services.sms_service import get_twilio_client

            client = get_twilio_client()
            if client is None:
                logger.warning("WhatsApp not configured (missing Twilio credentials)")
                return False
            
            msg = client.messages.create(
                body=message,
                from_=f"whatsapp:{self.from_number}",
                to=f"whatsapp:{self.to_number}"
            )
            
            print(f"💬 WhatsApp envoyé: {msg.sid}")
            logger.info(f"Report sent via WhatsApp: {msg.sid}")
            return True
            
        except ImportError:
            logger.error("Twilio not installed. Run: pip install twilio")
            return False
        except Exception as e:
            logger.error(f"WhatsApp failed: {e}")
            return False


class EmailChannel(NotificationChannel):
    """Envoi par Email via SMTP."""
    
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.email_from = os.getenv("SMTP_EMAIL")
        self.password = os.getenv("SMTP_PASSWORD")
        self.email_to = os.getenv("OWNER_EMAIL")
    
    @property
    def name(self) -> str:
        return "email"
    
    def is_configured(self) -> bool:
        return bool(self.email_from and self.password and self.email_to)
    
    def send(self, message: str, subject: Optional[str] = None) -> bool:
        if not self.is_configured():
            logger.warning("Email not configured (missing SMTP credentials)")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = subject or f"📊 Rapport UWI - {date.today().strftime('%d/%m/%Y')}"
            
            # Version texte simple
            msg.attach(MIMEText(message, 'plain'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_from, self.password)
                server.send_message(msg)
            
            print(f"📧 Email envoyé à {self.email_to}")
            logger.info(f"Report sent via Email to {self.email_to}")
            return True
            
        except Exception as e:
            logger.error(f"Email failed: {e}")
            return False


# Factory pour créer le bon canal
def get_notification_channel(channel_type: Optional[str] = None) -> NotificationChannel:
    """
    Retourne le canal de notification configuré.
    
    Args:
        channel_type: Type de canal (telegram, sms, whatsapp, email).
                     Si None, utilise REPORT_CHANNEL env var.
    
    Returns:
        Instance du canal approprié
    """
    if channel_type is None:
        channel_type = os.getenv("REPORT_CHANNEL", "telegram").lower()
    
    channels = {
        "telegram": TelegramChannel,
        "sms": SMSChannel,
        "whatsapp": WhatsAppChannel,
        "email": EmailChannel,
    }
    
    if channel_type not in channels:
        logger.warning(f"Unknown channel '{channel_type}', falling back to telegram")
        channel_type = "telegram"
    
    return channels[channel_type]()


def send_with_fallback(message: str, preferred_order: Optional[List[str]] = None) -> bool:
    """
    Envoie un message en essayant plusieurs canaux en cas d'échec.
    
    Args:
        message: Message à envoyer
        preferred_order: Ordre de préférence des canaux
                        (défaut: telegram, whatsapp, sms, email)
    
    Returns:
        True si envoyé via au moins un canal
    """
    if preferred_order is None:
        preferred_order = ["telegram", "whatsapp", "sms", "email"]
    
    for channel_type in preferred_order:
        channel = get_notification_channel(channel_type)
        
        if not channel.is_configured():
            logger.debug(f"Channel {channel_type} not configured, skipping")
            continue
        
        if channel.send(message):
            logger.info(f"Message sent via {channel_type}")
            return True
        else:
            logger.warning(f"Channel {channel_type} failed, trying next...")
    
    logger.error("All notification channels failed!")
    return False


def send_multi_channel(message: str, channels: List[str]) -> Dict[str, bool]:
    """
    Envoie un message sur plusieurs canaux simultanément.
    
    Args:
        message: Message à envoyer
        channels: Liste des canaux à utiliser
    
    Returns:
        Dict avec le résultat pour chaque canal
    """
    results = {}
    
    for channel_type in channels:
        channel = get_notification_channel(channel_type)
        results[channel_type] = channel.send(message)
    
    return results


@dataclass
class DailyStats:
    """Statistiques quotidiennes."""
    date: date
    total_calls: int = 0
    bookings: int = 0
    cancellations: int = 0
    modifications: int = 0
    faq_answered: int = 0
    transfers: int = 0
    no_response: int = 0
    
    # Détail par motif
    bookings_by_motif: Dict[str, int] = None
    
    # Métriques temps
    avg_response_time_ms: float = 0
    peak_hour: Optional[int] = None
    
    # Prévisions
    tomorrow_bookings: int = 0
    
    def __post_init__(self):
        if self.bookings_by_motif is None:
            self.bookings_by_motif = {}
    
    @property
    def conversion_rate(self) -> float:
        """Taux de conversion appels → RDV."""
        if self.total_calls == 0:
            return 0
        return (self.bookings / self.total_calls) * 100


class ReportGenerator:
    """
    Générateur de rapports.
    
    Usage:
        generator = ReportGenerator()
        
        # Rapport du jour
        report = generator.generate_daily_report()
        print(report)
        
        # Envoyer par Telegram
        generator.send_telegram(report)
    """
    
    def __init__(self, db_path: str = "data/stats.db"):
        """
        Initialise le générateur.
        
        Args:
            db_path: Chemin vers la base de stats
        """
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self) -> None:
        """Crée les tables de stats si nécessaires."""
        import sqlite3
        from pathlib import Path
        
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table des interactions (chaque appel/message)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id TEXT NOT NULL,
                channel TEXT DEFAULT 'vocal',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                intent TEXT,
                outcome TEXT,
                duration_ms INTEGER,
                motif TEXT,
                client_name TEXT,
                client_phone TEXT
            )
        """)
        
        # Index pour requêtes par date
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_interactions_date 
            ON interactions(DATE(timestamp))
        """)
        
        conn.commit()
        conn.close()
    
    # ============================================
    # Enregistrement des stats
    # ============================================
    
    def record_interaction(
        self,
        call_id: str,
        intent: str,
        outcome: str,
        channel: str = "vocal",
        duration_ms: int = 0,
        motif: Optional[str] = None,
        client_name: Optional[str] = None,
        client_phone: Optional[str] = None
    ) -> None:
        """
        Enregistre une interaction pour les stats.
        
        Args:
            call_id: ID de l'appel/conversation
            intent: Intent détecté (BOOKING, FAQ, CANCEL, etc.)
            outcome: Résultat (confirmed, transferred, abandoned, etc.)
            channel: Canal (vocal, web, whatsapp)
            duration_ms: Durée totale en ms
            motif: Motif du RDV si applicable
            client_name: Nom du client
            client_phone: Téléphone du client
        """
        import sqlite3
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO interactions 
            (call_id, channel, intent, outcome, duration_ms, motif, client_name, client_phone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (call_id, channel, intent, outcome, duration_ms, motif, client_name, client_phone)
        )
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Recorded interaction: {call_id} ({intent} → {outcome})")
    
    # ============================================
    # Génération des stats
    # ============================================
    
    def get_daily_stats(self, target_date: Optional[date] = None) -> DailyStats:
        """
        Récupère les stats pour une journée.
        
        Args:
            target_date: Date cible (défaut: aujourd'hui)
            
        Returns:
            DailyStats avec toutes les métriques
        """
        import sqlite3
        
        if target_date is None:
            target_date = date.today()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total calls
        cursor.execute(
            "SELECT COUNT(*) FROM interactions WHERE DATE(timestamp) = ?",
            (target_date.isoformat(),)
        )
        total_calls = cursor.fetchone()[0]
        
        # Bookings confirmés
        cursor.execute(
            """
            SELECT COUNT(*) FROM interactions 
            WHERE DATE(timestamp) = ? AND outcome = 'confirmed'
            """,
            (target_date.isoformat(),)
        )
        bookings = cursor.fetchone()[0]
        
        # Annulations
        cursor.execute(
            """
            SELECT COUNT(*) FROM interactions 
            WHERE DATE(timestamp) = ? AND intent = 'CANCEL' AND outcome = 'confirmed'
            """,
            (target_date.isoformat(),)
        )
        cancellations = cursor.fetchone()[0]
        
        # FAQ
        cursor.execute(
            """
            SELECT COUNT(*) FROM interactions 
            WHERE DATE(timestamp) = ? AND intent = 'FAQ'
            """,
            (target_date.isoformat(),)
        )
        faq_answered = cursor.fetchone()[0]
        
        # Transfers
        cursor.execute(
            """
            SELECT COUNT(*) FROM interactions 
            WHERE DATE(timestamp) = ? AND outcome = 'transferred'
            """,
            (target_date.isoformat(),)
        )
        transfers = cursor.fetchone()[0]
        
        # Bookings par motif
        cursor.execute(
            """
            SELECT motif, COUNT(*) FROM interactions 
            WHERE DATE(timestamp) = ? AND outcome = 'confirmed' AND motif IS NOT NULL
            GROUP BY motif
            """,
            (target_date.isoformat(),)
        )
        motif_rows = cursor.fetchall()
        bookings_by_motif = {row[0]: row[1] for row in motif_rows}
        
        # Temps de réponse moyen
        cursor.execute(
            """
            SELECT AVG(duration_ms) FROM interactions 
            WHERE DATE(timestamp) = ? AND duration_ms > 0
            """,
            (target_date.isoformat(),)
        )
        avg_response = cursor.fetchone()[0] or 0
        
        # Heure de pointe
        cursor.execute(
            """
            SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
            FROM interactions 
            WHERE DATE(timestamp) = ?
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 1
            """,
            (target_date.isoformat(),)
        )
        peak_row = cursor.fetchone()
        peak_hour = int(peak_row[0]) if peak_row else None
        
        # RDV de demain (depuis la table booking_history si disponible)
        tomorrow = target_date + timedelta(days=1)
        tomorrow_bookings = 0
        
        try:
            cursor.execute(
                """
                SELECT COUNT(*) FROM booking_history 
                WHERE DATE(created_at) = ? AND status = 'confirmed'
                """,
                (tomorrow.isoformat(),)
            )
            result = cursor.fetchone()
            if result:
                tomorrow_bookings = result[0]
        except:
            pass  # Table pas disponible
        
        conn.close()
        
        return DailyStats(
            date=target_date,
            total_calls=total_calls,
            bookings=bookings,
            cancellations=cancellations,
            faq_answered=faq_answered,
            transfers=transfers,
            bookings_by_motif=bookings_by_motif,
            avg_response_time_ms=avg_response,
            peak_hour=peak_hour,
            tomorrow_bookings=tomorrow_bookings,
        )
    
    # ============================================
    # Génération du rapport
    # ============================================
    
    def generate_daily_report(
        self,
        target_date: Optional[date] = None,
        business_name: str = "Cabinet Dupont"
    ) -> str:
        """
        Génère le rapport quotidien formaté.
        
        Args:
            target_date: Date cible (défaut: aujourd'hui)
            business_name: Nom du cabinet
            
        Returns:
            Rapport formaté pour Telegram/SMS
        """
        stats = self.get_daily_stats(target_date)
        
        # Header
        date_str = stats.date.strftime("%d/%m/%Y")
        report = f"📊 {business_name} - {date_str}\n"
        report += "─" * 30 + "\n\n"
        
        # Stats principales
        report += f"📞 {stats.total_calls} appels reçus\n"
        report += f"✅ {stats.bookings} RDV pris\n"
        
        if stats.cancellations > 0:
            report += f"❌ {stats.cancellations} annulations\n"
        
        if stats.faq_answered > 0:
            report += f"❓ {stats.faq_answered} questions FAQ\n"
        
        if stats.transfers > 0:
            report += f"📲 {stats.transfers} transferts humain\n"
        
        # Détail par motif
        if stats.bookings_by_motif:
            report += "\n📋 Détail des RDV:\n"
            for motif, count in sorted(stats.bookings_by_motif.items(), key=lambda x: -x[1]):
                report += f"  • {motif.capitalize()}: {count}\n"
        
        # Métriques
        report += "\n💡 Insights:\n"
        
        # Taux de conversion
        report += f"  • Conversion: {stats.conversion_rate:.0f}%"
        if stats.conversion_rate >= 50:
            report += " 👍\n"
        elif stats.conversion_rate >= 30:
            report += " 📈\n"
        else:
            report += " ⚠️\n"
        
        # Heure de pointe
        if stats.peak_hour is not None:
            report += f"  • Pic d'appels: {stats.peak_hour}h-{stats.peak_hour+1}h\n"
        
        # Temps de réponse
        if stats.avg_response_time_ms > 0:
            avg_sec = stats.avg_response_time_ms / 1000
            report += f"  • Temps moyen: {avg_sec:.1f}s\n"
        
        # Prévisions demain
        if stats.tomorrow_bookings > 0:
            report += f"\n📅 Demain: {stats.tomorrow_bookings} RDV prévus\n"
        
        return report
    
    def generate_weekly_report(self, business_name: str = "Cabinet Dupont") -> str:
        """
        Génère un rapport hebdomadaire.
        
        Returns:
            Rapport formaté
        """
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        
        total_calls = 0
        total_bookings = 0
        total_cancellations = 0
        daily_stats = []
        
        for i in range(7):
            day = week_start + timedelta(days=i)
            if day > today:
                break
            stats = self.get_daily_stats(day)
            daily_stats.append(stats)
            total_calls += stats.total_calls
            total_bookings += stats.bookings
            total_cancellations += stats.cancellations
        
        # Header
        week_end = min(week_start + timedelta(days=6), today)
        report = f"📊 {business_name} - Semaine du {week_start.strftime('%d/%m')}\n"
        report += "═" * 35 + "\n\n"
        
        # Stats globales
        report += f"📞 Total appels: {total_calls}\n"
        report += f"✅ Total RDV: {total_bookings}\n"
        if total_cancellations > 0:
            report += f"❌ Annulations: {total_cancellations}\n"
        
        # Conversion
        if total_calls > 0:
            conversion = (total_bookings / total_calls) * 100
            report += f"\n📈 Taux de conversion: {conversion:.0f}%\n"
        
        # Jour par jour
        report += "\n📅 Détail par jour:\n"
        for stats in daily_stats:
            day_name = stats.date.strftime("%a")
            report += f"  {day_name}: {stats.bookings} RDV / {stats.total_calls} appels\n"
        
        return report
    
    # ============================================
    # Envoi du rapport (multi-canal)
    # ============================================
    
    def send_report(
        self,
        message: str,
        channel_type: Optional[str] = None,
        subject: Optional[str] = None
    ) -> bool:
        """
        Envoie un rapport via le canal configuré.
        
        Args:
            message: Message à envoyer
            channel_type: Canal à utiliser (défaut: REPORT_CHANNEL env)
            subject: Sujet pour email
            
        Returns:
            True si envoyé avec succès
        """
        channel = get_notification_channel(channel_type)
        
        if not channel.is_configured():
            logger.warning(f"Channel {channel.name} not configured")
            # Essayer avec fallback
            return send_with_fallback(message)
        
        return channel.send(message, subject)
    
    def send_telegram(
        self,
        message: str,
        chat_id: Optional[str] = None,
        bot_token: Optional[str] = None
    ) -> bool:
        """
        Envoie un message via Telegram (méthode legacy pour compatibilité).
        
        Args:
            message: Message à envoyer
            chat_id: ID du chat (défaut: TELEGRAM_OWNER_ID env)
            bot_token: Token du bot (défaut: TELEGRAM_BOT_TOKEN env)
            
        Returns:
            True si envoyé avec succès
        """
        # Utilise le nouveau système de canaux
        channel = TelegramChannel()
        if chat_id:
            channel.chat_id = chat_id
        if bot_token:
            channel.bot_token = bot_token
        return channel.send(message)
    
    def send_sms(
        self,
        message: str,
        phone: Optional[str] = None
    ) -> bool:
        """
        Envoie un SMS via Twilio.
        
        Args:
            message: Message à envoyer
            phone: Numéro destination (override OWNER_PHONE_NUMBER)
            
        Returns:
            True si envoyé avec succès
        """
        channel = SMSChannel()
        if phone:
            channel.to_number = phone
        return channel.send(message)
    
    def send_whatsapp(
        self,
        message: str,
        phone: Optional[str] = None
    ) -> bool:
        """
        Envoie un message WhatsApp via Twilio.
        
        Args:
            message: Message à envoyer
            phone: Numéro destination (override OWNER_PHONE_NUMBER)
            
        Returns:
            True si envoyé avec succès
        """
        channel = WhatsAppChannel()
        if phone:
            channel.to_number = phone
        return channel.send(message)
    
    def send_email(
        self,
        message: str,
        email: Optional[str] = None,
        subject: Optional[str] = None
    ) -> bool:
        """
        Envoie un email.
        
        Args:
            message: Message à envoyer
            email: Adresse email destination (override OWNER_EMAIL)
            subject: Sujet de l'email
            
        Returns:
            True si envoyé avec succès
        """
        channel = EmailChannel()
        if email:
            channel.email_to = email
        return channel.send(message, subject)


# ============================================
# Cron Jobs
# ============================================

def setup_scheduler():
    """
    Configure le scheduler pour les rapports automatiques.
    
    Utilise APScheduler pour envoyer le rapport à 18h chaque jour.
    Le canal est déterminé par la variable REPORT_CHANNEL.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("APScheduler not installed - automatic reports disabled")
        return None
    
    scheduler = BackgroundScheduler()
    generator = ReportGenerator()
    
    # Rapport quotidien à 18h
    @scheduler.scheduled_job(CronTrigger(hour=18, minute=0))
    def send_daily_report():
        channel_type = os.getenv("REPORT_CHANNEL", "telegram")
        logger.info(f"Sending daily report via {channel_type}...")
        report = generator.generate_daily_report()
        generator.send_report(report)
    
    # Rapport hebdomadaire le dimanche à 20h
    @scheduler.scheduled_job(CronTrigger(day_of_week='sun', hour=20, minute=0))
    def send_weekly_report():
        channel_type = os.getenv("REPORT_CHANNEL", "telegram")
        logger.info(f"Sending weekly report via {channel_type}...")
        report = generator.generate_weekly_report()
        generator.send_report(report)

    # Suspension past_due : 03:00 UTC quotidien (SUSPENSION_PAST_DUE_DAYS=7 par défaut)
    @scheduler.scheduled_job(CronTrigger(hour=3, minute=0))
    def suspension_past_due_job():
        try:
            from backend.billing_pg import run_suspension_past_due_job
            days = int(os.environ.get("SUSPENSION_PAST_DUE_DAYS", "7"))
            n = run_suspension_past_due_job(days_after_period_end=days)
            if n:
                logger.info("suspension_past_due_job: %s tenant(s) suspended", n)
        except Exception as e:
            logger.warning("suspension_past_due_job failed: %s", e)

    @scheduler.scheduled_job(CronTrigger(hour=3, minute=15))
    def expire_questionnaire_requests_job():
        try:
            from backend.questionnaire_v2 import expire_stale_questionnaire_requests

            n = expire_stale_questionnaire_requests()
            if n:
                logger.info("expire_questionnaire_requests_job: %s request(s) expired", n)
        except Exception as e:
            logger.warning("expire_questionnaire_requests_job failed: %s", e)

    # Rappels de RDV par SMS (~24h avant) : toutes les heures, fenêtre [now+24h, now+25h)
    @scheduler.scheduled_job(CronTrigger(minute=5), id="appointment_reminders")
    def appointment_reminders_job():
        try:
            from backend.appointment_reminders import run_appointment_reminders_job

            run_appointment_reminders_job()
        except Exception as e:
            logger.warning("appointment_reminders_job failed: %s", e)

    # Pré-chauffage créneaux page publique (Google Calendar) — défaut toutes les 2 min
    try:
        from apscheduler.triggers.interval import IntervalTrigger
        from backend.public_slots_prewarm import run_public_slots_prewarm_job

        prewarm_minutes = max(1, min(int(os.getenv("PUBLIC_SLOTS_PREWARM_INTERVAL_MINUTES", "2")), 30))
        if os.getenv("PUBLIC_SLOTS_PREWARM_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on"):

            @scheduler.scheduled_job(IntervalTrigger(minutes=prewarm_minutes), id="public_slots_prewarm")
            def public_slots_prewarm_job():
                run_public_slots_prewarm_job()

            logger.info("Public slots prewarm scheduled every %s min", prewarm_minutes)
    except Exception as e:
        logger.warning("public_slots_prewarm scheduler setup failed: %s", e)

    scheduler.start()
    channel_type = os.getenv("REPORT_CHANNEL", "telegram")
    logger.info(f"Report scheduler started (daily at 18h, weekly on Sunday 20h) via {channel_type}")
    
    return scheduler


def setup_reminders_scheduler():
    """Scheduler minimal dédié aux rappels SMS de RDV.

    Utilisé quand le scheduler global est désactivé (DISABLE_SCHEDULER=true) afin
    de faire tourner UNIQUEMENT les rappels, sans réactiver les autres jobs
    (rapports, prewarm, auto-suspension facturation).
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("APScheduler not installed - appointment reminders disabled")
        return None

    from backend.appointment_reminders import reminders_enabled

    if not reminders_enabled():
        logger.info("Appointment reminders disabled (APPOINTMENT_REMINDERS_ENABLED)")
        return None

    scheduler = BackgroundScheduler()

    @scheduler.scheduled_job(CronTrigger(minute=5), id="appointment_reminders")
    def _appointment_reminders_job():
        try:
            from backend.appointment_reminders import run_appointment_reminders_job

            run_appointment_reminders_job()
        except Exception as e:
            logger.warning("appointment_reminders_job failed: %s", e)

    scheduler.start()
    logger.info("Appointment reminders scheduler started (standalone, hourly at :05)")
    return scheduler


# ============================================
# Singleton
# ============================================

_generator_instance: Optional[ReportGenerator] = None


def get_report_generator() -> ReportGenerator:
    """Récupère l'instance singleton du générateur."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = ReportGenerator()
    return _generator_instance


# ============================================
# CLI pour tests
# ============================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate and send UWI reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backend.reports --daily                    # Affiche le rapport
  python -m backend.reports --daily --send             # Envoie via REPORT_CHANNEL
  python -m backend.reports --daily --channel sms      # Envoie par SMS
  python -m backend.reports --daily --channel whatsapp # Envoie par WhatsApp
  python -m backend.reports --daily --channel email    # Envoie par email
  python -m backend.reports --weekly --send            # Rapport hebdo
  python -m backend.reports --test-channels            # Teste tous les canaux
        """
    )
    parser.add_argument("--daily", action="store_true", help="Generate daily report")
    parser.add_argument("--weekly", action="store_true", help="Generate weekly report")
    parser.add_argument("--send", action="store_true", help="Send the report")
    parser.add_argument("--channel", type=str, choices=["telegram", "sms", "whatsapp", "email"],
                       help="Override REPORT_CHANNEL for this send")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--test-channels", action="store_true", 
                       help="Test all configured channels")
    parser.add_argument("--list-channels", action="store_true",
                       help="List all channels and their configuration status")
    
    args = parser.parse_args()
    
    generator = ReportGenerator()
    
    # Test des canaux
    if args.test_channels:
        print("\n🧪 Test de tous les canaux de notification\n")
        print("=" * 50)
        
        test_message = f"🧪 Test UWI - {datetime.now().strftime('%H:%M:%S')}\nCeci est un message de test."
        channels_to_test = ["telegram", "sms", "whatsapp", "email"]
        
        results = {}
        for channel_type in channels_to_test:
            channel = get_notification_channel(channel_type)
            print(f"\n📡 {channel_type.upper()}:")
            print(f"   Configuré: {'✅ Oui' if channel.is_configured() else '❌ Non'}")
            
            if channel.is_configured():
                print(f"   Envoi en cours...")
                success = channel.send(test_message)
                results[channel_type] = success
                print(f"   Résultat: {'✅ Envoyé' if success else '❌ Échec'}")
            else:
                results[channel_type] = None
                print(f"   ⏭️  Skippé (non configuré)")
        
        print("\n" + "=" * 50)
        print("📊 Résumé:")
        for ch, result in results.items():
            if result is True:
                print(f"   ✅ {ch}: OK")
            elif result is False:
                print(f"   ❌ {ch}: ÉCHEC")
            else:
                print(f"   ⚪ {ch}: Non configuré")
        print()
        exit(0)
    
    # Liste des canaux
    if args.list_channels:
        print("\n📡 Canaux de notification disponibles\n")
        print("=" * 50)
        
        current_channel = os.getenv("REPORT_CHANNEL", "telegram")
        
        channels_info = [
            ("telegram", "Telegram Bot", ["TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_ID"]),
            ("sms", "SMS (Twilio)", ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER", "OWNER_PHONE_NUMBER"]),
            ("whatsapp", "WhatsApp (Twilio)", ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "OWNER_PHONE_NUMBER"]),
            ("email", "Email (SMTP)", ["SMTP_EMAIL", "SMTP_PASSWORD", "OWNER_EMAIL"]),
        ]
        
        for ch_type, ch_name, required_vars in channels_info:
            channel = get_notification_channel(ch_type)
            is_current = "← ACTIF" if ch_type == current_channel else ""
            status = "✅" if channel.is_configured() else "❌"
            
            print(f"\n{status} {ch_name} ({ch_type}) {is_current}")
            
            for var in required_vars:
                value = os.getenv(var)
                if value:
                    # Masquer les valeurs sensibles
                    if "TOKEN" in var or "PASSWORD" in var or "AUTH" in var:
                        display = value[:4] + "****"
                    else:
                        display = value[:15] + "..." if len(value) > 15 else value
                    print(f"     {var}: {display}")
                else:
                    print(f"     {var}: ⚠️  Non défini")
        
        print(f"\n💡 Canal actif: REPORT_CHANNEL={current_channel}")
        print()
        exit(0)
    
    # Génération du rapport
    target_date = None
    if args.date:
        target_date = date.fromisoformat(args.date)
    
    if args.weekly:
        report = generator.generate_weekly_report()
    else:
        report = generator.generate_daily_report(target_date)
    
    print(report)
    
    # Envoi
    if args.send:
        channel_type = args.channel or os.getenv("REPORT_CHANNEL", "telegram")
        print(f"\n📤 Envoi via {channel_type}...")
        
        channel = get_notification_channel(channel_type)
        
        if not channel.is_configured():
            print(f"❌ Canal {channel_type} non configuré!")
            print(f"💡 Utilisez --list-channels pour voir les variables requises")
            exit(1)
        
        success = channel.send(report)
        if success:
            print("✅ Envoyé!")
        else:
            print("❌ Échec de l'envoi")
