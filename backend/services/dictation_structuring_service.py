"""
Structuration de la dictée ambiante (fiche consultation UWi).

POST /api/tenant/consultations/structure-dictation
  { transcript, motif_choisi?, motif_patient_verbatim?, dossier_state? }
  -> { blocks: Block[], degraded: bool }

Règles non négociables :
- UWi ne génère JAMAIS de contenu médical : chaque bloc doit être justifié par
  des extraits verbatim du transcript (sourceSpans). Un bloc sans justification
  est rejeté côté serveur, quoi que retourne le LLM.
- L'IMC est calculé côté serveur (jamais par le LLM).
- La criticité (impression, decision, allergies) est forcée côté serveur.
- En échec/timeout LLM : réponse dégradée avec un unique bloc `elements`
  contenant le transcript complet — on ne perd JAMAIS une dictée.
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# Timeout dur de l'appel LLM (la route ajoute sa propre marge asyncio).
STRUCTURE_LLM_TIMEOUT_SECONDS = 15.0

BlockField = Literal[
    "motif", "elements", "examen", "impression", "decision", "note",
    "allergies", "antecedents", "traitements", "mesures", "contexte",
]
BlockDest = Literal["day", "dossier"]
BlockProvenance = Literal["dictee", "motif_patient", "calcule"]
BlockStatus = Literal["propose", "confirme", "non_renseigne", "modifie"]

# field -> (dest, label, critical, danger) — vérité serveur, le LLM ne décide pas.
FIELD_META: Dict[str, Dict[str, Any]] = {
    "motif": {"dest": "day", "label": "Motif", "critical": False, "danger": False},
    "elements": {"dest": "day", "label": "Éléments", "critical": False, "danger": False},
    "examen": {"dest": "day", "label": "Examen", "critical": False, "danger": False},
    "impression": {"dest": "day", "label": "Impression", "critical": True, "danger": False},
    "decision": {"dest": "day", "label": "Conduite", "critical": True, "danger": False},
    "note": {"dest": "day", "label": "Note interne", "critical": False, "danger": False},
    "allergies": {"dest": "dossier", "label": "Allergies", "critical": True, "danger": True},
    "antecedents": {"dest": "dossier", "label": "Antécédents", "critical": False, "danger": False},
    "traitements": {"dest": "dossier", "label": "Traitements", "critical": False, "danger": False},
    "mesures": {"dest": "dossier", "label": "Mesures", "critical": False, "danger": False},
    "contexte": {"dest": "dossier", "label": "Contexte", "critical": False, "danger": False},
}

DAY_FIELD_ORDER = ["motif", "elements", "examen", "impression", "decision", "note"]
DOSSIER_FIELD_ORDER = ["mesures", "allergies", "traitements", "antecedents", "contexte"]

STRUCTURE_SYSTEM_PROMPT = """Tu structures la dictée d'un médecin français en blocs JSON. Tu n'es PAS un assistant médical : tu ne diagnostiques pas, tu ne complètes pas, tu n'inventes rien.

