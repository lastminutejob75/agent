"""
Seed script: injecte des données de test réalistes dans la base SQLite locale (agent.db).
Usage: python3 seed_test_data.py
"""
import sqlite3
import uuid
import json
from datetime import datetime, timedelta

DB_PATH = "agent.db"
TENANT_ID = 1

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            is_booked INTEGER DEFAULT 0,
            UNIQUE(tenant_id, date, time)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_id INTEGER NOT NULL,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            name TEXT NOT NULL,
            contact TEXT NOT NULL,
            contact_type TEXT NOT NULL,
            motif TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(slot_id) REFERENCES slots(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ivr_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            call_id TEXT,
            event TEXT NOT NULL,
            context TEXT,
            reason TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS call_followups (
            tenant_id INTEGER NOT NULL,
            call_id TEXT NOT NULL,
            followup_state TEXT NOT NULL DEFAULT 'new',
            notes TEXT,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (tenant_id, call_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cabinet_clients (
            tenant_id INTEGER NOT NULL,
            phone TEXT NOT NULL,
            raw_name TEXT,
            validated_name TEXT,
            display_name TEXT,
            validation_status TEXT NOT NULL DEFAULT 'pending',
            email TEXT,
            source_call_id TEXT,
            last_call_id TEXT,
            last_booking_start TEXT,
            last_booking_end TEXT,
            last_booking_motif TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (tenant_id, phone)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS human_handoffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            call_id TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'vocal',
            reason TEXT NOT NULL,
            target TEXT NOT NULL,
            mode TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'normal',
            status TEXT NOT NULL DEFAULT 'callback_created',
            patient_phone TEXT,
            raw_name TEXT,
            validated_name TEXT,
            display_name TEXT,
            summary TEXT,
            transcript_excerpt TEXT,
            booking_start_iso TEXT,
            booking_end_iso TEXT,
            booking_motif TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            processed_at TEXT,
            UNIQUE (tenant_id, call_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            tenant_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)
    conn.execute("INSERT OR IGNORE INTO tenants (tenant_id, name) VALUES (1, 'Cabinet Dr. Martin')")
    conn.commit()

PATIENTS = [
    # (phone, raw_name, validated_name, display_name, validation_status, email)
    ("+33612345678", "Marie Dupont",   "Marie Dupont",   "Marie Dupont",   "validated", "marie.dupont@email.com"),
    ("+33698765432", "Jean Moreau",    "Jean Moreau",    "Jean Moreau",    "validated", "jean.moreau@gmail.com"),
    ("+33611223344", "Sophie Laurent", "Sophie Laurent", "Sophie Laurent", "validated", None),
    ("+33644556677", "Pierre Martin",  None,             "Pierre Martin",  "pending",   None),
    ("+33677889900", "Camille Roux",   None,             "Camille Roux",   "pending",   None),
    ("+33655443322", "Luc Bernard",    None,             "Luc Bernard",    "pending",   None),
    ("+33633221100", "Emma Petit",     "Emma Petit",     "Emma Petit",     "validated", "emma.petit@outlook.fr"),
    ("+33666778899", "Thomas Durand",  None,             "Thomas Durand",  "pending",   None),
    ("+33699887766", "Julie Lefevre",  "Julie Lefevre",  "Julie Lefevre",  "validated", None),
    ("+33622334455", "Nicolas Garnier", None,            "Nicolas Garnier","pending",   None),
]

MOTIFS = [
    "Consultation générale",
    "Renouvellement ordonnance",
    "Suivi post-opératoire",
    "Vaccination",
    "Douleurs dorsales",
    "Contrôle annuel",
    "Bilan sanguin",
    "Certificat médical",
    "Suivi grossesse",
    "Consultation dermatologique",
]

CALL_EVENTS_SCENARIOS = [
    ["call_started", "booking_confirmed"],
    ["call_started", "booking_confirmed"],
    ["call_started", "transferred_human"],
    ["call_started", "faq_answered", "call_ended"],
    ["call_started", "booking_confirmed"],
    ["call_started", "user_abandon"],
    ["call_started", "transferred_human"],
    ["call_started", "faq_answered", "call_ended"],
    ["call_started", "booking_confirmed"],
    ["call_started", "anti_loop_trigger"],
    ["call_started", "faq_answered", "call_ended"],
    ["call_started", "booking_confirmed"],
    ["call_started", "transferred_human"],
    ["call_started", "user_abandon"],
    ["call_started", "booking_confirmed"],
]

def seed_patients(conn):
    now = datetime.utcnow()
    count = 0
    for i, (phone, raw, val, disp, status, email) in enumerate(PATIENTS):
        created = (now - timedelta(days=30 - i * 3)).isoformat()
        updated = (now - timedelta(days=i)).isoformat()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO cabinet_clients
                   (tenant_id, phone, raw_name, validated_name, display_name,
                    validation_status, email, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (TENANT_ID, phone, raw, val, disp, status, email, created, updated),
            )
            count += 1
        except Exception as e:
            print(f"  [!] Patient {phone}: {e}")
    conn.commit()
    print(f"  -> {count} patients insérés")

def seed_appointments(conn):
    now = datetime.utcnow()
    today = now.date()
    count = 0
    appointment_data = []

    for day_offset in range(-2, 8):
        target_date = today + timedelta(days=day_offset)
        if target_date.weekday() >= 5:
            continue

        date_str = target_date.strftime("%Y-%m-%d")

        if day_offset < 0:
            hours = ["09:00", "10:30", "14:00"]
        elif day_offset == 0:
            hours = ["08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "14:00", "14:30", "15:00", "16:00"]
        elif day_offset <= 2:
            hours = ["09:00", "09:30", "10:00", "11:00", "14:00", "15:00", "16:30"]
        else:
            hours = ["09:00", "10:30", "14:00", "16:00"]

        for time_str in hours:
            patient_idx = (day_offset + count) % len(PATIENTS)
            patient = PATIENTS[patient_idx]
            motif = MOTIFS[(day_offset + count) % len(MOTIFS)]

            appointment_data.append((date_str, time_str, patient, motif))
            count += 1

    for date_str, time_str, patient, motif in appointment_data:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO slots (tenant_id, date, time, is_booked) VALUES (?, ?, ?, 1)",
                (TENANT_ID, date_str, time_str),
            )
            slot_row = conn.execute(
                "SELECT id FROM slots WHERE tenant_id = ? AND date = ? AND time = ?",
                (TENANT_ID, date_str, time_str),
            ).fetchone()
            if not slot_row:
                continue
            slot_id = slot_row["id"]

            existing = conn.execute(
                "SELECT id FROM appointments WHERE slot_id = ? AND tenant_id = ?",
                (slot_id, TENANT_ID),
            ).fetchone()
            if existing:
                continue

            created_at = (datetime.utcnow() - timedelta(days=2)).isoformat()
            conn.execute(
                """INSERT INTO appointments (slot_id, tenant_id, name, contact, contact_type, motif, created_at)
                   VALUES (?, ?, ?, ?, 'phone', ?, ?)""",
                (slot_id, TENANT_ID, patient[1] or patient[3], patient[0], motif, created_at),
            )
        except Exception as e:
            print(f"  [!] Appointment {date_str} {time_str}: {e}")

    conn.commit()
    print(f"  -> {count} créneaux/RDV insérés sur {len(set(d[0] for d in appointment_data))} jours")

def seed_calls(conn):
    now = datetime.utcnow()
    count = 0
    for i, scenario in enumerate(CALL_EVENTS_SCENARIOS):
        call_id = f"call-test-{uuid.uuid4().hex[:12]}"
        patient_idx = i % len(PATIENTS)
        patient = PATIENTS[patient_idx]
        call_start = now - timedelta(hours=(len(CALL_EVENTS_SCENARIOS) - i) * 3, minutes=i * 7)

        for j, event_name in enumerate(scenario):
            event_time = call_start + timedelta(seconds=j * 45 + j * 15)
            context_data = {
                "customer_number": patient[0],
                "patient_name": patient[1] or patient[3],
            }
            if event_name == "booking_confirmed":
                booking_date = (now + timedelta(days=2 + i)).strftime("%Y-%m-%d")
                context_data["booking_start"] = f"{booking_date}T10:00:00"
                context_data["booking_end"] = f"{booking_date}T10:30:00"
                context_data["booking_motif"] = MOTIFS[i % len(MOTIFS)]

            conn.execute(
                """INSERT INTO ivr_events (client_id, call_id, event, context, reason, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    TENANT_ID,
                    call_id,
                    event_name,
                    json.dumps(context_data),
                    f"Appel de {patient[1] or patient[3]}" if event_name in ("transferred_human", "user_abandon") else None,
                    event_time.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )

        last_event = scenario[-1]
        if last_event == "booking_confirmed":
            conn.execute(
                "INSERT OR IGNORE INTO call_followups (tenant_id, call_id, followup_state, notes) VALUES (?, ?, 'done', 'RDV confirmé')",
                (TENANT_ID, call_id),
            )
        elif last_event == "transferred_human":
            conn.execute(
                "INSERT OR IGNORE INTO call_followups (tenant_id, call_id, followup_state, notes) VALUES (?, ?, 'pending', 'Transfert - à rappeler')",
                (TENANT_ID, call_id),
            )
        else:
            conn.execute(
                "INSERT OR IGNORE INTO call_followups (tenant_id, call_id, followup_state, notes) VALUES (?, ?, 'new', NULL)",
                (TENANT_ID, call_id),
            )

        conn.execute(
            """UPDATE cabinet_clients SET last_call_id = ?, updated_at = ?
               WHERE tenant_id = ? AND phone = ?""",
            (call_id, call_start.strftime("%Y-%m-%d %H:%M:%S"), TENANT_ID, patient[0]),
        )

        count += 1
    conn.commit()
    print(f"  -> {count} appels insérés (avec événements IVR et followups)")

def seed_handoffs(conn):
    now = datetime.utcnow()
    handoff_data = [
        {
            "call_id": f"handoff-{uuid.uuid4().hex[:8]}",
            "channel": "vocal",
            "reason": "Le patient souhaite renouveler son ordonnance de Doliprane et Amoxicilline",
            "target": "callback",
            "mode": "callback",
            "priority": "normal",
            "status": "callback_created",
            "patient": PATIENTS[0],
            "summary": "Renouvellement ordonnance - Marie Dupont demande le renouvellement de son traitement habituel.",
            "transcript_excerpt": "Patient: Bonjour, j'aurais besoin de renouveler mon ordonnance s'il vous plaît...",
            "hours_ago": 2,
        },
        {
            "call_id": f"handoff-{uuid.uuid4().hex[:8]}",
            "channel": "vocal",
            "reason": "Urgence : le patient signale des douleurs thoraciques depuis ce matin",
            "target": "callback",
            "mode": "callback",
            "priority": "urgent",
            "status": "callback_created",
            "patient": PATIENTS[3],
            "summary": "Douleurs thoraciques - Pierre Martin signale des douleurs depuis le matin, demande un rappel urgent.",
            "transcript_excerpt": "Patient: J'ai très mal à la poitrine depuis ce matin, c'est de pire en pire...",
            "hours_ago": 1,
        },
        {
            "call_id": f"handoff-{uuid.uuid4().hex[:8]}",
            "channel": "vocal",
            "reason": "Question sur les résultats d'analyse sanguine",
            "target": "callback",
            "mode": "callback",
            "priority": "normal",
            "status": "callback_created",
            "patient": PATIENTS[1],
            "summary": "Résultats analyses - Jean Moreau souhaite discuter de ses résultats de prise de sang.",
            "transcript_excerpt": "Patient: J'ai reçu mes résultats de prise de sang et j'aimerais en parler avec le docteur...",
            "hours_ago": 5,
        },
        {
            "call_id": f"handoff-{uuid.uuid4().hex[:8]}",
            "channel": "vocal",
            "reason": "Demande de certificat médical pour le sport",
            "target": "callback",
            "mode": "callback",
            "priority": "normal",
            "status": "processed",
            "patient": PATIENTS[6],
            "summary": "Certificat médical sport - Emma Petit a besoin d'un certificat pour inscription en salle de sport.",
            "transcript_excerpt": "Patient: J'aurais besoin d'un certificat médical pour m'inscrire à la salle de sport...",
            "hours_ago": 24,
        },
        {
            "call_id": f"handoff-{uuid.uuid4().hex[:8]}",
            "channel": "vocal",
            "reason": "Le patient souhaite modifier son rendez-vous de demain",
            "target": "callback",
            "mode": "callback",
            "priority": "normal",
            "status": "callback_created",
            "patient": PATIENTS[4],
            "summary": "Modification RDV - Camille Roux souhaite déplacer son RDV de demain à une date ultérieure.",
            "transcript_excerpt": "Patient: Est-ce qu'il serait possible de décaler mon rendez-vous de demain ?...",
            "hours_ago": 3,
        },
        {
            "call_id": f"handoff-{uuid.uuid4().hex[:8]}",
            "channel": "vocal",
            "reason": "Demande d'arrêt de travail suite à une grippe",
            "target": "callback",
            "mode": "callback",
            "priority": "normal",
            "status": "cancelled",
            "patient": PATIENTS[7],
            "summary": "Arrêt de travail - Thomas Durand a la grippe et demande un arrêt. A finalement pu venir au cabinet.",
            "transcript_excerpt": "Patient: Je suis très malade, je pense avoir la grippe, j'aurais besoin d'un arrêt...",
            "hours_ago": 48,
        },
    ]

    count = 0
    for h in handoff_data:
        patient = h["patient"]
        created = (now - timedelta(hours=h["hours_ago"])).strftime("%Y-%m-%d %H:%M:%S")
        processed_at = created if h["status"] in ("processed", "cancelled") else None
        try:
            conn.execute(
                """INSERT OR IGNORE INTO human_handoffs
                   (tenant_id, call_id, channel, reason, target, mode, priority, status,
                    patient_phone, raw_name, validated_name, display_name,
                    summary, transcript_excerpt, notes, created_at, updated_at, processed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    TENANT_ID, h["call_id"], h["channel"], h["reason"],
                    h["target"], h["mode"], h["priority"], h["status"],
                    patient[0], patient[1], patient[2], patient[3],
                    h["summary"], h["transcript_excerpt"], None,
                    created, created, processed_at,
                ),
            )
            count += 1
        except Exception as e:
            print(f"  [!] Handoff {h['call_id']}: {e}")
    conn.commit()
    print(f"  -> {count} demandes/handoffs insérées")


def main():
    print(f"=== Seed données de test dans {DB_PATH} (tenant_id={TENANT_ID}) ===\n")
    conn = get_conn()
    try:
        ensure_tables(conn)

        print("[1/4] Patients (cabinet_clients)...")
        seed_patients(conn)

        print("[2/4] Rendez-vous (slots + appointments)...")
        seed_appointments(conn)

        print("[3/4] Appels (ivr_events + call_followups)...")
        seed_calls(conn)

        print("[4/4] Demandes / Handoffs (human_handoffs)...")
        seed_handoffs(conn)

        print("\n=== Seed terminé avec succès ! ===")
        print("\nRésumé :")
        for table in ("cabinet_clients", "slots", "appointments", "ivr_events", "call_followups", "human_handoffs"):
            row = conn.execute(f"SELECT COUNT(*) as c FROM {table} WHERE {'tenant_id' if table != 'ivr_events' else 'client_id'} = ?", (TENANT_ID,)).fetchone()
            print(f"  {table}: {row['c']} lignes")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
