import React from "react";

export default function CTASection() {
  return (
    <section className="section-padding bg-gradient-to-br from-[#0066CC] to-[#0052A3] text-white">
      <div className="container-custom">
        <div className="text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">Prêt à transformer votre accueil client ?</h2>
          <p className="text-xl mb-8 opacity-90">Essayez UWI gratuitement pendant 14 jours</p>
          <a href="#contact" className="inline-flex items-center justify-center gap-2 rounded-xl bg-white text-[#0066CC] px-8 py-4 text-lg font-semibold shadow-lg hover:bg-gray-50 transition">
            Démarrer maintenant
          </a>
        </div>
      </div>
    </section>
  );
}