RÈGLES ABSOLUES :
1. Chaque bloc ne contient QUE des informations explicitement présentes dans la dictée. Si le médecin n'a pas dicté d'impression, ne crée pas de bloc impression.
2. Chaque bloc inclut "sourceSpans" : les extraits verbatim de la dictée qui justifient son contenu. Un bloc sans extrait justificatif est interdit.
3. Style : résume et structure en phrases courtes (style télégraphique médical). Ne recopie PAS les phrases dictées mot à mot : condense, supprime les hésitations et répétitions, normalise les unités ("1 mètre 65" → "165 cm", "128 sur 76" → "128/76 mmHg"). Ajout d'information interdit.
4. Ne jamais transformer une observation en diagnostic. "Je retiens des douleurs épigastriques à caractériser" → impression telle quelle. Ne jamais écrire "gastrite probable" si le médecin ne l'a pas dit.
5. Double destination :
   - dest "day" (note du jour datée) : motif, elements (histoire de la maladie/symptômes), examen (constat physique + constantes du jour dont la tension), impression (hypothèses/impression clinique), decision (conduite à tenir, prescriptions, examens demandés, suivi prévu), note (note interne praticien — UNIQUEMENT si le médecin le dit explicitement : "note interne", "note pour moi", "à ne pas mettre dans le compte rendu").
   - dest "dossier" (profil patient durable) : allergies, antecedents (médicaux, chirurgicaux, familiaux), traitements (chroniques/en cours), mesures (poids, taille uniquement), contexte (mode de vie, points d'attention).
   - La tension artérielle va dans "examen" (dest day), jamais dans mesures : c'est une mesure d'un instant.
   - Un traitement PRESCRIT aujourd'hui va dans "decision" (day). Un traitement que le patient PREND déjà va dans "traitements" (dossier).
6. Si la dictée dit explicitement l'absence ("pas d'allergie connue", "aucun traitement") : créer le bloc avec ce contenu — c'est une information.
7. Données machine "structured" (uniquement si explicitement dictées, jamais déduites) :
   - "mesures" : {"poids_kg":68,"taille_cm":165}. NE PAS calculer l'IMC (calcul serveur).
   - "examen" : constantes du jour {"pa_systolique":128,"pa_diastolique":76,"fc_bpm":72,"temperature_c":37.2,"spo2_pct":98,"fr_min":16} — seulement les valeurs dictées.
   - "decision" : {"prescription":"...","examens_demandes":["..."],"orientation":"...","suivi_consignes":"...","prochain_rdv":"AAAA-MM-JJ"} — seulement ce qui est dicté.
   - "antecedents" : {"medicaux":"...","chirurgicaux":"...","familiaux":"..."} — sépare STRICTEMENT les trois catégories, chacune en phrases courtes.
   - "contexte" : {"mode_de_vie":"...","points_attention":"..."} — "mode_de_vie" = profession, tabac, alcool, activité physique, situation familiale ; "points_attention" = UNIQUEMENT les éléments utiles en consultation (risques, alertes, pathologies à surveiller, suivi important). Ne mélange JAMAIS les deux.
8. Sortie : uniquement le JSON {"blocks":[...]}, sans texte autour.

Schéma d'un bloc :
{"field":"motif|elements|examen|impression|decision|note|allergies|antecedents|traitements|mesures|contexte","text":"...","sourceSpans":["extrait verbatim", "..."],"structured":{...}?}
"""


class DossierStateBody(BaseModel):
    allergies_connues: bool = False
    antecedents_connus: bool = False
    traitements_connus: bool = False
    mesures_connues: bool = False


class StructureDictationRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=60000)
    motif_choisi: Optional[str] = Field(default=None, max_length=240)
    motif_patient_verbatim: Optional[str] = Field(default=None, max_length=1000)
    dossier_state: DossierStateBody = Field(default_factory=DossierStateBody)

    @field_validator("transcript")
    @classmethod
    def strip_transcript(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError("transcript requis")
        return cleaned


def _normalize_for_match(value: str) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()


def span_in_transcript(span: str, transcript_normalized: str) -> bool:
    """Vérifie qu'un sourceSpan est bien une sous-chaîne du transcript (tolérance espaces/casse/accents)."""
    needle = _normalize_for_match(span)
    if not needle:
        return False
    return needle in transcript_normalized


def compute_imc(poids_kg: Any, taille_cm: Any) -> Optional[float]:
    try:
        kg = float(str(poids_kg).replace(",", "."))
        cm = float(str(taille_cm).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if kg <= 0 or cm <= 0:
        return None
    m = cm / 100.0
    return round(kg / (m * m), 1)


def _parse_llm_json(raw: str) -> Dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text, flags=re.IGNORECASE)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}


