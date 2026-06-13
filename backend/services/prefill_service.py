"""
UWI — Préparation de fiche (prefill à l'ouverture)
===================================================
Alimente la carte "Préparation UWi" du front. Combine DEUX sources :

  1. Le dernier appel Clara du patient (DÉCLARATIF) -> motif + anamnèse déclarés
  2. Le context pack (DOSSIER)                       -> dernière consult, examens en attente

Renvoie EXACTEMENT le format attendu par onLoadPrefill côté front :
  {
    source: "clara" | "context",
    resume_appel: str | None,
    derniere_consultation: str,
    documents: str,
    extraction: { motif?, anamnese? },         # JAMAIS de constantes / impression / examens
    champs_confiance: [...],
    avertissements: [...]
  }

Route : GET /api/tenant/patients/{patient_id}/prefill

PRINCIPE DE SÛRETÉ :
  Un appel téléphonique ne produit NI constante, NI diagnostic, NI examen.
  Le prefill ne propose donc QUE motif + anamnèse, et tout est étiqueté
  "déclaré par le patient" — jamais comme fait clinique établi.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Optional

from pydantic import BaseModel


# =============================================================================
# 1. Modèle de sortie (miroir de ce que consomme le front)
# =============================================================================

class PrefillResult(BaseModel):
    source: str = "context"
    resume_appel: Optional[str] = None
    derniere_consultation: str = "Aucune consultation récente dans le dossier."
    documents: str = "Aucun résultat biologique intégré."
    extraction: dict[str, Any] = {}                 # uniquement motif / anamnese
    champs_confiance: list[dict[str, Any]] = []
    avertissements: list[str] = []


# =============================================================================
# 2. Récupération du dernier appel Clara
# =============================================================================
# Adapter les noms de colonnes à ton schéma `calls` (cf. UwiAppels).
# On privilégie un résumé structuré produit à la fin de l'appel (Vapi
# post-call analysis) ; sinon on retombe sur le transcript brut + LLM.

LAST_CALL_SQL = """
SELECT
    id,
    started_at,
    transcript,            -- texte intégral de l'appel (peut être NULL)
    declared_summary       -- résumé structuré éventuel (JSONB) produit en fin d'appel
FROM calls
WHERE tenant_id = %(tenant_id)s
  AND direction = 'inbound'
  AND (
      (%(patient_id)s IS NOT NULL AND patient_id = %(patient_id)s)
      OR (%(patient_phone)s IS NOT NULL AND customer_number = %(patient_phone)s)
  )
ORDER BY started_at DESC
LIMIT 1;
"""


def fetch_last_call(
    conn,
    *,
    tenant_id: str,
    patient_id: Optional[str] = None,
    patient_phone: Optional[str] = None,
) -> Optional[dict]:
    # Défense en profondeur : scope tenant posé avant toute requête calls.
    conn.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant_id,))
    row = conn.execute(
        LAST_CALL_SQL,
        {
            "tenant_id": tenant_id,
            "patient_id": patient_id,
            "patient_phone": patient_phone,
        },
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "started_at": row[1],
        "transcript": row[2],
        "declared_summary": row[3],   # dict | None
    }


# =============================================================================
# 3. Extraction "déclarative" depuis le transcript (si pas de résumé structuré)
# =============================================================================
# Prompt VOLONTAIREMENT plus restrictif que voice_extraction :
#   - seulement motif + anamnèse
#   - tout est "déclaré par le patient", jamais un fait clinique

PREFILL_SYSTEM_PROMPT = """\
Tu prépares une fiche de consultation à partir d'un appel téléphonique de prise
de rendez-vous (le patient a parlé à un assistant, pas à un médecin).

Tu n'extrais QUE deux choses, et UNIQUEMENT ce que le patient a réellement dit :
- motif    : la raison de venue telle que DÉCLARÉE par le patient (phrase courte)
- anamnese : les symptômes/contexte DÉCLARÉS par le patient au téléphone

INTERDITS ABSOLUS :
- Aucune constante (le patient ne se mesure pas au téléphone).
- Aucune impression / hypothèse / diagnostic (ce n'est pas un médecin qui parle).
- Aucun examen complémentaire.
- N'invente rien. Si le patient n'a rien dit d'exploitable, renvoie un objet vide.
- Reformule sobrement, sans interpréter médicalement. Garde le registre déclaratif.

Format de sortie — JSON STRICT, rien d'autre :
{ "motif": "...", "anamnese": "..." }
ou {} si rien d'exploitable. Pas de ```json, pas de préambule.
"""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def extract_declared(transcript: str, anthropic_client, model: str = "claude-sonnet-4-6") -> dict:
    """Extrait motif + anamnèse déclarés depuis un transcript d'appel."""
    if not transcript or not transcript.strip():
        return {}
    msg = await anthropic_client.messages.create(
        model=model,
        max_tokens=500,
        system=PREFILL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Transcript de l'appel :\n\"\"\"\n{transcript}\n\"\"\""}],
    )
    raw = "".join(b.text for b in msg.content if b.type == "text")
    try:
        data = json.loads(_strip_fences(raw))
    except json.JSONDecodeError:
        return {}
    # filtre dur : on ne garde QUE motif et anamnese, rien d'autre ne peut passer
    return {k: v for k, v in data.items() if k in ("motif", "anamnese") and isinstance(v, str) and v.strip()}


# =============================================================================
# 4. Métriques dossier minimales (sous-ensemble du context pack)
# =============================================================================

DOSSIER_BITS_SQL = """
SELECT
    (SELECT MAX(date_consultation)
       FROM consultations
      WHERE tenant_id = %(tenant_id)s
        AND patient_id = %(patient_id)s) AS derniere_consult,
    (SELECT COALESCE(jsonb_agg(DISTINCT ex), '[]'::jsonb)
       FROM consultations, unnest(examens_demandes) AS ex
       WHERE tenant_id = %(tenant_id)s
         AND patient_id = %(patient_id)s
         AND date_consultation >= CURRENT_DATE - INTERVAL '3 months') AS examens_recents;
"""


def fetch_dossier_bits(conn, *, tenant_id: str, patient_id: str) -> dict:
    conn.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant_id,))
    row = conn.execute(
        DOSSIER_BITS_SQL,
        {
            "tenant_id": tenant_id,
            "patient_id": patient_id,
        },
    ).fetchone()
    return {"derniere_consult": row[0], "examens_recents": row[1] or []}


