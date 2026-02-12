import React from "react";
import { Link } from "react-router-dom";

export default function Footer() {
  return (
    <footer className="border-t bg-white">
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2">
            <Link to="/" className="text-xl font-bold text-slate-900">
              UW<span className="text-blue-600">i</span>
            </Link>
            <span className="text-sm text-slate-500">© UWI {new Date().getFullYear()}</span>
          </div>
          <div className="flex gap-4 text-sm text-slate-500">
            <Link to="/login" className="hover:text-slate-900">Connexion</Link>
            <a href="#" className="hover:text-slate-900">Mentions légales</a>
            <a href="#" className="hover:text-slate-900">Confidentialité</a>
            <a href="#contact" className="hover:text-slate-900">Contact</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