def _clean_structured_mesures(structured: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(structured, dict):
        return None
    out: Dict[str, Any] = {}
    for key in ("poids_kg", "taille_cm"):
        raw = structured.get(key)
        if raw in (None, ""):
            continue
        try:
            out[key] = float(str(raw).replace(",", "."))
        except (TypeError, ValueError):
            continue
    return out or None


# Constantes du jour extraites dans le bloc examen : clé -> (min, max) plausibles.
_EXAMEN_CONSTANTES_BOUNDS = {
    "pa_systolique": (50, 300),
    "pa_diastolique": (20, 200),
    "fc_bpm": (20, 300),
    "temperature_c": (30.0, 45.0),
    "spo2_pct": (50, 100),
    "fr_min": (4, 80),
}


def _clean_structured_examen(structured: Any) -> Optional[Dict[str, Any]]:
    """Constantes du jour dictées : valeurs numériques bornées, rien d'autre."""
    if not isinstance(structured, dict):
        return None
    out: Dict[str, Any] = {}
    for key, (lo, hi) in _EXAMEN_CONSTANTES_BOUNDS.items():
        raw = structured.get(key)
        if raw in (None, ""):
            continue
        try:
            value = float(str(raw).replace(",", "."))
        except (TypeError, ValueError):
            continue
        if not (lo <= value <= hi):
            continue
        out[key] = value if key == "temperature_c" else int(round(value))
    return out or None


def _clean_structured_decision(structured: Any) -> Optional[Dict[str, Any]]:
    """Conduite à tenir détaillée : prescription, examens demandés, orientation, suivi."""
    if not isinstance(structured, dict):
        return None
    out: Dict[str, Any] = {}
    for key, cap in (("prescription", 6000), ("orientation", 4000), ("suivi_consignes", 4000)):
        value = str(structured.get(key) or "").strip()
        if value:
            out[key] = value[:cap]
    examens = structured.get("examens_demandes")
    if isinstance(examens, list):
        cleaned = [str(e).strip()[:120] for e in examens if str(e).strip()]
        if cleaned:
            out["examens_demandes"] = cleaned[:12]
    rdv = str(structured.get("prochain_rdv") or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", rdv):
        out["prochain_rdv"] = rdv
    return out or None


def _clean_structured_text_fields(structured: Any, keys: tuple, cap: int = 2000) -> Optional[Dict[str, Any]]:
    """Sous-champs texte d'un bloc (antecedents, contexte) : chaînes courtes uniquement."""
    if not isinstance(structured, dict):
        return None
    out: Dict[str, Any] = {}
    for key in keys:
        value = str(structured.get(key) or "").strip()
        if value:
            out[key] = value[:cap]
    return out or None


def clean_block_structured(field: str, structured: Any) -> Optional[Dict[str, Any]]:
    """Nettoyage déterministe du `structured` selon le champ (whitelist stricte)."""
    if field == "mesures":
        return _clean_structured_mesures(structured)
    if field == "examen":
        return _clean_structured_examen(structured)
    if field == "decision":
        return _clean_structured_decision(structured)
    if field == "antecedents":
        return _clean_structured_text_fields(structured, ("medicaux", "chirurgicaux", "familiaux"))
    if field == "contexte":
        return _clean_structured_text_fields(structured, ("mode_de_vie", "points_attention"))
    return None


def _make_block(
    field: str,
    text: str,
    source_spans: List[str],
    *,
    provenance: str = "dictee",
    structured: Optional[Dict[str, Any]] = None,
    extra: Optional[str] = None,
    index: int = 0,
) -> Dict[str, Any]:
    meta = FIELD_META[field]
    return {
        "id": f"{field}-{index}",
        "field": field,
        "dest": meta["dest"],
        "label": meta["label"],
        "text": text,
        "sourceSpans": source_spans,
        "provenance": provenance,
        "critical": meta["critical"],
        "danger": meta["danger"],
        "confirmed": not meta["critical"],
        "status": "propose",
        "extra": extra,
        "structured": structured,
    }


def sanitize_blocks(
    raw_blocks: Any,
    transcript: str,
    *,
    motif_choisi: Optional[str] = None,
    motif_patient_verbatim: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Post-traitement déterministe des blocs LLM.

    - rejette tout bloc hors énumération ou sans sourceSpans vérifiables ;
    - force dest/label/criticité/danger depuis FIELD_META ;
    - un seul bloc par field (le premier valide gagne) ;
    - calcule l'IMC si poids + taille présents dans mesures ;
    - le motif choisi par le praticien (chips) remplace tout motif LLM.
    """
    transcript_normalized = _normalize_for_match(transcript)
    by_field: Dict[str, Dict[str, Any]] = {}

    for item in raw_blocks if isinstance(raw_blocks, list) else []:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip().lower()
        if field not in FIELD_META or field in by_field:
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        spans_raw = item.get("sourceSpans")
        spans = [str(s).strip() for s in (spans_raw if isinstance(spans_raw, list) else []) if str(s).strip()]
        valid_spans = [s for s in spans if span_in_transcript(s, transcript_normalized)]
        if not valid_spans:
            logger.warning("dictation block rejected (sourceSpans invalides) field=%s", field)
            continue

        structured = clean_block_structured(field, item.get("structured"))
        extra = None
        if field == "mesures":
            imc = compute_imc((structured or {}).get("poids_kg"), (structured or {}).get("taille_cm"))
            if imc is not None:
                structured = {**(structured or {}), "imc": imc}
                extra = f"IMC calculé : {str(imc).replace('.', ',')}"

        by_field[field] = _make_block(
            field,
            text[:6000],
            valid_spans[:8],
            structured=structured,
            extra=extra,
            index=len(by_field),
        )

    # Motif : le choix du praticien (chips de reformulation) fait foi.
    motif_final = str(motif_choisi or "").strip()
    if motif_final:
        by_field["motif"] = _make_block(
            "motif",
            motif_final[:240],
            [str(motif_patient_verbatim or motif_final).strip()],
            provenance="motif_patient",
            index=len(by_field),
        )

    ordered: List[Dict[str, Any]] = []
    for field in DAY_FIELD_ORDER + DOSSIER_FIELD_ORDER:
        if field in by_field:
            ordered.append(by_field[field])
    for i, block in enumerate(ordered):
        block["id"] = f"{block['field']}-{i}"
    return ordered


def build_degraded_blocks(transcript: str) -> List[Dict[str, Any]]:
    """Mode dégradé : la dictée est conservée telle quelle dans un unique bloc éditable."""
    text = str(transcript or "").strip()
    return [_make_block("elements", text[:12000], [text[:2000]] if text else ["—"], index=0)]


def _structure_model() -> str:
    return (
        str(os.getenv("DICTATION_STRUCTURE_MODEL") or "").strip()
        or str(os.getenv("CONSULTATION_EXTRACTION_MODEL") or "").strip()
        or str(os.getenv("LLM_ASSIST_MODEL") or "").strip()
        or "claude-haiku-4-5-20251001"
    )


def build_structure_user_prompt(req: StructureDictationRequest) -> str:
    parts = [f"DICTÉE DU MÉDECIN :\n{req.transcript}"]
    if req.motif_choisi:
        parts.append(
            f"MOTIF DÉJÀ CHOISI PAR LE PRATICIEN : «{req.motif_choisi}» — ne crée PAS de bloc motif."
        )
    elif req.motif_patient_verbatim:
        parts.append(f"MOTIF DÉCLARÉ PAR LE PATIENT (prise de RDV) : «{req.motif_patient_verbatim}»")
    ds = req.dossier_state
    known = [
        label
        for flag, label in (
            (ds.allergies_connues, "allergies"),
            (ds.antecedents_connus, "antécédents"),
            (ds.traitements_connus, "traitements"),
            (ds.mesures_connues, "mesures"),
        )
        if flag
    ]
    if known:
        parts.append(
            "DOSSIER PATIENT : les champs suivants sont déjà connus — ne crée un bloc dossier "
            f"correspondant QUE si la dictée apporte une information nouvelle : {', '.join(known)}."
        )
    return "\n\n".join(parts)


def structure_dictation(req: StructureDictationRequest) -> Dict[str, Any]:
    """Appel LLM synchrone + post-traitement. Lève en cas d'échec (la route gère le mode dégradé)."""
    anthropic_key = str(os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not anthropic_key:
        raise RuntimeError("ANTHROPIC_API_KEY manquant")

    from anthropic import Anthropic

    client = Anthropic(api_key=anthropic_key, timeout=STRUCTURE_LLM_TIMEOUT_SECONDS, max_retries=0)
    message = client.messages.create(
        model=_structure_model(),
        max_tokens=2400,
        system=STRUCTURE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_structure_user_prompt(req)}],
    )
    raw = "".join(
        getattr(block, "text", "")
        for block in getattr(message, "content", [])
        if getattr(block, "type", None) == "text"
    )
    parsed = _parse_llm_json(raw)
    blocks = sanitize_blocks(
        parsed.get("blocks"),
        req.transcript,
        motif_choisi=req.motif_choisi,
        motif_patient_verbatim=req.motif_patient_verbatim,
    )
    if not blocks:
        raise RuntimeError("structuration vide après validation")
    return {"blocks": blocks, "degraded": False}
