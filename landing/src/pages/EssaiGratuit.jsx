import { useState } from "react";
import { Link } from "react-router-dom";

export default function EssaiGratuit() {
  const [nom, setNom] = useState("");
  const [prenom, setPrenom] = useState("");
  const [email, setEmail] = useState("");
  const [telephone, setTelephone] = useState("");
  const [cabinet, setCabinet] = useState("");
  const [message, setMessage] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const inputClass =
    "w-full rounded-xl border border-slate-600 bg-slate-800/80 px-4 py-2.5 text-white placeholder-slate-500 focus:border-teal-500 focus:ring-2 focus:ring-teal-500/50 focus:outline-none transition-colors";
  const btnClass =
    "w-full rounded-xl bg-gradient-to-r from-teal-500 to-cyan-400 text-slate-950 font-black px-4 py-2.5 hover:shadow-lg hover:shadow-teal-500/30 disabled:opacity-50 transition-all";

  function handleSubmit(e) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    // Pour l'instant : message de confirmation (backend à brancher ensuite)
    setTimeout(() => {
      setSent(true);
      setLoading(false);
    }, 600);
  }

  if (sent) {
    return (
      <div className="flex justify-center">
        <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-800/80 backdrop-blur p-6 sm:p-8 shadow-xl">
          <h1 className="text-2xl font-black text-white">Demande envoyée</h1>
          <p className="mt-2 text-slate-400">
            Merci pour votre intérêt. Nous vous recontacterons sous 48 h pour activer votre essai gratuit d'un mois.
          </p>
          <Link
            to="/"
            className="mt-6 inline-block text-teal-400 hover:text-teal-300 transition-colors"
          >
            Retour à l'accueil
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-center">
      <div className="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-800/80 backdrop-blur p-6 sm:p-8 shadow-xl">
        <h1 className="text-2xl font-black text-white">Essai gratuit 1 mois</h1>
        <p className="mt-1 text-sm text-slate-400">
          Remplissez le formulaire et nous vous recontacterons pour activer votre essai.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="essai-nom" className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Nom</label>
              <input
                id="essai-nom"
                type="text"
                value={nom}
                onChange={(e) => setNom(e.target.value)}
                placeholder="Votre nom"
                required
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="essai-prenom" className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Prénom</label>
              <input
                id="essai-prenom"
                type="text"
                value={prenom}
                onChange={(e) => setPrenom(e.target.value)}
                placeholder="Votre prénom"
                required
                className={inputClass}
              />
            </div>
          </div>

          <div>
            <label htmlFor="essai-email" className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Email</label>
            <input
              id="essai-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="email@cabinet.fr"
              required
              autoComplete="email"
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="essai-tel" className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Téléphone</label>
            <input
              id="essai-tel"
              type="tel"
              value={telephone}
              onChange={(e) => setTelephone(e.target.value)}
              placeholder="06 12 34 56 78"
              required
              autoComplete="tel"
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="essai-cabinet" className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Cabinet / structure</label>
            <input
              id="essai-cabinet"
              type="text"
              value={cabinet}
              onChange={(e) => setCabinet(e.target.value)}
              placeholder="Nom du cabinet ou structure"
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="essai-message" className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Message (optionnel)</label>
            <textarea
              id="essai-message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Vos questions ou besoins particuliers..."
              rows={3}
              className={inputClass + " resize-none"}
            />
          </div>

          {err && <p className="text-red-400 text-sm">{err}</p>}

          <button type="submit" disabled={loading} className={btnClass}>
            {loading ? "Envoi..." : "Demander mon essai gratuit"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          <Link to="/" className="text-teal-400 hover:text-teal-300 transition-colors">
            Retour à l'accueil
          </Link>
        </p>
      </div>
    </div>
  );
}
