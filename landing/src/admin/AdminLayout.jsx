import { NavLink, Outlet } from "react-router-dom";
import { useAdminAuth } from "./AdminAuthProvider";

export default function AdminLayout() {
  const { logout, me } = useAdminAuth();

  const linkClass = ({ isActive }) =>
    `block px-3 py-2.5 rounded-lg text-sm font-medium no-underline ${
      isActive ? "bg-indigo-50 text-indigo-700" : "text-gray-700 hover:bg-gray-100"
    }`;

  return (
    <div className="grid grid-cols-[260px_1fr] min-h-screen bg-gray-50">
      <aside className="bg-white border-r border-gray-200 p-4 flex flex-col">
        <div className="font-bold text-gray-900 mb-4">UWi Admin</div>
        <nav className="flex flex-col gap-1">
          <NavLink to="/admin" end className={linkClass}>
            Dashboard
          </NavLink>
          <NavLink to="/admin/tenants" className={linkClass}>
            Clients
          </NavLink>
          <NavLink to="/admin/monitoring" className={linkClass}>
            Monitoring
          </NavLink>
          <NavLink to="/admin/audit" className={linkClass}>
            Audit log
          </NavLink>
        </nav>
        <div className="mt-auto pt-4 border-t border-gray-200">
          <div className="text-xs text-gray-500">Connecté</div>
          <div className="text-sm font-medium text-gray-800 truncate">{me?.email || "—"}</div>
          <button
            type="button"
            onClick={logout}
            className="mt-2 w-full px-3 py-2 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Déconnexion
          </button>
        </div>
      </aside>
      <main className="p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
