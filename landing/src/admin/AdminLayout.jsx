import { NavLink, Outlet } from "react-router-dom";
import { useAdminAuth } from "./AdminAuthProvider";

export default function AdminLayout() {
  const { logout, me } = useAdminAuth();

  const linkClass = ({ isActive }) =>
    `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium no-underline transition-colors ${
      isActive
        ? "bg-slate-700 text-white"
        : "text-slate-300 hover:bg-slate-700/50 hover:text-white"
    }`;

  return (
    <div className="flex min-h-screen bg-slate-100">
      <aside className="w-64 flex-shrink-0 bg-slate-800 flex flex-col shadow-xl">
        <div className="p-5 border-b border-slate-700">
          <div className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500 text-white font-bold text-sm">
              U
            </span>
            <span className="font-semibold text-white tracking-tight">UWi Admin</span>
          </div>
          <p className="text-slate-400 text-xs mt-1">Pilotage & facturation</p>
        </div>
        <nav className="p-3 flex flex-col gap-0.5 flex-1">
          <span className="px-3 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Navigation
          </span>
          <NavLink to="/admin" end className={linkClass}>
            <span className="text-slate-400">📊</span> Dashboard
          </NavLink>
          <NavLink to="/admin/tenants" className={linkClass}>
            <span className="text-slate-400">👥</span> Clients
          </NavLink>
          <NavLink to="/admin/calls" className={linkClass}>
            <span className="text-slate-400">📞</span> Appels
          </NavLink>
          <NavLink to="/admin/monitoring" className={linkClass}>
            <span className="text-slate-400">📈</span> Monitoring
          </NavLink>
          <NavLink to="/admin/operations" className={linkClass}>
            <span className="text-slate-400">⚙️</span> Operations
          </NavLink>
          <NavLink to="/admin/audit" className={linkClass}>
            <span className="text-slate-400">📋</span> Audit log
          </NavLink>
        </nav>
        <div className="p-3 border-t border-slate-700">
          <span className="px-3 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Compte
          </span>
          <div className="mt-2 px-3 py-2 rounded-lg bg-slate-700/50">
            <div className="text-xs text-slate-400">Connecté</div>
            <div className="text-sm font-medium text-white truncate mt-0.5">
              {me?.email || "—"}
            </div>
          </div>
          <button
            type="button"
            onClick={logout}
            className="mt-2 w-full px-3 py-2 text-sm text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
          >
            Déconnexion
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="p-6 lg:p-8 max-w-7xl mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
