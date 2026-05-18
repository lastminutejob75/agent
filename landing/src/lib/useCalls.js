import { useCallback, useEffect, useState } from "react";
import {
  addCallNote,
  createPatientFromCall,
  getCallById,
  getCalls,
  markCallAsHandled,
} from "./callsService.js";

export function useCalls({ days = 30 } = {}) {
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedCallId, setSelectedCallId] = useState("");
  const [selectedCall, setSelectedCall] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const list = await getCalls({ days, limit: 50 });
      setCalls(list);
    } catch (e) {
      setError(e?.message || "Impossible de charger les appels.");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const selectCall = useCallback(async (id) => {
    if (!id) {
      setSelectedCallId("");
      setSelectedCall(null);
      return;
    }
    setSelectedCallId(id);
    setDetailLoading(true);
    try {
      const detail = await getCallById(id);
      setSelectedCall(detail);
    } catch {
      setSelectedCall(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedCallId("");
    setSelectedCall(null);
  }, []);

  const handleMarkAsHandled = useCallback(
    async (id) => {
      await markCallAsHandled(id);
      await refresh();
      if (selectedCallId === id) await selectCall(id);
    },
    [refresh, selectedCallId, selectCall],
  );

  const handleCreatePatientFromCall = useCallback(
    async (id, payload) => {
      const result = await createPatientFromCall(id, payload);
      await refresh();
      if (selectedCallId === id) await selectCall(id);
      return result;
    },
    [refresh, selectedCallId, selectCall],
  );

  const handleAddCallNote = useCallback(
    async (id, note) => {
      await addCallNote(id, note);
      if (selectedCallId === id) await selectCall(id);
    },
    [selectedCallId, selectCall],
  );

  return {
    calls,
    loading,
    error,
    selectedCallId,
    selectedCall,
    detailLoading,
    refresh,
    selectCall,
    clearSelection,
    markAsHandled: handleMarkAsHandled,
    createPatientFromCall: handleCreatePatientFromCall,
    addCallNote: handleAddCallNote,
  };
}
