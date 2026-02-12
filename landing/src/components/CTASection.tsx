import React from "react";
import { Link } from "react-router-dom";

export default function CTASection() {
  return (
    <section className="section-padding bg-gray-50">
      <div className="container-custom">
        <div className="max-w-4xl mx-auto">
          {/* Card avec gradient bleu */}
          <div className="bg-gradient-to-b from-[#0066CC] via-[#0066CC] to-[#0052A3] rounded-2xl p-8 md:p-12 text-white shadow-hard">
            {/* Titre principal */}
            <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold mb-6 text-center leading-tight">
              Prêt à
              <br />
              transformer
              <br />
              votre
              <br />
              gestion des
              <br />
              appels?
            </h2>

            {/* Texte descriptif */}
            <p className="text-lg md:text-xl mb-10 text-center opacity-95 max-w-2xl mx-auto">
              Rejoignez les 500+
              <br />
              entreprises qui gagnent des
              <br />
              heures chaque semaine avec
              <br />
              <span className="font-semibold">UWi</span>
            </p>

            {/* Boutons CTA */}
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              {/* Bouton 1 : Essayer → onboarding */}
              <Link
                to="/onboarding"
                className="w-full sm:w-auto inline-flex items-center justify-center rounded-xl bg-white text-[#0066CC] px-8 py-4 text-base font-semibold shadow-lg hover:bg-gray-50 transition-all hover:scale-105 active:scale-95"
              >
                Essayer
              </Link>

              {/* Bouton 2 : Parcourir la démo (fond bleu avec bordure blanche) */}
              <a
                href="#demo"
                className="w-full sm:w-auto inline-flex items-center justify-center rounded-xl bg-[#0052A3] text-white border-2 border-white px-8 py-4 text-base font-semibold hover:bg-[#004080] transition-all hover:scale-105 active:scale-95"
              >
                Parcourir la démo
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
