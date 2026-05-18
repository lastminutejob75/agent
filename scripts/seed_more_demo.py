"""
Seed enrichi : patients, demandes (handoffs), appels récents.
À lancer depuis la racine du projet : python3 scripts/seed_more_demo.py

Idempotent : ne ré-insère pas les patients/handoffs/appels déjà présents
(détection par phone+display_name pour patients, par call_id pour les autres).
"""
import json
import sqlite3
import uuid
from datetime import datetime, timedelta

DB = "agent.db"
TENANT_ID = 1
NOW = datetime.now()


def fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


# ────────────────────────────── PATIENTS ──────────────────────────────
NEW_PATIENTS = [
    # phone, display_name, validated_name, status, email, last_booking_start, last_booking_motif
    ("+33611223355", "Élise Moreau",     "Élise Moreau",     "validated",   "elise.moreau@gmail.com",   None,                       None),
    ("+33622446688", "Hugo Bernard",     "Hugo Bernard",     "validated",   "hugo.b@orange.fr",         iso(NOW + timedelta(days=2, hours=10)), "Suivi tension"),
    ("+33644778800", "Léa Dubois",       "Léa Dubois",       "validated",   None,                       iso(NOW + timedelta(days=1, hours=14)), "Renouvellement ordonnance"),
    ("+33655998877", "Antoine Girard",   "Antoine Girard",   "unvalidated", None,                       None,                       None),
    ("+33666332244", "Clara Robert",     "Clara Robert",     "validated",   "c.robert@yahoo.fr",        iso(NOW + timedelta(days=4, hours=9)),  "Consultation pédiatrique"),
    ("+33677556644", "Maxime Lefèvre",   "Maxime Lefèvre",   "validated",   None,                       None,                       None),
    ("+33688990011", "Fatima Benali",    "Fatima Benali",    "validated",   "fatima.benali@free.fr",    iso(NOW + timedelta(days=3, hours=11, minutes=30)), "Bilan sanguin"),
    ("+33699112233", "Olivier Chevalier","Olivier Chevalier","unvalidated", None,                       None,                       None),
    ("+33611445566", "Aïcha Diallo",     "Aïcha Diallo",     "validated",   "aicha.d@gmail.com",        iso(NOW + timedelta(days=7, hours=15)), "Vaccin grippe"),
    ("+33622778899", "Romain Faure",     "Romain Faure",     "validated",   None,                       iso(NOW - timedelta(days=2, hours=4)), "Consultation urgente"),
]

# ────────────────────────────── DEMANDES (handoffs) ──────────────────────────────
NEW_HANDOFFS = [
    # patient_phone, display_name, status, reason, summary, created_offset (jours en arrière)
    ("+33611223355", "Élise Moreau",      "callback_created", "Demande de rappel pour résultats d'IRM",
     "Résultats IRM - Élise Moreau souhaite être rappelée pour discuter de ses résultats d'IRM lombaire.", 0.1),
    ("+33644778800", "Léa Dubois",        "callback_created", "Renouvellement urgent d'ordonnance Levothyrox",
     "Renouvellement Levothyrox - Léa Dubois n'a plus de comprimés depuis ce matin.", 0.3),
    ("+33688990011", "Fatima Benali",     "callback_created", "Question sur préparation au bilan sanguin",
     "Bilan sanguin - Fatima Benali demande si elle doit être à jeun pour son bilan de jeudi.", 1.2),
    ("+33622446688", "Hugo Bernard",      "callback_created", "Demande arrêt de travail pour COVID",
     "Arrêt COVID - Hugo Bernard est positif depuis 2 jours, demande un arrêt rétroactif.", 0.5),
    ("+33666332244", "Clara Robert",      "processed",        "Question sur posologie sirop pour bébé",
     "Posologie pédiatrique - Clara Robert demande si elle peut donner du Doliprane à son bébé de 6 mois.", 2.5),
    ("+33611445566", "Aïcha Diallo",      "processed",        "Demande de certificat médical voyage",
     "Certificat voyage - Aïcha Diallo a besoin d'un certificat pour son visa.", 3.0),
    ("+33622778899", "Romain Faure",      "callback_created", "Douleurs abdominales aiguës",
     "Urgence - Romain Faure signale de fortes douleurs abdominales depuis 6h, demande un avis rapide.", 0.05),
    ("+33655998877", "Antoine Girard",    "cancelled",        "Question administrative - dossier mutuelle",
     "Mutuelle - Antoine Girard demandait de l'aide pour remplir un formulaire. A trouvé l'info en ligne.", 4.0),
]

# Mapping motif → catégorie pour cohérence avec dashboard
HANDOFF_PRIORITY = {
    "Urgence": "high",
    "douleur": "high",
    "Douleurs": "high",
    "urgent": "high",
    "Renouvellement": "normal",
    "Question": "low",
    "Demande": "normal",
    "Certificat": "low",
    "Bilan": "low",
    "Mutuelle": "low",
    "Posologie": "normal",
}


