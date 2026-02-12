import { Routes, Route, Navigate } from "react-router-dom";
import UwiLanding from "./components/UwiLanding";
import Onboarding from "./pages/Onboarding";
import Admin from "./pages/Admin";
import AdminTenant from "./pages/AdminTenant";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<UwiLanding />} />
      <Route path="/onboarding" element={<Onboarding />} />
      <Route path="/admin" element={<Admin />} />
      <Route path="/admin/tenants/:tenantId" element={<AdminTenant />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
