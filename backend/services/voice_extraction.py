"""
UWI — Extraction vocale structurée (dictée -> champs de la fiche)
=================================================================
Pipeline batch :

    audio  ->  Deepgram (STT)  ->  transcription brute
                                        |
                                        v
                          Claude (extracteur structuré)
                                        |
                                        v
              JSON partiel (mêmes clés que ConsultationCreate)
                                        |
                                        v
                  merge côté front en mode "draft" validable

Route : POST /api/tenant/consultations/transcribe   (multipart: audio)
        -> { transcription, extraction, champs_confiance }

RÈGLES NON NÉGOCIABLES (médical) :
  1. N'INVENTE RIEN. Champ non mentionné = absent du JSON (jamais de valeur par défaut).
  2. N'écrase rien : le merge front décide, l'extracteur ne fait que proposer.
  3. Aucune suggestion diagnostique : on range ce que le praticien a dit, point.
  4. Chaque champ extrait porte un niveau de confiance -> affichage différencié.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from pydantic import BaseModel

# =============================================================================
# 1. Modèles de sortie
# =============================================================================

class ChampConfiance(BaseModel):
    """Confiance d'extraction par chemin de champ (ex. 'examen_clinique.constantes.fc_bpm')."""
    champ: str
    niveau: float  # 0.0 - 1.0


class ExtractionResult(BaseModel):
    transcription: str
    extraction: dict[str, Any]          # JSON partiel, clés = celles de la fiche
    champs_confiance: list[ChampConfiance]
    avertissements: list[str] = []      # incohérences à signaler, PAS des diagnostics


# =============================================================================
# 2. Le prompt d'extraction — le nerf de la guerre
# =============================================================================
# Conçu pour Claude. Sortie JSON STRICTE, schéma identique à la fiche.
# On donne le contexte patient (antécédents) pour désambiguïser, JAMAIS pour
# compléter : le contexte aide à comprendre la parole, il n'ajoute pas de données.

EXTRACTION_SYSTEM_PROMPT = """\
Tu es un module d'extraction pour un logiciel de consultation médicale français.
Ta SEULE tâche : ranger ce qu'un médecin vient de dicter dans les bons champs d'une fiche.

Tu ne diagnostiques pas. Tu ne suggères pas d'examens. Tu ne complètes pas.
Tu RANGES ce qui a été dit, mot pour mot dans le fond, reformulé proprement dans la forme.

## Champs cibles (n'émets QUE ceux réellement mentionnés)

- motif                  : raison de venue (phrase courte)
- anamnese               : histoire de la maladie, symptômes, chronologie, contexte
- examen_clinique.etat_general    : état général observé
- examen_clinique.examen_physique : examen par appareil
- examen_clinique.constantes : objet avec, si dictés :
    fc_bpm (entier), pa_systolique (entier), pa_diastolique (entier),
    temperature_c (décimal), spo2_pct (entier), fr_min (entier),
    poids_kg (décimal), taille_cm (entier)
- impression_clinique    : conclusion/hypothèse formulée PAR LE MÉDECIN
- conduite_a_tenir.examens_complementaires : liste d'examens qu'il demande explicitement
- conduite_a_tenir.prescription : traitement prescrit
- conduite_a_tenir.orientation  : orientation/avis spécialiste
- conduite_a_tenir.suivi.consignes : consignes données au patient

## Règles de conversion orale -> structuré

- "tension onze sept" / "11/7" / "110 sur 70" -> pa_systolique:110, pa_diastolique:70
  (le médecin parle en cmHg à l'oral "onze" = 110 mmHg ; convertis en mmHg)
- "cœur à 102" / "fréquence 102" / "pouls 102" -> fc_bpm:102
- "saturation 98" / "sat à 98" -> spo2_pct:98
- "37°5" / "trente-sept cinq" -> temperature_c:37.5
- "il fait 80 kilos" -> poids_kg:80

## Règles de rangement

- Ce qui décrit POURQUOI il vient -> motif (court)
- Ce qui décrit l'évolution/les symptômes -> anamnese
- Ce qu'il CONSTATE à l'examen -> examen_clinique
- Ce qu'il CONCLUT ("je pense à", "ça oriente vers", "syndrome X à explorer") -> impression_clinique
- Ce qu'il DEMANDE/PRESCRIT -> conduite_a_tenir

## Interdits absolus

- N'invente AUCUNE valeur. Température non dite = champ absent. Jamais de "par défaut".
- N'ajoute AUCUN examen que le médecin n'a pas explicitement demandé, même si "logique".
- Ne formule AUCUN diagnostic de ta part. Si le médecin n'a pas conclu, impression_clinique absent.
- Si un passage est ambigu ou inaudible, ne devine pas : baisse la confiance, ou omets.

## Format de sortie — JSON STRICT, rien d'autre

{
  "extraction": { ...uniquement les champs mentionnés, structure ci-dessus... },
  "confiance": { "chemin.du.champ": 0.0-1.0, ... },
  "avertissements": [ "incohérences factuelles éventuelles, sans interprétation médicale" ]
}

Exemple d'avertissement acceptable : "SpO2 98% dictée mais 'détresse respiratoire' mentionnée — à vérifier."
Exemple INTERDIT : "Les symptômes évoquent une anémie" (c'est un diagnostic, pas ton rôle).

Réponds UNIQUEMENT par le JSON. Pas de ```json, pas de préambule.
"""


