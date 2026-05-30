"""Résumé IA de fiche patient — cache hash + garde-fous anti-hallucination."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.db import get_conn
from backend.patient_v2_db import ensure_patient_v2_schema, exec_pg, fetch_one_pg, normalize_patient_phone
from backend.services.context_providers import build_context_pack
from backend.tenant_capabilities import RequesterContext

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """\
Tu es l'assistant de synthèse d'UWI. Produis un résumé court et factuel de la situation \
d'un patient pour un praticien qui ouvre sa fiche, lisible en moins de 10 secondes.

RÈGLES ABSOLUES :
1. Tu n'utilises QUE les données du bloc DONNÉES. Tu n'inventes rien.
2. Tu ne recalcules JAMAIS un chiffre ; tu cites les métriques telles quelles.
3. Donnée absente/null -> tu ne la mentionnes pas, tu ne combles pas.
4. Aucun jugement médical, diagnostic ni conseil de soin.
5. score_fiabilite/taux_assiduite null -> "historique insuffisant", jamais un chiffre ni un jugement négatif.
6. Ton neutre, factuel. Pas de superlatifs, pas d'emojis.

FORMAT — JSON strict, aucun texte hors JSON :
{
  "une_ligne": "<=120 car : prénom + assiduité + prochain/dernier RDV",
  "points_attention": ["<flags et signaux factuels>"],
  "contexte_recent": "<2-3 phrases sur derniers échanges + questionnaires admin reçus>",
  "en_attente": ["<rappels promis, questionnaire envoyé non rempli, callbacks — si présents>"]
}
Section sans donnée -> chaîne/tableau vide. Ne remplis jamais "pour faire joli".
"""

SANTE_RULES = """\
DONNÉES DE SANTÉ — règles renforcées :
7. Tu RESTITUES les éléments cliniques fournis (questionnaire médical, antécédents, traitements, \
notes praticien). Tu ne les interprètes pas, aucun diagnostic, aucune suggestion de traitement/examen.
8. Tu ne déduis aucune info de santé non écrite explicitement.
9. Aucun lien de causalité médicale, même évident.
10. Section "rappel_clinique" : reformulation neutre des éléments existants, pour un praticien \
qui connaît déjà le dossier. Aucun conseil.
"""

EMPTY_SECTIONS = {
    "une_ligne": "",
    "points_attention": [],
    "contexte_recent": "",
    "en_attente": [],
}


class SummaryStore:
    """Store résumé (standard ; HDS utilisera un store distinct — stub)."""

    def get(self, tenant_id: int, patient_phone: str) -> Optional[Dict[str, Any]]:
        phone = normalize_patient_phone(patient_phone)
        row = fetch_one_pg(
            """
            SELECT sections_json, inputs_hash, model, is_health, generated_at
            FROM patient_summaries
            WHERE tenant_id = %s AND patient_phone = %s
            """,
            (tenant_id, phone),
        )
        if row:
            return _row_to_summary(row)
        conn = get_conn()
        try:
            cur = conn.execute(
                """
                SELECT sections_json, inputs_hash, model, is_health, generated_at
                FROM patient_summaries WHERE tenant_id = ? AND patient_phone = ?
                """,
                (tenant_id, phone),
            ).fetchone()
            return _row_to_summary(dict(cur)) if cur else None
        finally:
            conn.close()

    def save(
        self,
        tenant_id: int,
        patient_phone: str,
        summary: Dict[str, Any],
        *,
        inputs_hash: str,
        is_health: bool,
    ) -> None:
        phone = normalize_patient_phone(patient_phone)
        sections = summary.get("sections_json") or EMPTY_SECTIONS
        model = summary.get("model") or ""
        payload = json.dumps(sections, ensure_ascii=False)
        conn = get_conn()
        try:
            conn.execute(
                """
                INSERT INTO patient_summaries
                (tenant_id, patient_phone, sections_json, inputs_hash, model, is_health, generated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(tenant_id, patient_phone) DO UPDATE SET
                    sections_json=excluded.sections_json,
                    inputs_hash=excluded.inputs_hash,
                    model=excluded.model,
                    is_health=excluded.is_health,
                    generated_at=datetime('now')
                """,
                (tenant_id, phone, payload, inputs_hash, model, 1 if is_health else 0),
            )
            conn.commit()
        finally:
            conn.close()
        exec_pg(
            """
            INSERT INTO patient_summaries
            (tenant_id, patient_phone, sections_json, inputs_hash, model, is_health, generated_at)
            VALUES (%s, %s, %s::jsonb, %s, %s, %s, now())
            ON CONFLICT (tenant_id, patient_phone) DO UPDATE SET
                sections_json=EXCLUDED.sections_json,
                inputs_hash=EXCLUDED.inputs_hash,
                model=EXCLUDED.model,
                is_health=EXCLUDED.is_health,
                generated_at=now()
            """,
            (tenant_id, phone, payload, inputs_hash, model, is_health),
        )


STANDARD_SUMMARY_STORE = SummaryStore()
HDS_SUMMARY_STORE = SummaryStore()  # TODO HDS : store certifié distinct


def log_health_access(tenant_id: int, patient_phone: str, user_id: str, *, action: str) -> None:
    """STUB traçabilité HDS — journalise en debug pour l'instant."""
    logger.info(
        "health_access tenant=%s phone=%s user=%s action=%s",
        tenant_id,
        normalize_patient_phone(patient_phone)[-4:].rjust(4, "*"),
        user_id,
        action,
    )


def _inputs_hash(pack: dict) -> str:
    blob = json.dumps(pack, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def _row_to_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    sections = row.get("sections_json")
    if isinstance(sections, str):
        try:
            sections = json.loads(sections)
        except json.JSONDecodeError:
            sections = EMPTY_SECTIONS
    return {
        "sections_json": sections or EMPTY_SECTIONS,
        "inputs_hash": row.get("inputs_hash") or "",
        "model": row.get("model") or "",
        "is_health": bool(row.get("is_health")),
        "generated_at": str(row.get("generated_at") or ""),
    }


def _parse_llm_json(raw: str) -> Dict[str, Any]:
    cleaned = raw.strip().replace("```json", "").replace("```", "").strip()
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("summary not an object")
    return {
        "une_ligne": str(data.get("une_ligne") or "")[:200],
        "points_attention": list(data.get("points_attention") or [])[:8],
        "contexte_recent": str(data.get("contexte_recent") or "")[:1200],
        "en_attente": list(data.get("en_attente") or [])[:8],
        **({"rappel_clinique": str(data.get("rappel_clinique") or "")[:1200]} if "rappel_clinique" in data else {}),
    }


def _call_llm(pack: dict, *, contains_health: bool) -> Dict[str, Any]:
    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        return _fallback_summary(pack, contains_health=contains_health, model="fallback")

    system = SUMMARY_SYSTEM_PROMPT + ("\n\n" + SANTE_RULES if contains_health else "")
    model = "claude-sonnet-4-20250514" if contains_health else "claude-haiku-4-5-20251001"
    user_content = "DONNÉES (source de vérité, ne rien inventer) :\n" + json.dumps(
        pack, ensure_ascii=False, indent=2, default=str
    )
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        raw = resp.content[0].text
        sections = _parse_llm_json(raw)
        return {"sections_json": sections, "model": resp.model}
    except Exception:
        logger.warning("patient summary LLM failed", exc_info=True)
        return _fallback_summary(pack, contains_health=contains_health, model="fallback")


def _fallback_summary(pack: dict, *, contains_health: bool, model: str) -> Dict[str, Any]:
    ident = pack.get("identite") or {}
    metrics = ((pack.get("ReceptionProvider") or {}).get("metriques")) or {}
    prenom = (ident.get("prenom") or "Patient").split()[0] if ident.get("prenom") else "Patient"
    taux = metrics.get("taux_assiduite")
    assiduite_txt = "historique insuffisant" if taux is None else f"assiduité {taux}%"
    prochain = metrics.get("prochain_rdv")
    une_ligne = f"{prenom} — {assiduite_txt}"
    if prochain:
        une_ligne += f", prochain RDV {str(prochain)[:10]}"
    flags = ((pack.get("ReceptionProvider") or {}).get("flags")) or []
    pending = ((pack.get("QuestionnaireProvider") or {}).get("questionnaires_en_attente")) or []
    en_attente = []
    if pending:
        en_attente.append("Questionnaire envoyé, en attente de réponse")
    return {
        "sections_json": {
            "une_ligne": une_ligne[:120],
            "points_attention": flags[:5],
            "contexte_recent": "",
            "en_attente": en_attente,
        },
        "model": model,
    }


def _reception_only_summary(db, tenant_id: int, patient_phone: str, tenant_caps: set) -> Dict[str, Any]:
    pack, _ = build_context_pack(db, tenant_id, patient_phone, tenant_caps)
    summary = _fallback_summary(pack, contains_health=False, model="reception_only")
    return {
        **summary,
        "is_health": False,
        "from_cache": False,
        "access_limited": True,
    }


def get_or_generate_summary(
    db,
    tenant_id: int,
    patient_phone: str,
    tenant_caps: set,
    requester: RequesterContext,
    *,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    ensure_patient_v2_schema()
    pack, contains_health = build_context_pack(db, tenant_id, patient_phone, tenant_caps)

    if contains_health and not requester.is_soignant:
        return _reception_only_summary(db, tenant_id, patient_phone, tenant_caps)

    if contains_health:
        log_health_access(tenant_id, patient_phone, requester.id, action="summary_view")
        store = HDS_SUMMARY_STORE
    else:
        store = STANDARD_SUMMARY_STORE

    h = _inputs_hash(pack)
    if not force_refresh:
        cached = store.get(tenant_id, patient_phone)
        if cached and cached.get("inputs_hash") == h:
            return {**cached, "from_cache": True}

    summary = _call_llm(pack, contains_health=contains_health)
    store.save(tenant_id, patient_phone, summary, inputs_hash=h, is_health=contains_health)
    return {
        "sections_json": summary["sections_json"],
        "model": summary.get("model"),
        "is_health": contains_health,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs_hash": h,
        "from_cache": False,
    }


def invalidate_patient_summary(tenant_id: int, patient_phone: str) -> None:
    """Force la régénération au prochain GET (supprime le cache)."""
    phone = normalize_patient_phone(patient_phone)
    conn = get_conn()
    try:
        conn.execute(
            "DELETE FROM patient_summaries WHERE tenant_id = ? AND patient_phone = ?",
            (tenant_id, phone),
        )
        conn.commit()
    finally:
        conn.close()
    exec_pg(
        "DELETE FROM patient_summaries WHERE tenant_id = %s AND patient_phone = %s",
        (tenant_id, phone),
    )
