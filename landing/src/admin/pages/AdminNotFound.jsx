import { Link } from "react-router-dom";

export default function AdminNotFound() {
  return (
    <div className="text-center py-12">
      <h1 className="text-xl font-bold text-gray-900">Page introuvable</h1>
      <p className="text-gray-500 mt-2">Cette page admin n'existe pas.</p>
      <Link to="/admin" className="mt-4 inline-block text-indigo-600 hover:underline">
        Retour au dashboard
      </Link>
    </div>
  );
}
