-- Lie les uploads patient à une demande questionnaire avant soumission.

ALTER TABLE patient_documents_v2
    ADD COLUMN IF NOT EXISTS questionnaire_request_id UUID REFERENCES questionnaire_requests(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_patient_documents_v2_request
    ON patient_documents_v2(questionnaire_request_id);
