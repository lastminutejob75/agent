import { useState } from "react";

const AGENTS = [
  { id: "sophie", name: "Sophie", initial: "S", active: true, voice: "Française — féminine (naturelle)", hours: "Lun–Ven · 08h00 – 20h00", phrase: "Cabinet du Dr. Martin, bonjour, je suis Sophie !", gradient: "var(--grad)" },
  { id: "clara", name: "Clara", initial: "C", active: false, voice: "Française — féminine (douce)", hours: "Sam · 09h00 – 13h00", phrase: "Cabinet du Dr. Martin, bonjour, je suis Clara !", gradient: "linear-gradient(135deg,#F97316,#EF4444)" },
];

const INTEGRATIONS = [
  { id: "doctolib", name: "Doctolib", sub: "Synchro agenda en temps réel", on: true },
  { id: "sms", name: "Rappels SMS patients", sub: "SMS automatique 24h avant chaque RDV", on: true },
  { id: "whatsapp", name: "WhatsApp Business", sub: "Confirmations et infos via WhatsApp", on: false },
  { id: "rapport", name: "Rapport quotidien", sub: "Synthèse des appels envoyée chaque soir par email", on: true },
];

export default function AppConfig() {
  const [toggles, setToggles] = useState(
    Object.fromEntries(INTEGRATIONS.map((i) => [i.id, i.on]))
  );

  const toggle = (id) => {
    setToggles((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="page">
      {/* Mes agents UWi */}
      <div className="dcard" style={{ marginBottom: 0 }}>
        <div className="ch" style={{ padding: '22px 26px 18px' }}>
          <div className="ch-left">
            <div className="ch-ico ico-t">🧑‍💼</div>
            <div>
              <div className="ch-title">Mes agents UWi</div>
              <div className="ch-sub">Forfait Growth — 2 agents actifs sur 2</div>
            </div>
          </div>
          <button type="button" className="save-btn" style={{ padding: '8px 16px', fontSize: 12 }}>+ Ajouter un agent</button>
        </div>
        <div className="agents-grid">
          {AGENTS.map((agent) => (
            <div key={agent.id} className="agent-card">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: '50%',
                      background: agent.gradient,
                      display: 'grid',
                      placeItems: 'center',
                      fontSize: 17,
                      fontWeight: 800,
                      color: '#fff',
                      flexShrink: 0,
                    }}
                  >
                    {agent.initial}
                  </div>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--navy)' }}>{agent.name}</div>
                    <div style={{ fontSize: 11.5, color: agent.active ? 'var(--green)' : 'var(--muted)', fontWeight: 600 }}>
                      ● {agent.active ? 'Active maintenant' : 'Hors horaires'}
                    </div>
                  </div>
                </div>
                <button type="button" className={`tog ${agent.active ? 'tog-on' : ''}`} aria-label={`Activer ${agent.name}`} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div>
                  <label className="flbl">Prénom de l'agent</label>
                  <input className="fin" defaultValue={agent.name} />
                </div>
                <div>
                  <label className="flbl">Voix</label>
                  <select className="fin" style={{ cursor: 'pointer' }} defaultValue={agent.voice}>
                    <option>Française — féminine (naturelle)</option>
                    <option>Française — féminine (douce)</option>
                    <option>Française — masculine (naturelle)</option>
                    <option>Française — neutre</option>
                  </select>
                </div>
                <div>
                  <label className="flbl">Horaires actifs</label>
                  <input className="fin" defaultValue={agent.hours} />
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--muted)', background: 'var(--bg)', padding: '10px 12px', borderRadius: 9, lineHeight: 1.6 }}>
                  Phrase : <em style={{ color: 'var(--body)' }}>"{agent.phrase}"</em>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Configuration générale */}
      <div className="dcard">
        <div className="ch" style={{ padding: '22px 26px 18px' }}>
          <div className="ch-left">
            <div className="ch-ico ico-t">⚙️</div>
            <div>
              <div className="ch-title">Configuration générale</div>
              <div className="ch-sub">Paramètres communs à tous les agents</div>
            </div>
          </div>
        </div>
        <div className="form-wrap" style={{ borderTop: '1px solid var(--border)' }}>
          <div>
            <label className="flbl">Message hors horaires (tous agents inactifs)</label>
            <textarea
              className="fta"
              defaultValue="Le cabinet est fermé. Horaires : lundi-vendredi 8h30–18h30. En cas d'urgence, appelez le 15."
            />
          </div>
          <div>
            <label className="flbl" style={{ marginBottom: 10 }}>Motifs d'appel autorisés</label>
            <div className="mtags">
              <span className="mtag">📅 Prise de RDV <span className="mtag-x">×</span></span>
              <span className="mtag">💊 Renouvellement <span className="mtag-x">×</span></span>
              <span className="mtag">🚨 Urgences <span className="mtag-x">×</span></span>
              <span className="mtag">📋 Résultats <span className="mtag-x">×</span></span>
              <span className="madd">+ Ajouter un motif</span>
            </div>
          </div>
          <div>
            <label className="flbl" style={{ marginBottom: 10 }}>Intégrations & automatisations</label>
            <div className="tog-block">
              {INTEGRATIONS.map((item) => (
                <div key={item.id} className="trow">
                  <div>
                    <div className="trnm">{item.name}</div>
                    <div className="trsub">{item.sub}</div>
                  </div>
                  <button
                    type="button"
                    className={`tog ${toggles[item.id] ? 'tog-on' : ''}`}
                    onClick={() => toggle(item.id)}
                    aria-label={item.name}
                  />
                </div>
              ))}
            </div>
          </div>
          <button type="button" className="save-btn">Enregistrer la configuration</button>
        </div>
      </div>
    </div>
  );
}
