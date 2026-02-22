// Layout des pages auth (login, forgot, reset, callback) — même header/footer que la landing
import { Link, Outlet } from "react-router-dom";
import { Stethoscope } from "lucide-react";

export default function AuthLayout() {
  return (
    <div className="min-h-screen bg-slate-950">
      <header className="fixed top-0 left-0 right-0 bg-slate-950/90 backdrop-blur-2xl border-b border-slate-800 z-50">
        <nav className="max-w-7xl mx-auto px-6 py-6 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-4">
            <div className="relative">
              <div className="absolute inset-0 bg-teal-500 rounded-xl blur-lg opacity-50" />
              <div className="relative w-12 h-12 bg-gradient-to-br from-teal-500 to-cyan-400 rounded-xl flex items-center justify-center shadow-2xl transform -rotate-3">
                <Stethoscope className="w-7 h-7 text-slate-950 font-bold" strokeWidth={2.5} />
              </div>
            </div>
            <div>
              <div className="text-2xl font-black text-white tracking-tight">UWi Medical</div>
              <div className="text-[10px] text-teal-400 font-semibold tracking-widest uppercase">IA Secrétariat</div>
            </div>
          </Link>
          <div className="flex items-center gap-3">
            <Link
              to="/login"
              className="hidden sm:block text-slate-300 hover:text-white px-5 py-2.5 rounded-lg text-sm font-bold transition-colors"
            >
              Connexion
            </Link>
            <Link
              to="/decouverte"
              className="relative group bg-gradient-to-r from-teal-500 to-cyan-400 text-slate-950 px-7 py-3 rounded-lg text-sm font-black hover:shadow-2xl hover:shadow-teal-500/50 hover:scale-105 transition-all duration-200 inline-flex"
            >
              <span className="relative">Démarrer →</span>
            </Link>
          </div>
        </nav>
      </header>

      <main className="pt-28 pb-16 min-h-screen">
        <div className="max-w-7xl mx-auto px-6">
          <Outlet />
        </div>
      </main>

      <footer className="bg-slate-950 border-t border-slate-800 text-slate-400 py-8">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm">
          <p className="text-slate-500 font-medium">&copy; {new Date().getFullYear()} UWi Medical</p>
          <div className="flex gap-6">
            <Link to="/" className="text-slate-500 hover:text-teal-400 transition-colors font-semibold">
              Accueil
            </Link>
            <Link to="/login" className="text-slate-500 hover:text-teal-400 transition-colors font-semibold">
              Connexion
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
