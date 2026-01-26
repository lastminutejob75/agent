"""
Rapport quotidien automatique - inspiré du pattern Clawdbot.

Ce module génère des rapports d'activité et les envoie au gérant.
Peut être déclenché par cron job ou manuellement.
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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
    # Envoi du rapport
    # ============================================
    
    def send_telegram(
        self,
        message: str,
        chat_id: Optional[str] = None,
        bot_token: Optional[str] = None
    ) -> bool:
        """
        Envoie un message via Telegram.
        
        Args:
            message: Message à envoyer
            chat_id: ID du chat (défaut: TELEGRAM_OWNER_ID env)
            bot_token: Token du bot (défaut: TELEGRAM_BOT_TOKEN env)
            
        Returns:
            True si envoyé avec succès
        """
        import requests
        
        chat_id = chat_id or os.getenv("TELEGRAM_OWNER_ID")
        bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        
        if not chat_id or not bot_token:
            logger.warning("Telegram credentials not configured")
            return False
        
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("Daily report sent to Telegram")
                return True
            else:
                logger.error(f"Telegram error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def send_sms(
        self,
        message: str,
        phone: Optional[str] = None
    ) -> bool:
        """
        Envoie un SMS via Twilio (si configuré).
        
        Args:
            message: Message à envoyer
            phone: Numéro destination
            
        Returns:
            True si envoyé avec succès
        """
        # Placeholder - à implémenter avec Twilio
        logger.warning("SMS sending not implemented yet")
        return False


# ============================================
# Cron Jobs
# ============================================

def setup_scheduler():
    """
    Configure le scheduler pour les rapports automatiques.
    
    Utilise APScheduler pour envoyer le rapport à 18h chaque jour.
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
        logger.info("Sending daily report...")
        report = generator.generate_daily_report()
        generator.send_telegram(report)
    
    # Rapport hebdomadaire le dimanche à 20h
    @scheduler.scheduled_job(CronTrigger(day_of_week='sun', hour=20, minute=0))
    def send_weekly_report():
        logger.info("Sending weekly report...")
        report = generator.generate_weekly_report()
        generator.send_telegram(report)
    
    scheduler.start()
    logger.info("Report scheduler started (daily at 18h, weekly on Sunday 20h)")
    
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
    
    parser = argparse.ArgumentParser(description="Generate UWI reports")
    parser.add_argument("--daily", action="store_true", help="Generate daily report")
    parser.add_argument("--weekly", action="store_true", help="Generate weekly report")
    parser.add_argument("--send", action="store_true", help="Send via Telegram")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    generator = ReportGenerator()
    
    target_date = None
    if args.date:
        target_date = date.fromisoformat(args.date)
    
    if args.weekly:
        report = generator.generate_weekly_report()
    else:
        report = generator.generate_daily_report(target_date)
    
    print(report)
    
    if args.send:
        success = generator.send_telegram(report)
        print(f"\n{'✅ Sent!' if success else '❌ Failed to send'}")
