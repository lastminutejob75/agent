import { useCallback, useEffect, useState } from "react";
import { adminApi } from "../lib/adminApi.js";
import { setAdminToken } from "../lib/api.js";

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

  /** Connexion avec le token API (ADMIN_API_TOKEN). Contourne email/mot de passe. */
  const loginWithToken = async (token) => {
    const t = (token || "").trim();
    if (!t) throw new Error("Token requis");
    setAdminToken(t);
    try {
      const data = await adminApi.me();
      setMe(data);
      setIsAuthed(true);
      return { ok: true };
    } catch (e) {
      setAdminToken("");
      throw e;
    }
  };

  const logout = async () => {
    try {
      await adminApi.logout();
    } finally {
      setAdminToken("");
      setMe(null);
      setIsAuthed(false);
    }
  };

  return { loading, isAuthed, me, login, loginWithToken, logout, refresh, sessionPersistError };
}