def pick_priority(reason: str) -> str:
    for k, v in HANDOFF_PRIORITY.items():
        if k.lower() in reason.lower():
            return v
    return "normal"


# ────────────────────────────── APPELS (ivr_events) ──────────────────────────────
# (offset_jours, durée_min, phone, display_name, event, motif|reason)
NEW_CALLS = [
    # Aujourd'hui
    (0.05, 3, "+33622778899", "Romain Faure",     "transferred_human", "Romain Faure souhaite parler au praticien (douleurs)"),
    (0.10, 4, "+33611223355", "Élise Moreau",     "transferred_human", "Élise Moreau demande un rappel pour résultats IRM"),
    (0.20, 2, "+33644778800", "Léa Dubois",       "transferred_human", "Léa Dubois - renouvellement urgent ordonnance"),
    (0.40, 5, "+33611223355", "Élise Moreau",     "booking_confirmed", {"motif": "Bilan annuel", "start": iso(NOW + timedelta(days=10, hours=9))}),
    (0.50, 1, "+33655998877", "Antoine Girard",   "user_abandon",      None),
    (0.60, 2, "+33622446688", "Hugo Bernard",     "faq_answered",      "Horaires d'ouverture le samedi"),
    # Hier
    (1.10, 3, "+33688990011", "Fatima Benali",    "booking_confirmed", {"motif": "Bilan sanguin", "start": iso(NOW + timedelta(days=3, hours=11, minutes=30))}),
    (1.20, 4, "+33688990011", "Fatima Benali",    "transferred_human", "Fatima Benali - question préparation bilan"),
    (1.50, 2, "+33677556644", "Maxime Lefèvre",   "faq_answered",      "Tarifs consultation"),
    (1.70, 5, "+33666332244", "Clara Robert",     "booking_confirmed", {"motif": "Consultation pédiatrique", "start": iso(NOW + timedelta(days=4, hours=9))}),
    # Avant-hier
    (2.10, 3, "+33699112233", "Olivier Chevalier","user_abandon",      None),
    (2.30, 4, "+33666332244", "Clara Robert",     "transferred_human", "Clara Robert - posologie pédiatrique"),
    (2.50, 2, "+33611445566", "Aïcha Diallo",     "faq_answered",      "Vaccins disponibles au cabinet"),
    # 3 jours
    (3.10, 5, "+33611445566", "Aïcha Diallo",     "booking_confirmed", {"motif": "Vaccin grippe", "start": iso(NOW + timedelta(days=7, hours=15))}),
    (3.20, 3, "+33611445566", "Aïcha Diallo",     "transferred_human", "Aïcha Diallo - certificat voyage"),
    (3.50, 1, "+33644778800", "Léa Dubois",       "user_abandon",      None),
    # 4 jours
    (4.10, 4, "+33655998877", "Antoine Girard",   "transferred_human", "Antoine Girard - question mutuelle"),
    (4.30, 2, "+33677556644", "Maxime Lefèvre",   "faq_answered",      "Cabinet ouvert lundi férié ?"),
    (4.50, 5, "+33622446688", "Hugo Bernard",     "booking_confirmed", {"motif": "Suivi tension", "start": iso(NOW + timedelta(days=2, hours=10))}),
    # 5+ jours
    (5.20, 3, "+33644778800", "Léa Dubois",       "booking_confirmed", {"motif": "Renouvellement ordonnance", "start": iso(NOW + timedelta(days=1, hours=14))}),
    (6.10, 4, "+33611223355", "Élise Moreau",     "faq_answered",      "Résultats analyses disponibles ?"),
    (7.30, 2, "+33699112233", "Olivier Chevalier","faq_answered",      "Liste documents pour première consult."),
]


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1) Patients
    inserted_p = 0
    for phone, name, vname, status, email, lbs, lbm in NEW_PATIENTS:
        existing = cur.execute(
            "SELECT 1 FROM cabinet_clients WHERE tenant_id=? AND phone=?",
            (TENANT_ID, phone),
        ).fetchone()
        if existing:
            continue
        cur.execute(
            """INSERT INTO cabinet_clients (tenant_id, phone, raw_name, validated_name, display_name,
               validation_status, last_booking_start, last_booking_motif, email, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (TENANT_ID, phone, name, vname, name, status, lbs, lbm, email, fmt(NOW), fmt(NOW)),
        )
        inserted_p += 1

    # 2) Handoffs
    inserted_h = 0
    for phone, name, status, reason, summary, days_ago in NEW_HANDOFFS:
        created = NOW - timedelta(days=days_ago)
        already = cur.execute(
            "SELECT 1 FROM human_handoffs WHERE tenant_id=? AND patient_phone=? AND reason=?",
            (TENANT_ID, phone, reason),
        ).fetchone()
        if already:
            continue
        priority = pick_priority(reason)
        call_id = f"call-{uuid.uuid4().hex[:10]}"
        processed_at = fmt(created + timedelta(hours=2)) if status == "processed" else None
        cur.execute(
            """INSERT INTO human_handoffs (tenant_id, call_id, channel, reason, target, mode, priority,
               status, patient_phone, raw_name, validated_name, display_name, summary,
               created_at, updated_at, processed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (TENANT_ID, call_id, "phone", reason, "praticien", "callback", priority,
             status, phone, name, name, name, summary,
             fmt(created), fmt(created), processed_at),
        )
        inserted_h += 1

    # 3) Appels
    inserted_c = 0
    for days_ago, dur_min, phone, name, event, payload in NEW_CALLS:
        created = NOW - timedelta(days=days_ago)
        call_id = f"demo-{phone[-4:]}-{uuid.uuid4().hex[:8]}"
        already = cur.execute("SELECT 1 FROM ivr_events WHERE call_id=?", (call_id,)).fetchone()
        if already:
            continue

        ctx_start = {"customer_number": phone, "patient_name": name}
        cur.execute(
            "INSERT INTO ivr_events (client_id, call_id, event, context, created_at) VALUES (?,?,?,?,?)",
            (TENANT_ID, call_id, "call_started", json.dumps(ctx_start, ensure_ascii=False), fmt(created)),
        )

        if event == "booking_confirmed" and isinstance(payload, dict):
            start = payload["start"]
            end = (datetime.strptime(start, "%Y-%m-%dT%H:%M:%S") + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")
            ctx = {"customer_number": phone, "patient_name": name, "booking_start": start,
                   "booking_end": end, "booking_motif": payload["motif"]}
            cur.execute(
                "INSERT INTO ivr_events (client_id, call_id, event, context, created_at) VALUES (?,?,?,?,?)",
                (TENANT_ID, call_id, "booking_confirmed", json.dumps(ctx, ensure_ascii=False),
                 fmt(created + timedelta(minutes=dur_min))),
            )
        elif event == "transferred_human":
            ctx = {"customer_number": phone, "patient_name": name, "reason": payload}
            cur.execute(
                "INSERT INTO ivr_events (client_id, call_id, event, context, reason, created_at) VALUES (?,?,?,?,?,?)",
                (TENANT_ID, call_id, "transferred_human", json.dumps(ctx, ensure_ascii=False), payload,
                 fmt(created + timedelta(minutes=dur_min))),
            )
        elif event == "faq_answered":
            ctx = {"customer_number": phone, "patient_name": name, "question": payload}
            cur.execute(
                "INSERT INTO ivr_events (client_id, call_id, event, context, created_at) VALUES (?,?,?,?,?)",
                (TENANT_ID, call_id, "faq_answered", json.dumps(ctx, ensure_ascii=False),
                 fmt(created + timedelta(minutes=dur_min))),
            )
        elif event == "user_abandon":
            ctx = {"customer_number": phone, "patient_name": name}
            cur.execute(
                "INSERT INTO ivr_events (client_id, call_id, event, context, created_at) VALUES (?,?,?,?,?)",
                (TENANT_ID, call_id, "user_abandon", json.dumps(ctx, ensure_ascii=False),
                 fmt(created + timedelta(minutes=dur_min))),
            )

        cur.execute(
            "INSERT INTO ivr_events (client_id, call_id, event, context, created_at) VALUES (?,?,?,?,?)",
            (TENANT_ID, call_id, "call_ended", json.dumps(ctx_start, ensure_ascii=False),
             fmt(created + timedelta(minutes=dur_min, seconds=10))),
        )
        inserted_c += 1

    conn.commit()
    print(f"✅ Patients ajoutés : {inserted_p}")
    print(f"✅ Demandes ajoutées : {inserted_h}")
    print(f"✅ Appels ajoutés    : {inserted_c}")

    # Stats finales
    print("\n--- État final ---")
    print(f"  cabinet_clients : {cur.execute('SELECT COUNT(*) FROM cabinet_clients WHERE tenant_id=?',(TENANT_ID,)).fetchone()[0]}")
    print(f"  human_handoffs  : {cur.execute('SELECT COUNT(*) FROM human_handoffs WHERE tenant_id=?',(TENANT_ID,)).fetchone()[0]}")
    print(f"  ivr_events      : {cur.execute('SELECT COUNT(*) FROM ivr_events').fetchone()[0]}")
    pending = cur.execute("SELECT COUNT(*) FROM human_handoffs WHERE tenant_id=? AND status='callback_created'", (TENANT_ID,)).fetchone()[0]
    print(f"  demandes en attente : {pending}")
    conn.close()


if __name__ == "__main__":
    main()
