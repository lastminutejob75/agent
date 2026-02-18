import React, { createContext, useContext } from "react";
import { useAdminAuth as useAdminAuthHook } from "./useAdminAuth.js";

const Ctx = createContext(null);

export function AdminAuthProvider({ children }) {
  const auth = useAdminAuthHook();
  return <Ctx.Provider value={auth}>{children}</Ctx.Provider>;
}

export function useAdminAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAdminAuth must be used within AdminAuthProvider");
  return v;
}