def _fmt_derniere_consult(d: Optional[date]) -> str:
    if not d:
        return "Aucune consultation récente dans le dossier."
    jours = (date.today() - d).days
    if jours == 0:
        return "Dernière consultation : aujourd'hui."
    if jours < 31:
        return f"Dernière consultation il y a {jours} jour{'s' if jours > 1 else ''}."
    mois = jours // 30
    return f"Dernière consultation il y a ~{mois} mois."


def _fmt_documents(examens_recents: list[str]) -> str:
    if not examens_recents:
        return "Aucun examen récent en attente de résultat."
    return f"{len(examens_recents)} examen(s) demandé(s) récemment : {', '.join(examens_recents)}."


# =============================================================================
# 5. Orchestration : assemble le prefill
# =============================================================================

def assemble_prefill(
    *,
    declared: dict,                 # {motif?, anamnese?} issu de l'appel (ou {})
    call_started_at: Optional[Any],
    raw_quote: Optional[str],       # citation brute du patient (pour resume_appel)
    derniere_consult: Optional[date],
    examens_recents: list[str],
) -> PrefillResult:
    """Logique pure (testable sans I/O). Décide de la source et étiquette le motif."""
    extraction: dict[str, Any] = {}
    champs_confiance: list[dict] = []
    avertissements: list[str] = []
    has_call = bool(declared.get("motif") or declared.get("anamnese") or raw_quote)

    if declared.get("motif"):
        # le motif est DÉCLARÉ -> on le suffixe explicitement et confiance modérée
        extraction["motif"] = f"{declared['motif'].rstrip('.')} (déclaré à la prise de RDV)"
        champs_confiance.append({"champ": "motif", "niveau": 0.55})
    if declared.get("anamnese"):
        extraction["anamnese"] = declared["anamnese"]
        champs_confiance.append({"champ": "anamnese", "niveau": 0.5})

    if has_call:
        avertissements.append("Informations déclarées par le patient au téléphone — à confirmer en consultation.")

    return PrefillResult(
        source="clara" if has_call else "context",
        resume_appel=raw_quote,
        derniere_consultation=_fmt_derniere_consult(derniere_consult),
        documents=_fmt_documents(examens_recents),
        extraction=extraction,
        champs_confiance=champs_confiance,
        avertissements=avertissements,
    )


async def build_prefill(
    pool,
    tenant_id: str,
    patient_id: str,
    anthropic_client,
    *,
    patient_phone: Optional[str] = None,
) -> PrefillResult:
    """Récupère appel + dossier et assemble le prefill."""
    with pool.connection() as conn:
        conn.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant_id,))
        call = fetch_last_call(
            conn,
            tenant_id=tenant_id,
            patient_id=patient_id,
            patient_phone=patient_phone,
        )
        bits = fetch_dossier_bits(conn, tenant_id=tenant_id, patient_id=patient_id)

    declared: dict = {}
    raw_quote: Optional[str] = None
    if call:
        ds = call.get("declared_summary") or {}
        if isinstance(ds, dict) and (ds.get("motif") or ds.get("anamnese")):
            # résumé structuré déjà produit en fin d'appel : pas de LLM
            declared = {k: ds[k] for k in ("motif", "anamnese") if ds.get(k)}
            raw_quote = ds.get("verbatim") or ds.get("citation")
        elif call.get("transcript"):
            # sinon extraction déclarative sur le transcript
            declared = await extract_declared(call["transcript"], anthropic_client)
            raw_quote = _first_patient_quote(call["transcript"])

    return assemble_prefill(
        declared=declared,
        call_started_at=call["started_at"] if call else None,
        raw_quote=raw_quote,
        derniere_consult=bits["derniere_consult"],
        examens_recents=bits["examens_recents"],
    )


def _first_patient_quote(transcript: str, max_len: int = 240) -> Optional[str]:
    """Extrait une citation représentative du patient pour resume_appel.
    Heuristique simple : première réplique 'patient' un peu substantielle."""
    if not transcript:
        return None
    for line in transcript.splitlines():
        low = line.lower()
        if low.startswith(("patient", "user", "appelant")):
            quote = line.split(":", 1)[-1].strip()
            if len(quote) >= 15:
                quote = quote[:max_len].rstrip()
                return f"« {quote} »"
    return None


# =============================================================================
# 6. Route FastAPI
# =============================================================================
"""
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/tenant/patients", tags=["consultations"])

@router.get("/{patient_id}/prefill")
async def patient_prefill(
    patient_id: str,
    tenant=Depends(get_current_tenant),
    anthropic=Depends(get_anthropic),
):
    result = await build_prefill(pool, tenant.id, patient_id, anthropic)
    return result.model_dump()
"""
