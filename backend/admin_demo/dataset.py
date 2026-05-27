"""Dataset demo pour l'admin (deterministe).

Le module genere une fois pour toutes :
    - 8 cabinets (tenants) varies en plan/sante/billing
    - 12 leads pre-onboarding (mix new/contacted/converted/lost + grands comptes)
    - 60-80 appels Vapi sur 14 jours (RDV, transferts, abandons, erreurs)
    - 1 transcript pour chaque appel "narratif"
    - Billing Stripe simule par tenant
    - Quotas et conso Vapi

Le tout est expose via des helpers (`get_tenants`, `get_calls_for_tenant`...)
utilises par `router.py`. Les donnees sont generees au premier import et
resta en memoire pour le restant de la session uvicorn.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Seeding deterministe
# ---------------------------------------------------------------------------

_RNG = random.Random(42)
_NOW = datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ago(**kwargs) -> datetime:
    return _NOW - timedelta(**kwargs)


# ---------------------------------------------------------------------------
# Plans Stripe simules
# ---------------------------------------------------------------------------

PLANS: Dict[str, Dict[str, Any]] = {
    "starter": {
        "key": "starter",
        "name": "Starter",
        "price_eur": 19,
        "included_minutes_month": 100,
        "extra_minute_eur": 0.30,
        "stripe_price_id": "price_demo_starter",
    },
    "growth": {
        "key": "growth",
        "name": "Growth",
        "price_eur": 49,
        "included_minutes_month": 400,
        "extra_minute_eur": 0.20,
        "stripe_price_id": "price_demo_growth",
    },
    "pro": {
        "key": "pro",
        "name": "Pro",
        "price_eur": 99,
        "included_minutes_month": 1200,
        "extra_minute_eur": 0.15,
        "stripe_price_id": "price_demo_pro",
    },
}


# ---------------------------------------------------------------------------
# Tenants demo
# ---------------------------------------------------------------------------


@dataclass
class DemoTenant:
    tenant_id: int
    name: str
    contact_email: str
    timezone: str
    status: str  # active | suspended
    plan_key: str
    billing_status: str  # active | trialing | past_due | canceled
    stripe_customer_id: Optional[str]
    stripe_subscription_id: Optional[str]
    created_at: datetime
    primary_did: str
    transfer_number: Optional[str]
    transfer_practitioner_phone: Optional[str]
    vapi_assistant_id: Optional[str]
    assistant_name: str
    voice_gender: str
    calendar_status: str  # connected | not_configured | none
    calendar_provider: str
    specialty: str
    suspension: Optional[Dict[str, Any]] = None
    # Indicators
    used_minutes_month: float = 0.0
    cost_usd_month: float = 0.0
    cost_usd_today: float = 0.0
    cost_usd_7d: float = 0.0
    last_event_at: Optional[datetime] = None
    error_count_window: int = 0
    transfer_validated: bool = True

    def to_summary(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "status": self.status,
        }

    def to_detail(self) -> Dict[str, Any]:
        params = {
            "contact_email": self.contact_email,
            "billing_email": self.contact_email,
            "manager_name": self.name.replace("Cabinet ", "").replace("Centre ", ""),
            "responsible_phone": "+33612345678",
            "transfer_number": self.transfer_number,
            "transfer_practitioner_phone": self.transfer_practitioner_phone,
            "transfer_validated": self.transfer_validated,
            "vapi_assistant_id": self.vapi_assistant_id,
            "assistant_name": self.assistant_name,
            "voice_gender": self.voice_gender,
            "plan_key": self.plan_key,
            "calendar_provider": self.calendar_provider,
            "calendar_status": self.calendar_status,
            "phone_number": self.transfer_number,
            "medical_specialty_label": self.specialty,
        }
        routing = []
        if self.primary_did:
            routing.append({"channel": "vocal", "key": self.primary_did, "is_active": True})
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "timezone": self.timezone,
            "status": self.status,
            "created_at": _iso(self.created_at),
            "flags": {},
            "params": params,
            "routing": routing,
        }


_TENANT_SEED: List[Dict[str, Any]] = [
    dict(
        name="Centre Medical Bonaparte",
        contact_email="contact@bonaparte-sante.fr",
        plan_key="growth",
        billing_status="active",
        primary_did="+33186260140",
        vapi="bonaparte",
        assistant_name="Sophie",
        voice_gender="female",
        calendar_status="connected",
        calendar_provider="google",
        specialty="Medecine generale",
        used_minutes=312,
        cost_month=18.40,
        last_call_hours=2,
        error_count=1,
    ),
    dict(
        name="Cabinet du Dr Lefevre",
        contact_email="dr.lefevre@cabinet-lefevre.fr",
        plan_key="starter",
        billing_status="active",
        primary_did="+33186260141",
        vapi="lefevre",
        assistant_name="Camille",
        voice_gender="female",
        calendar_status="connected",
        calendar_provider="google",
        specialty="Dermatologie",
        used_minutes=72,
        cost_month=5.20,
        last_call_hours=8,
        error_count=0,
    ),
    dict(
        name="Pole Sante Republique",
        contact_email="admin@pole-republique.com",
        plan_key="pro",
        billing_status="active",
        primary_did="+33186260142",
        vapi="republique",
        assistant_name="Lucas",
        voice_gender="male",
        calendar_status="connected",
        calendar_provider="google",
        specialty="Cardiologie",
        used_minutes=985,
        cost_month=58.90,
        last_call_hours=1,
        error_count=2,
    ),
    dict(
        name="Cabinet Saint-Charles",
        contact_email="contact@saintcharles.fr",
        plan_key="starter",
        billing_status="active",
        primary_did="+33186260143",
        vapi=None,
        assistant_name="Emma",
        voice_gender="female",
        calendar_status="not_configured",
        calendar_provider="none",
        specialty="Osteopathie",
        used_minutes=12,
        cost_month=0.95,
        last_call_hours=72,
        error_count=4,
        transfer_number=None,
        transfer_validated=False,
    ),
    dict(
        name="Maison de Sante Lumiere",
        contact_email="direction@lumiere-sante.fr",
        plan_key="growth",
        billing_status="past_due",
        primary_did="+33186260144",
        vapi="lumiere",
        assistant_name="Manon",
        voice_gender="female",
        calendar_status="connected",
        calendar_provider="google",
        specialty="Psychologie",
        used_minutes=420,
        cost_month=24.50,
        last_call_hours=5,
        error_count=1,
    ),
    dict(
        name="Centre Holistique Pasteur",
        contact_email="hello@pasteur-holistique.com",
        plan_key="growth",
        billing_status="canceled",
        status="suspended",
        suspension={"reason": "billing", "mode": "soft", "since_hours": 96},
        primary_did="+33186260145",
        vapi="pasteur",
        assistant_name="Lea",
        voice_gender="female",
        calendar_status="connected",
        calendar_provider="google",
        specialty="Naturopathie",
        used_minutes=0,
        cost_month=0,
        last_call_hours=120,
        error_count=0,
    ),
    dict(
        name="Cabinet du Dr Moreau",
        contact_email="dr.moreau@cabinet-moreau.fr",
        plan_key="growth",
        billing_status="trialing",
        primary_did="+33186260146",
        vapi="moreau",
        assistant_name="Romain",
        voice_gender="male",
        calendar_status="connected",
        calendar_provider="google",
        specialty="Ophtalmologie",
        used_minutes=124,
        cost_month=7.10,
        last_call_hours=3,
        error_count=0,
    ),
    dict(
        name="Polyclinique Beaurepaire",
        contact_email="contact@beaurepaire-clinique.fr",
        plan_key="pro",
        billing_status="active",
        primary_did="+33186260147",
        vapi="beaurepaire",
        assistant_name="Julien",
        voice_gender="male",
        calendar_status="connected",
        calendar_provider="google",
        specialty="Pluridisciplinaire",
        used_minutes=1320,
        cost_month=82.40,
        last_call_hours=1,
        error_count=3,
    ),
]


def _build_tenants() -> List[DemoTenant]:
    out: List[DemoTenant] = []
    for idx, seed in enumerate(_TENANT_SEED, start=10):
        plan = PLANS[seed["plan_key"]]
        billing_status = seed["billing_status"]
        status = seed.get("status", "active")
        suspension_seed = seed.get("suspension")
        suspension = None
        if suspension_seed:
            suspension = {
                "reason": suspension_seed["reason"],
                "mode": suspension_seed["mode"],
                "suspended_at": _iso(_ago(hours=suspension_seed["since_hours"])),
            }

        cost_today = round(seed["cost_month"] / 30.0, 2)
        cost_7d = round(seed["cost_month"] / 30.0 * 7, 2)

        out.append(
            DemoTenant(
                tenant_id=idx,
                name=seed["name"],
                contact_email=seed["contact_email"],
                timezone="Europe/Paris",
                status=status,
                plan_key=plan["key"],
                billing_status=billing_status,
                stripe_customer_id=f"cus_demo{idx:03d}" if billing_status != "canceled" else None,
                stripe_subscription_id=(
                    f"sub_demo{idx:03d}" if billing_status not in ("canceled",) else None
                ),
                created_at=_ago(days=90 - (idx - 10) * 8),
                primary_did=seed["primary_did"],
                transfer_number=seed.get("transfer_number", "+33147010203"),
                transfer_practitioner_phone="+33611223344"
                if seed.get("transfer_number") is not False
                else None,
                vapi_assistant_id=(f"asst_demo_{seed['vapi']}" if seed["vapi"] else None),
                assistant_name=seed["assistant_name"],
                voice_gender=seed["voice_gender"],
                calendar_status=seed["calendar_status"],
                calendar_provider=seed["calendar_provider"],
                specialty=seed["specialty"],
                suspension=suspension,
                used_minutes_month=float(seed["used_minutes"]),
                cost_usd_month=float(seed["cost_month"]),
                cost_usd_today=cost_today,
                cost_usd_7d=cost_7d,
                last_event_at=_ago(hours=seed["last_call_hours"]),
                error_count_window=int(seed["error_count"]),
                transfer_validated=bool(seed.get("transfer_validated", True)),
            )
        )
    return out


_TENANTS: List[DemoTenant] = _build_tenants()
_TENANTS_BY_ID: Dict[int, DemoTenant] = {t.tenant_id: t for t in _TENANTS}


# ---------------------------------------------------------------------------
# Calls demo (vapi_calls + ivr_events + transcripts)
# ---------------------------------------------------------------------------


CALL_RESULTS = [
    ("rdv", 0.55),
    ("transfer", 0.18),
    ("abandoned", 0.18),
    ("error", 0.04),
    ("info", 0.05),
]

EVENT_BY_RESULT = {
    "rdv": "booking_confirmed",
    "transfer": "transferred_human",
    "abandoned": "user_abandon",
    "error": "anti_loop_trigger",
    "info": "call_completed",
}

ENDED_REASON_BY_RESULT = {
    "rdv": "customer-ended-call",
    "transfer": "assistant-forwarded-call",
    "abandoned": "customer-did-not-answer",
    "error": "assistant-error",
    "info": "customer-ended-call",
}

PATIENT_FIRST_NAMES = [
    "Marie", "Pierre", "Sophie", "Jean", "Camille", "Antoine", "Lea", "Lucas",
    "Manon", "Hugo", "Chloe", "Nathan", "Emma", "Romain", "Clara", "Julien",
    "Sarah", "Maxime", "Alice", "Thomas",
]
PATIENT_LAST_NAMES = [
    "Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand",
    "Leroy", "Moreau", "Simon", "Laurent", "Lefevre", "Roux", "Fournier", "Mercier",
]
MOTIFS = [
    "Consultation generale",
    "Renouvellement ordonnance",
    "Suivi traitement",
    "Resultats d'analyse",
    "Premiere consultation",
    "Bilan annuel",
    "Douleur lombaire",
    "Suivi pediatrique",
    "Question administrative",
    "Renouvellement vaccin",
]


def _customer_phone() -> str:
    return f"+336{_RNG.randint(10000000, 99999999):08d}"


def _patient_name() -> str:
    return f"{_RNG.choice(PATIENT_FIRST_NAMES)} {_RNG.choice(PATIENT_LAST_NAMES)}"


def _pick_result() -> str:
    r = _RNG.random()
    cum = 0.0
    for label, w in CALL_RESULTS:
        cum += w
        if r <= cum:
            return label
    return "info"


def _build_transcript(result: str, motif: str, patient_name: str) -> List[Dict[str, Any]]:
    """Genere une mini conversation pour le drawer detail. Format : [{role, transcript, created_at}]."""
    base_time = _NOW
    lines: List[Tuple[str, str]] = [
        ("assistant", f"Bonjour, vous etes bien au cabinet. Je suis l'assistante. Comment puis-je vous aider ?"),
        ("user", f"Bonjour, je suis {patient_name}, j'aimerais prendre rendez-vous."),
        ("assistant", "Avec plaisir. Pouvez-vous me preciser le motif de votre demande ?"),
        ("user", motif),
    ]
    if result == "rdv":
        lines.extend([
            ("assistant", "Tres bien. J'ai un creneau jeudi a 14h30, est-ce que cela vous convient ?"),
            ("user", "Oui, parfait."),
            ("assistant", "C'est note, je vous envoie une confirmation par SMS."),
        ])
    elif result == "transfer":
        lines.extend([
            ("assistant", "C'est une question medicale specifique, je vous transfere vers le praticien."),
            ("user", "D'accord, je patiente."),
        ])
    elif result == "abandoned":
        lines.extend([
            ("assistant", "Je vous propose plusieurs creneaux : mardi 9h, jeudi 14h, vendredi 16h."),
            ("user", "(silence)"),
            ("assistant", "Allo ? Etes-vous toujours en ligne ?"),
        ])
    elif result == "error":
        lines.extend([
            ("assistant", "Je n'arrive pas a verifier votre dossier, je vous propose de rappeler ulterieurement."),
        ])
    out = []
    for i, (role, text) in enumerate(lines):
        out.append({
            "role": role,
            "transcript": text,
            "is_final": True,
            "created_at": _iso(base_time - timedelta(seconds=(len(lines) - i) * 8)),
        })
    return out


@dataclass
class DemoCall:
    tenant_id: int
    call_id: str
    customer_number: str
    started_at: datetime
    ended_at: datetime
    duration_sec: float
    cost_usd: float
    result: str
    motif: str
    patient_name: str
    ended_reason: str
    transcript: List[Dict[str, Any]] = field(default_factory=list)


def _build_calls() -> List[DemoCall]:
    """Genere ~70 calls reparties entre tenants, selon leur volume relatif."""
    out: List[DemoCall] = []
    # Volume relatif par tenant (approximatif, depend du plan / activite)
    relative_volume = {
        10: 14,  # Bonaparte
        11: 6,   # Lefevre
        12: 18,  # Republique
        13: 2,   # Saint-Charles (peu de calls)
        14: 12,  # Lumiere
        15: 0,   # Pasteur (suspended)
        16: 7,   # Moreau (trial)
        17: 22,  # Beaurepaire (top consommateur)
    }
    for tenant_id, n_calls in relative_volume.items():
        tenant = _TENANTS_BY_ID[tenant_id]
        for _ in range(n_calls):
            hours_ago = _RNG.uniform(0.2, 14 * 24)
            started = _NOW - timedelta(hours=hours_ago)
            duration_sec = _RNG.uniform(45, 320)
            ended = started + timedelta(seconds=duration_sec)
            cost = round(duration_sec / 60.0 * 0.06, 4)  # ~$0.06/min
            result = _pick_result()
            motif = _RNG.choice(MOTIFS)
            patient_name = _patient_name()
            call_id = f"call_demo_{uuid.UUID(int=_RNG.getrandbits(128)).hex[:16]}"
            ended_reason = ENDED_REASON_BY_RESULT[result]
            # Genere un transcript pour les appels recents (~50 % d'appels narratifs)
            transcript = []
            if hours_ago < 7 * 24 and _RNG.random() < 0.6:
                transcript = _build_transcript(result, motif, patient_name)
            out.append(
                DemoCall(
                    tenant_id=tenant_id,
                    call_id=call_id,
                    customer_number=_customer_phone(),
                    started_at=started,
                    ended_at=ended,
                    duration_sec=round(duration_sec, 1),
                    cost_usd=cost,
                    result=result,
                    motif=motif,
                    patient_name=patient_name,
                    ended_reason=ended_reason,
                    transcript=transcript,
                )
            )
    out.sort(key=lambda c: c.started_at, reverse=True)
    return out


_CALLS: List[DemoCall] = _build_calls()
_CALLS_BY_ID: Dict[Tuple[int, str], DemoCall] = {(c.tenant_id, c.call_id): c for c in _CALLS}


# ---------------------------------------------------------------------------
# Leads pre-onboarding demo
# ---------------------------------------------------------------------------

LEAD_SPECIALTIES = [
    ("medecine_generale", "Medecine generale"),
    ("dermatologie", "Dermatologie"),
    ("kinesitherapie", "Kinesitherapie"),
    ("dentiste", "Dentiste"),
    ("psychologue", "Psychologue"),
    ("osteopathe", "Osteopathie"),
    ("nutritionniste", "Nutritionniste"),
    ("orthophoniste", "Orthophoniste"),
]
LEAD_VOLUMES = ["less_than_10", "10_to_50", "50_to_100", "more_than_100"]
LEAD_PAIN_POINTS = [
    "appels_perdus",
    "secretariat_sature",
    "rdv_oublies",
    "horaires_etendus",
    "no_show",
]


def _build_leads() -> List[Dict[str, Any]]:
    """12 leads varies."""
    leads_seed = [
        dict(email="dr.dupont@cabinet-medical.fr", spec=0, vol=2, status="new", enterprise=False, hours_ago=2),
        dict(email="contact@centre-marais.fr", spec=4, vol=3, status="new", enterprise=True, hours_ago=8),
        dict(email="marie.bernard@dermalp.fr", spec=1, vol=1, status="contacted", enterprise=False, hours_ago=22),
        dict(email="cabinet.legrand@gmail.com", spec=2, vol=1, status="contacted", enterprise=False, hours_ago=50),
        dict(email="hello@dental-leon.com", spec=3, vol=2, status="new", enterprise=False, hours_ago=72),
        dict(email="direction@reseau-vitalys.fr", spec=0, vol=3, status="contacted", enterprise=True, hours_ago=120),
        dict(email="psy.morel@cabinet-morel.fr", spec=4, vol=0, status="new", enterprise=False, hours_ago=140),
        dict(email="contact@osteo-paris9.fr", spec=5, vol=1, status="lost", enterprise=False, hours_ago=240),
        dict(email="dr.bonnet@nutrigam.com", spec=6, vol=1, status="converted", enterprise=False, hours_ago=320),
        dict(email="contact@orthophonie-est.fr", spec=7, vol=2, status="converted", enterprise=False, hours_ago=400),
        dict(email="manager@groupe-medisens.fr", spec=0, vol=3, status="new", enterprise=True, hours_ago=4),
        dict(email="dr.olivier@dermlille.fr", spec=1, vol=1, status="lost", enterprise=False, hours_ago=600),
    ]
    out: List[Dict[str, Any]] = []
    for seed in leads_seed:
        spec_key, spec_label = LEAD_SPECIALTIES[seed["spec"]]
        vol = LEAD_VOLUMES[seed["vol"]]
        created_at = _ago(hours=seed["hours_ago"])
        contacted_at = (
            _ago(hours=max(1, seed["hours_ago"] - 24))
            if seed["status"] in ("contacted", "converted", "lost")
            else None
        )
        converted_at = _ago(hours=max(1, seed["hours_ago"] - 48)) if seed["status"] == "converted" else None
        amplitude_h = _RNG.choice([8, 9, 10, 11, 12])

        # Journal de notes simule
        notes_log: List[Dict[str, Any]] = [
            {
                "text": f"Lead recu via le formulaire ({seed['email']}).",
                "action": "creation",
                "created_at": _iso(created_at),
            }
        ]
        if seed["status"] == "contacted":
            notes_log.append({
                "text": "Premier contact pris par mail. RDV de demo a planifier.",
                "action": "statut",
                "created_at": _iso(contacted_at) if contacted_at else _iso(created_at),
            })
        if seed["status"] == "converted":
            notes_log.extend([
                {
                    "text": "Demo realisee, le client a valide la solution.",
                    "action": "demo",
                    "created_at": _iso(contacted_at) if contacted_at else _iso(created_at),
                },
                {
                    "text": "Client cree dans la plateforme.",
                    "action": "conversion",
                    "created_at": _iso(converted_at) if converted_at else _iso(created_at),
                },
            ])
        if seed["status"] == "lost":
            notes_log.append({
                "text": "Pas de retour apres deux relances. Marque perdu.",
                "action": "statut",
                "created_at": _iso(contacted_at) if contacted_at else _iso(created_at),
            })

        out.append(
            {
                "id": str(uuid.UUID(int=_RNG.getrandbits(128))),
                "email": seed["email"],
                "daily_call_volume": vol,
                "medical_specialty": spec_key,
                "medical_specialty_label": spec_label,
                "primary_pain_point": _RNG.choice(LEAD_PAIN_POINTS),
                "assistant_name": _RNG.choice(["Sophie", "Camille", "Lucas", "Emma", "Manon"]),
                "voice_gender": _RNG.choice(["female", "male"]),
                "opening_hours": {
                    "monday": [["08:00", "12:00"], ["14:00", "19:00"]],
                    "tuesday": [["08:00", "12:00"], ["14:00", "19:00"]],
                },
                "wants_callback": _RNG.choice([True, False]),
                "callback_phone": _customer_phone() if _RNG.random() < 0.4 else None,
                "callback_booking_date": None,
                "callback_booking_slot": None,
                "is_enterprise": seed["enterprise"],
                "source": "landing_cta",
                "status": seed["status"],
                "notes": "Demande gros volume" if seed["enterprise"] else None,
                "notes_log": notes_log,
                "contacted_at": _iso(contacted_at) if contacted_at else None,
                "converted_at": _iso(converted_at) if converted_at else None,
                "tenant_id": 10 if seed["status"] == "converted" else None,
                "created_at": _iso(created_at),
                "updated_at": _iso(created_at),
                "last_submitted_at": _iso(created_at),
                "specialty_other": None,
                "max_daily_amplitude": amplitude_h,
            }
        )
    out.sort(key=lambda l: l["created_at"], reverse=True)
    return out


_LEADS: List[Dict[str, Any]] = _build_leads()
_LEADS_BY_ID: Dict[str, Dict[str, Any]] = {l["id"]: l for l in _LEADS}


# ---------------------------------------------------------------------------
# Public helpers (consommes par router.py)
# ---------------------------------------------------------------------------


def get_tenants(include_inactive: bool = True) -> List[DemoTenant]:
    if include_inactive:
        return list(_TENANTS)
    return [t for t in _TENANTS if t.status == "active"]


def get_tenant(tenant_id: int) -> Optional[DemoTenant]:
    return _TENANTS_BY_ID.get(int(tenant_id))


def get_calls(
    tenant_id: Optional[int] = None,
    days: int = 30,
    result: Optional[str] = None,
    limit: int = 50,
) -> List[DemoCall]:
    cutoff = _NOW - timedelta(days=days)
    out: List[DemoCall] = []
    for c in _CALLS:
        if tenant_id is not None and c.tenant_id != int(tenant_id):
            continue
        if c.started_at < cutoff:
            continue
        if result and result != c.result:
            continue
        out.append(c)
        if len(out) >= limit:
            break
    return out


def get_call(tenant_id: int, call_id: str) -> Optional[DemoCall]:
    return _CALLS_BY_ID.get((int(tenant_id), call_id))


def get_leads(status: Optional[str] = None, enterprise_only: bool = False) -> List[Dict[str, Any]]:
    out = list(_LEADS)
    if status:
        out = [l for l in out if l["status"] == status]
    if enterprise_only:
        out = [l for l in out if l.get("is_enterprise")]
    return out


def get_lead(lead_id: str) -> Optional[Dict[str, Any]]:
    return _LEADS_BY_ID.get(lead_id)


def get_now() -> datetime:
    return _NOW


def iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return _iso(dt)
