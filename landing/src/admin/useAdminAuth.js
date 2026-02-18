import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../lib/adminApi.js";

export function useAdminAuth() {
  const [loading, setLoading] = useState(true);
  const [isAuthed, setIsAuthed] = useState(false);
  const [me, setMe] = useState(null);
  const [sessionPersistError, setSessionPersistError] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setSessionPersistError(false);
    try {
      const data = await adminApi.me();
      setMe(data);
      setIsAuthed(true);
    } catch {
      setMe(null);
      setIsAuthed(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = async (email, password) => {
    setSessionPersistError(false);
    try {
      await adminApi.login({ email, password });
    } catch (e) {
      throw e;
    }
    try {
      const data = await adminApi.me();
      setMe(data);
      setIsAuthed(true);
      return { ok: true };
    } catch (e) {
      setMe(null);
      setIsAuthed(false);
      if (e?.status === 401) setSessionPersistError(true);
      return { sessionPersistError: true };
    }
  };

  const logout = async () => {
    try {
      await adminApi.logout();
    } finally {
      setMe(null);
      setIsAuthed(false);
    }
  };

  return { loading, isAuthed, me, login, logout, refresh, sessionPersistError };
}
