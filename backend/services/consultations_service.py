"""
UWI — Consultations : modèles Pydantic + service context pack
==============================================================
Colle au payload émis par FicheConsultationUWI.jsx (zéro mapping front<->back).

  POST  /api/tenant/patients/{patient_id}/consultations   -> create_consultation()
  POST  /api/tenant/consultations/summary                 -> draft, renvoie {resume, contexte}
  GET   /api/tenant/patients/{patient_id}/context-pack    -> get_context_pack()

Pattern psycopg + pool, cohérent avec le reste du backend.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# 1. Modèles Pydantic (miroir exact du payload front)
# =============================================================================

class Constantes(BaseModel):
    fc_bpm:         Optional[int]   = Field(None, ge=20,  le=300)
    pa_systolique:  Optional[int]   = Field(None, ge=50,  le=300)
    pa_diastolique: Optional[int]   = Field(None, ge=20,  le=200)
    temperature_c:  Optional[float] = Field(None, ge=30,  le=45)
    spo2_pct:       Optional[int]   = Field(None, ge=50,  le=100)
    fr_min:         Optional[int]   = Field(None, ge=4,   le=80)
    poids_kg:       Optional[float] = Field(None, ge=1,   le=400)
    taille_cm:      Optional[int]   = Field(None, ge=30,  le=250)
    imc:            Optional[float] = None

    @property
    def is_empty(self) -> bool:
        return all(
            getattr(self, f) is None
            for f in self.model_fields
        )


class ExamenClinique(BaseModel):
    etat_general:    str = ""
    examen_physique: str = ""
    constantes:      Constantes = Constantes()


class Suivi(BaseModel):
    prochain_rdv: Optional[date] = None
    consignes:    str = ""


class ConduiteATenir(BaseModel):
    examens_complementaires: list[str] = []
    prescription:            str = ""
    orientation:             str = ""
    suivi:                   Suivi = Suivi()

    @field_validator("examens_complementaires")
    @classmethod
    def clean_tags(cls, v: list[str]) -> list[str]:
        # dédoublonne en préservant l'ordre, vire les vides
        seen, out = set(), []
        for tag in (t.strip() for t in v):
            if tag and tag.lower() not in seen:
                seen.add(tag.lower())
                out.append(tag)
        return out


class IaUwi(BaseModel):
    resume_consultation:        str = ""
    contexte_patient:           str = ""
    validated_by_practitioner:  bool = False


class ConsultationCreate(BaseModel):
    """Payload de POST /patients/{id}/consultations — émis tel quel par la fiche."""
    patient_id:          str
    date:                date
    mode_consultation:   Literal["rapide", "complete"] = "rapide"
    motif:               str = Field(min_length=1)
    anamnese:            str = ""
    examen_clinique:     ExamenClinique = ExamenClinique()
    impression_clinique: str = Field(min_length=1)
    cim10:               Optional[str] = None
    conduite_a_tenir:    ConduiteATenir = ConduiteATenir()
    ia_uwi:              Optional[IaUwi] = None     # None => génération async backend
    note_praticien:      Optional[str] = None


class ConsultationOut(BaseModel):
    id:                str
    patient_id:        str
    date_consultation: date
    motif:             str
    impression_clinique: str
    ia_status:         str
    created_at:        datetime


# =============================================================================
# 2. Création — consultations + consultation_vitals en une transaction
# =============================================================================

INSERT_CONSULTATION = """
INSERT INTO consultations (
    tenant_id, patient_id, date_consultation, mode_consultation,
    motif, anamnese, etat_general, examen_physique,
    impression_clinique, cim10,
    examens_demandes, prescription, orientation,
    suivi_prochain_rdv, suivi_consignes,
    note_praticien,
    ia_resume, ia_contexte_patient, ia_status, ia_validated_at,
    raw_payload
) VALUES (
    %(tenant_id)s, %(patient_id)s, %(date)s, %(mode)s,
    %(motif)s, %(anamnese)s, %(etat_general)s, %(examen_physique)s,
    %(impression)s, %(cim10)s,
    %(examens)s, %(prescription)s, %(orientation)s,
    %(prochain_rdv)s, %(consignes)s,
    %(note_praticien)s,
    %(ia_resume)s, %(ia_contexte)s, %(ia_status)s, %(ia_validated_at)s,
    %(raw_payload)s
)
RETURNING id, created_at;
"""

INSERT_VITALS = """
INSERT INTO consultation_vitals (
    consultation_id, tenant_id, patient_id, measured_at,
    fc_bpm, pa_systolique, pa_diastolique, temperature_c,
    spo2_pct, fr_min, poids_kg, taille_cm, imc, source
) VALUES (
    %(consultation_id)s, %(tenant_id)s, %(patient_id)s, %(measured_at)s,
    %(fc_bpm)s, %(pa_systolique)s, %(pa_diastolique)s, %(temperature_c)s,
    %(spo2_pct)s, %(fr_min)s, %(poids_kg)s, %(taille_cm)s, %(imc)s, 'praticien'
);
"""


def create_consultation(pool, tenant_id: str, body: ConsultationCreate) -> ConsultationOut:
    """
    Insère la consultation + ses constantes (si non vides) en une transaction.
    ia_status :
      - 'validated' si le praticien a généré/édité la synthèse côté front
      - 'pending'   sinon -> le worker async la génère puis UPDATE ia_resume,
                    ia_contexte_patient, ia_status='generated', ia_generated_at
    """
    import json

    ia = body.ia_uwi
    params = {
        "tenant_id":       tenant_id,
        "patient_id":      body.patient_id,
        "date":            body.date,
        "mode":            body.mode_consultation,
        "motif":           body.motif.strip(),
        "anamnese":        body.anamnese.strip() or None,
        "etat_general":    body.examen_clinique.etat_general.strip() or None,
        "examen_physique": body.examen_clinique.examen_physique.strip() or None,
        "impression":      body.impression_clinique.strip(),
        "cim10":           body.cim10,
        "examens":         body.conduite_a_tenir.examens_complementaires,
        "prescription":    body.conduite_a_tenir.prescription.strip() or None,
        "orientation":     body.conduite_a_tenir.orientation.strip() or None,
        "prochain_rdv":    body.conduite_a_tenir.suivi.prochain_rdv,
        "consignes":       body.conduite_a_tenir.suivi.consignes.strip() or None,
        "note_praticien":  (body.note_praticien or "").strip() or None,
        "ia_resume":       ia.resume_consultation if ia else None,
        "ia_contexte":     ia.contexte_patient if ia else None,
        "ia_status":       "validated" if (ia and ia.validated_by_practitioner) else "pending",
        "ia_validated_at": datetime.utcnow() if (ia and ia.validated_by_practitioner) else None,
        "raw_payload":     json.dumps(body.model_dump(mode="json")),
    }

    with pool.connection() as conn:
        # RLS : positionner le tenant sur la connexion (pattern existant)
        conn.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant_id,))

        with conn.transaction():
            row = conn.execute(INSERT_CONSULTATION, params).fetchone()
            consultation_id, created_at = row[0], row[1]

            constantes = body.examen_clinique.constantes
            if not constantes.is_empty:
                conn.execute(INSERT_VITALS, {
                    "consultation_id": consultation_id,
                    "tenant_id":       tenant_id,
                    "patient_id":      body.patient_id,
                    "measured_at":     body.date,
                    **constantes.model_dump(),
                })

    return ConsultationOut(
        id=str(consultation_id),
        patient_id=body.patient_id,
        date_consultation=body.date,
        motif=params["motif"],
        impression_clinique=params["impression"],
        ia_status=params["ia_status"],
        created_at=created_at,
    )


# =============================================================================
# 3. Context pack — métriques SQL en UNE round-trip
# =============================================================================
# Les "dernières constantes" sont générées par boucle Python -> pas de
# copier-coller SQL par constante, et ajout d'une constante = 1 ligne ici.

_VITAL_COLS = [
    "fc_bpm", "pa_systolique", "pa_diastolique",
    "temperature_c", "spo2_pct", "poids_kg", "imc",
]

_LAST_VITALS_SQL = " || ".join(
    f"""COALESCE((
        SELECT jsonb_build_object('{col}',
               jsonb_build_object('valeur', {col}, 'date', measured_at))
        FROM consultation_vitals
        WHERE patient_id = %(patient_id)s AND {col} IS NOT NULL
        ORDER BY measured_at DESC LIMIT 1
    ), '{{}}'::jsonb)"""
    for col in _VITAL_COLS
)

CONTEXT_PACK_SQL = f"""
SELECT jsonb_build_object(

  'dernieres_constantes', {_LAST_VITALS_SQL},

  'poids_tendance_6m', (
      SELECT jsonb_build_object(
          'debut_kg', MIN(poids_kg) FILTER (WHERE rn_asc  = 1),
          'fin_kg',   MIN(poids_kg) FILTER (WHERE rn_desc = 1),
          'delta_kg', ROUND(MIN(poids_kg) FILTER (WHERE rn_desc = 1)
                          - MIN(poids_kg) FILTER (WHERE rn_asc  = 1), 1),
          'nb_pesees', COUNT(*))
      FROM (
          SELECT poids_kg,
                 ROW_NUMBER() OVER (ORDER BY measured_at ASC)  AS rn_asc,
                 ROW_NUMBER() OVER (ORDER BY measured_at DESC) AS rn_desc
          FROM consultation_vitals
          WHERE patient_id = %(patient_id)s
            AND poids_kg IS NOT NULL
            AND measured_at >= CURRENT_DATE - INTERVAL '6 months'
      ) p
  ),

  'pa_moyenne_3_dernieres', (
      SELECT jsonb_build_object('pas', ROUND(AVG(pa_systolique)),
                                'pad', ROUND(AVG(pa_diastolique)),
                                'nb',  COUNT(*))
      FROM (SELECT pa_systolique, pa_diastolique
            FROM consultation_vitals
            WHERE patient_id = %(patient_id)s AND pa_systolique IS NOT NULL
            ORDER BY measured_at DESC LIMIT 3) t
  ),

  'frequentation', (
      SELECT jsonb_build_object(
          'nb_12_mois',      COUNT(*),
          'derniere_visite', MAX(date_consultation),
          'jours_depuis',    CURRENT_DATE - MAX(date_consultation))
      FROM consultations
      WHERE patient_id = %(patient_id)s
        AND date_consultation >= CURRENT_DATE - INTERVAL '12 months'
  ),

  'dernieres_consultations', (
      SELECT COALESCE(jsonb_agg(jsonb_build_object(
                 'date',       date_consultation,
                 'motif',      motif,
                 'impression', impression_clinique,
                 'resume_ia',  ia_resume)
             ORDER BY date_consultation DESC), '[]'::jsonb)
      FROM (SELECT date_consultation, motif, impression_clinique, ia_resume
            FROM consultations
            WHERE patient_id = %(patient_id)s
            ORDER BY date_consultation DESC LIMIT 5) c
  ),

  'examens_recents', (
      SELECT COALESCE(jsonb_agg(DISTINCT ex), '[]'::jsonb)
      FROM consultations, unnest(examens_demandes) AS ex
      WHERE patient_id = %(patient_id)s
        AND date_consultation >= CURRENT_DATE - INTERVAL '3 months'
  )

) AS context_pack;
"""
# NB : note_praticien est volontairement ABSENT du context pack -> jamais
# exposé à Clara ni aux communications patient.


def get_context_pack(pool, tenant_id: str, patient_id: str) -> dict:
    """Métriques SQL du context pack en une round-trip. À fusionner ensuite
    avec le bloc dossier patient + le résumé LLM dans le service appelant."""
    with pool.connection() as conn:
        conn.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant_id,))
        row = conn.execute(CONTEXT_PACK_SQL, {"patient_id": patient_id}).fetchone()
    return row[0] if row else {}
