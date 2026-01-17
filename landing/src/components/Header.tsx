import React from "react";

export default function Header() {
  return (
    <header className="sticky top-0 z-50 border-b bg-white/95 backdrop-blur">
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="text-2xl font-bold text-slate-900">
            UW<span className="text-blue-600">i</span>
          </div>
          <nav className="hidden items-center gap-8 text-sm text-slate-700 md:flex">
            <a className="hover:text-slate-900 font-medium" href="#features">Fonctionnalités</a>
            <a className="hover:text-slate-900 font-medium" href="#roi">ROI</a>
            <a className="hover:text-slate-900 font-medium" href="#pricing">Tarifs</a>
            <a className="hover:text-slate-900 font-medium" href="#contact">Contact</a>
          </nav>
          <a
            href="#contact"
            className="rounded-xl bg-[#0066CC] px-6 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[#0052A3] transition"
          >
            Essai 14 jours
          </a>
        </div>
      </div>
    </header>
  );
}
