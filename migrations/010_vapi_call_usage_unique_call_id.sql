-- Filet : un vapi_call_id ne peut apparaître qu'une fois (évite doublon si résolution tenant change).
CREATE UNIQUE INDEX IF NOT EXISTS uniq_vapi_call_usage_vapi_call_id
    ON vapi_call_usage (vapi_call_id);
