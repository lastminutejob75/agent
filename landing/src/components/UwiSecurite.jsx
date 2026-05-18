import { Link } from "react-router-dom";
import {
  Lock,
  LockKeyhole,
  MapPin,
  ShieldCheck,
  Globe2,
  CircleSlash,
} from "lucide-react";
import "./UwiSecurite.css";
import MedicalHeadsetCrossIcon from "./icons/MedicalHeadsetCrossIcon";

function DragHandle() {
  return (
    <div className="uwi-sec-v2-handle" aria-hidden>
      {Array.from({ length: 9 }).map((_, i) => (
        <span key={i} />
      ))}
    </div>
  );
}

function WaveUnderline() {
  return (
    <svg className="uwi-sec-v2-wave" viewBox="0 0 420 14" fill="none" aria-hidden>
      <path
        d="M4 10c36-8 72-10 108-6 36 4 72 10 108 8 36-2 72-8 108-6 36 2 72 10 88 12"
        stroke="url(#uwiSecWave)"
        strokeWidth="3.5"
        strokeLinecap="round"
      />
      <defs>
        <linearGradient id="uwiSecWave" x1="0" y1="0" x2="420" y2="0" gradientUnits="userSpaceOnUse">
          <stop stopColor="#009ca4" />
          <stop offset="1" stopColor="#38bdf8" />
        </linearGradient>
      </defs>
    </svg>
  );
}

const CARDS = [
  {
    key: "encrypt",
    title: "Données chiffrées",
    desc: "En transit et au repos",
    icon: (
      <div className="uwi-sec-v2-icon-wrap" aria-hidden>
        <LockKeyhole size={34} strokeWidth={1.65} />
      </div>
    ),
  },
  {
    key: "eu",
    title: "Hébergement européen",
    desc: "Les données restent dans un cadre européen",
    icon: (
      <div className="uwi-sec-v2-icon-wrap" aria-hidden>
        <Globe2 size={36} strokeWidth={1.55} />
      </div>
    ),
  },
  {
    key: "access",
    title: "Accès encadré",
    desc: "Accès limité aux personnes et systèmes autorisés",
    icon: (
      <div className="uwi-sec-v2-icon-wrap uwi-sec-v2-icon-wrap--headset" aria-hidden>
        <MedicalHeadsetCrossIcon size={38} className="uwi-sec-v2-med-headset" />
      </div>
    ),
  },
  {
    key: "nore",
    title: "Aucune revente",
    desc: "Les données de vos patients ne sont jamais revendues",
    icon: (
      <div className="uwi-sec-v2-icon-wrap" aria-hidden>
        <CircleSlash size={34} strokeWidth={1.65} />
      </div>
    ),
  },
];

export default function UwiSecurite() {
  return (
    <section id="securite" className="uwi-sec-v2" aria-labelledby="uwi-sec-v2-heading">
      <div className="uwi-sec-v2-inner">
        <div className="uwi-sec-v2-status-wrap">
          <div className="uwi-sec-v2-status">
            <div className="uwi-sec-v2-status-item">
              <Lock size={16} strokeWidth={2.2} aria-hidden />
              <span>Données chiffrées</span>
            </div>
            <span className="uwi-sec-v2-status-dot" aria-hidden>
              ·
            </span>
            <div className="uwi-sec-v2-status-item">
              <MapPin size={16} strokeWidth={2.2} aria-hidden />
              <span>Hébergement européen</span>
            </div>
            <span className="uwi-sec-v2-status-dot" aria-hidden>
              ·
            </span>
            <div className="uwi-sec-v2-status-item">
              <ShieldCheck size={16} strokeWidth={2.2} aria-hidden />
              <span>Aucune revente</span>
            </div>
          </div>
        </div>

        <div className="uwi-sec-v2-eyebrow">
          <span className="uwi-sec-v2-eyebrow-line" aria-hidden />
          Sécurité &amp; Conformité
          <span className="uwi-sec-v2-eyebrow-line" aria-hidden />
        </div>

        <h2 id="uwi-sec-v2-heading" className="uwi-sec-v2-title">
          Vos données patients restent
          <br />
          <span className="uwi-sec-v2-highlight-wrap">
            <span className="uwi-sec-v2-highlight">sous votre contrôle.</span>
            <WaveUnderline />
          </span>
        </h2>

        <p className="uwi-sec-v2-lead">
          Chiffrement des données, hébergement européen et accès strictement encadré : UWi protège les
          informations de votre cabinet et de vos patients.
        </p>

        <div className="uwi-sec-v2-grid">
          {CARDS.map((c) => (
            <article key={c.key} className="uwi-sec-v2-card">
              <DragHandle />
              {c.icon}
              <h3 className="uwi-sec-v2-card-title">{c.title}</h3>
              <p className="uwi-sec-v2-card-desc">{c.desc}</p>
            </article>
          ))}
        </div>

        <div className="uwi-sec-v2-cta-wrap">
          <Link to="/securite" className="uwi-sec-v2-cta">
            Voir notre Trust Center complet
            <span aria-hidden>→</span>
          </Link>
          <span className="uwi-sec-v2-cta-sub">Infrastructure · Confidentialité · Fiabilité</span>
        </div>
      </div>
    </section>
  );
}