def build_user_prompt(transcription: str, antecedents: Optional[str] = None) -> str:
    contexte = ""
    if antecedents:
        contexte = (
            f"\n\nContexte patient (pour COMPRENDRE la dictée, pas pour la compléter) :\n"
            f"Antécédents : {antecedents}"
        )
    return f"Dictée du médecin à ranger :\n\"\"\"\n{transcription}\n\"\"\"{contexte}"


# =============================================================================
# 3. Parsing robuste de la sortie LLM
# =============================================================================

# Champs numériques -> bornes (cohérentes avec les CHECK SQL et Pydantic)
_NUM_BOUNDS = {
    "fc_bpm": (20, 300), "pa_systolique": (50, 300), "pa_diastolique": (20, 200),
    "temperature_c": (30, 45), "spo2_pct": (50, 100), "fr_min": (4, 80),
    "poids_kg": (1, 400), "taille_cm": (30, 250),
}


def _strip_fences(text: str) -> str:
    """Enlève d'éventuels ```json ... ``` si le modèle déborde malgré la consigne."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _validate_constantes(constantes: dict) -> tuple[dict, list[str]]:
    """Filtre les constantes hors bornes physiologiques -> on les rejette plutôt
    que d'insérer une valeur aberrante issue d'une mauvaise transcription."""
    clean, warns = {}, []
    for k, v in constantes.items():
        if k not in _NUM_BOUNDS:
            continue
        try:
            val = float(v)
        except (TypeError, ValueError):
            continue
        lo, hi = _NUM_BOUNDS[k]
        if lo <= val <= hi:
            clean[k] = int(val) if k != "temperature_c" and k != "poids_kg" else val
        else:
            warns.append(f"Valeur '{k}={v}' hors plage plausible, ignorée (transcription douteuse).")
    return clean, warns


def parse_extraction(raw_text: str, transcription: str) -> ExtractionResult:
    """Parse + sécurise la sortie du LLM. Tolérant : en cas d'échec JSON,
    renvoie la transcription brute pour que le médecin garde la main."""
    avertissements: list[str] = []
    try:
        data = json.loads(_strip_fences(raw_text))
    except json.JSONDecodeError:
        return ExtractionResult(
            transcription=transcription,
            extraction={},
            champs_confiance=[],
            avertissements=["Extraction automatique indisponible — transcription brute fournie."],
        )

    extraction = data.get("extraction", {}) or {}

    # Sécurise les constantes (bornes physio)
    ec = extraction.get("examen_clinique", {})
    if isinstance(ec.get("constantes"), dict):
        ec["constantes"], cwarns = _validate_constantes(ec["constantes"])
        avertissements.extend(cwarns)
        if not ec["constantes"]:
            ec.pop("constantes", None)
        extraction["examen_clinique"] = ec

    # Confiance
    confiance = data.get("confiance", {}) or {}
    champs_confiance = [
        ChampConfiance(champ=k, niveau=max(0.0, min(1.0, float(v))))
        for k, v in confiance.items()
        if isinstance(v, (int, float))
    ]

    avertissements.extend(data.get("avertissements", []) or [])

    return ExtractionResult(
        transcription=transcription,
        extraction=extraction,
        champs_confiance=champs_confiance,
        avertissements=avertissements,
    )


# =============================================================================
# 4. Orchestration : audio -> STT -> extraction
# =============================================================================

async def transcribe_and_extract(
    audio_bytes: bytes,
    *,
    deepgram_client,        # ton client Deepgram déjà configuré (Vapi stack)
    anthropic_client,       # client Anthropic
    antecedents: Optional[str] = None,
    model: str = "claude-sonnet-4-6",
) -> ExtractionResult:
    """
    1. STT Deepgram (fr, ponctuation, vocabulaire médical via keywords si dispo)
    2. Extraction structurée via Claude
    3. Parsing sécurisé
    """
    # --- 1. STT ---
    dg_response = await deepgram_client.listen.asyncrest.v("1").transcribe_file(
        {"buffer": audio_bytes},
        {
            "model": "nova-2-medical",   # modèle médical Deepgram si dispo sur ton plan, sinon "nova-2"
            "language": "fr",
            "punctuate": True,
            "smart_format": True,
        },
    )
    transcription = (
        dg_response.results.channels[0].alternatives[0].transcript
        if dg_response.results.channels else ""
    )
    if not transcription.strip():
        return ExtractionResult(
            transcription="",
            extraction={},
            champs_confiance=[],
            avertissements=["Aucune parole détectée."],
        )

    # --- 2. Extraction LLM ---
    message = await anthropic_client.messages.create(
        model=model,
        max_tokens=1500,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(transcription, antecedents)}],
    )
    raw = "".join(block.text for block in message.content if block.type == "text")

    # --- 3. Parsing ---
    return parse_extraction(raw, transcription)


# =============================================================================
# 5. Route FastAPI (à monter sur ton routeur tenant existant)
# =============================================================================
"""
from fastapi import APIRouter, UploadFile, File, Depends

router = APIRouter(prefix="/api/tenant/consultations", tags=["consultations"])

@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    patient_id: str | None = None,
    tenant=Depends(get_current_tenant),
    deepgram=Depends(get_deepgram),
    anthropic=Depends(get_anthropic),
):
    antecedents = None
    if patient_id:
        # réutilise le context pack : on ne passe QUE les antécédents au LLM
        pack = get_context_pack(pool, tenant.id, patient_id)
        antecedents = (pack.get("dossier") or {}).get("antecedents_medicaux")

    audio_bytes = await audio.read()
    result = await transcribe_and_extract(
        audio_bytes,
        deepgram_client=deepgram,
        anthropic_client=anthropic,
        antecedents=antecedents,
    )
    return result.model_dump()
"""
