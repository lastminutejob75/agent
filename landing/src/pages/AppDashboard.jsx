import { useNavigate, useOutletContext } from "react-router-dom";

export default function AppDashboard() {
  const navigate = useNavigate();
  const { me, dashboard } = useOutletContext() || {};
  const today = new Date();
  const dayLabel = today.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
  const counters = dashboard?.counters_7d || {};
  const callsTotal = counters.calls_total ?? 0;
  const bookingsConfirmed = counters.bookings_confirmed ?? 0;

  const go = (path) => (e) => {
    if (e && e.preventDefault) e.preventDefault();
    navigate(path);
  };

  return (
    <div className="page">
      {/* Greeting */}
      <div className="greeting fi a1">
        <div className="gr-l">
          <div className="gr-hello">Bonjour, {me?.tenant_name?.split(/\s+/)[0] || "Dr. Martin"} 👋</div>
          <div className="gr-sub">
            {dayLabel} · <strong>UWi</strong> a traité {callsTotal} appel{callsTotal !== 1 ? "s" : ""} sur les 7 derniers jours
            {bookingsConfirmed > 0 && <> · <strong>{bookingsConfirmed} RDV</strong> pris</>}
          </div>
        </div>
        <div className="gr-kpis">
          <div className="gr-kpi"><div className="gr-kpi-val">98%</div><div className="gr-kpi-lbl">Décroché</div></div>
          <div className="gr-kpi"><div className="gr-kpi-val">563</div><div className="gr-kpi-lbl">Min / 800</div></div>
          <div className="gr-kpi"><div className="gr-kpi-val">{bookingsConfirmed || 8}</div><div className="gr-kpi-lbl">RDV auj.</div></div>
        </div>
      </div>

      <div className="layout">
        <div className="lstack">

          {/* Urgences */}
          <div className="card fi a2">
            <div className="ch">
              <div className="ch-left">
                <div className="ch-ico ico-r">🚨</div>
                <div><div className="ch-title">Actions requises</div><div className="ch-sub">Nécessitent votre attention aujourd'hui</div></div>
              </div>
              <a className="ch-lnk" href="/app/actions" onClick={go("/app/actions")}>Tout voir →</a>
            </div>
            <div className="urg-grid">
              <div className="urg-cell" onClick={go("/app/actions")}>
                <div className="urg-bubble ub-r">📞</div>
                <div>
                  <div className="urg-count uc-r">2</div>
                  <div className="urg-lbl">Rappels en attente</div>
                  <div className="urg-cta">Appeler maintenant →</div>
                </div>
              </div>
              <div className="urg-cell" onClick={go("/app/actions")}>
                <div className="urg-bubble ub-o">💊</div>
                <div>
                  <div className="urg-count uc-o">1</div>
                  <div className="urg-lbl">Ordonnance à valider</div>
                  <div className="urg-cta">Valider →</div>
                </div>
              </div>
            </div>
          </div>

          {/* Journal appels */}
          <div className="card fi a3">
            <div className="ch">
              <div className="ch-left">
                <div className="ch-ico ico-t">📋</div>
                <div><div className="ch-title">Appels d'aujourd'hui</div><div className="ch-sub">7 appels · 3 actions requises</div></div>
              </div>
              <a className="ch-lnk" href="/app/appels" onClick={go("/app/appels")}>Historique →</a>
            </div>
            <div className="call-list">
              <div className="call-row call-urg">
                <div className="ctime"><span className="ct-h">10:32</span><span className="ct-d">2'04</span></div>
                <div className="cdot cd-r"></div>
                <div className="cbody">
                  <div className="cname">Pierre Bernard <span className="agent-badge">Sophie</span></div>
                  <div className="ctext">Douleurs thoraciques depuis 2h — orienté urgences</div>
                  <span className="ctag tg-r">⚠ Urgence signalée</span>
                </div>
                <div className="cbtns">
                  <button type="button" className="cbtn btn-call" onClick={go("/app/appels")}>📞 Rappeler</button>
                  <button type="button" className="cbtn btn-view" onClick={go("/app/appels")}>Transcription</button>
                </div>
              </div>
              <div className="call-row">
                <div className="ctime"><span className="ct-h">11:05</span><span className="ct-d">3'17</span></div>
                <div className="cdot cd-o"></div>
                <div className="cbody">
                  <div className="cname">Sophie Leroy <span className="agent-badge">Clara</span></div>
                  <div className="ctext">Renouvellement Metformine 850mg — en attente de validation</div>
                  <span className="ctag tg-o">⏳ À valider</span>
                </div>
                <div className="cbtns">
                  <button type="button" className="cbtn btn-vali" onClick={go("/app/actions")}>Valider</button>
                  <button type="button" className="cbtn btn-view" onClick={go("/app/appels")}>Transcription</button>
                </div>
              </div>
              <div className="call-row">
                <div className="ctime"><span className="ct-h">09:14</span><span className="ct-d">4'02</span></div>
                <div className="cdot cd-g"></div>
                <div className="cbody">
                  <div className="cname">Marie Dupont <span className="agent-badge">Sophie</span></div>
                  <div className="ctext">RDV pris mardi 25/02 à 10h — consultation générale</div>
                  <span className="ctag tg-g">✓ RDV confirmé</span>
                </div>
                <div className="cbtns">
                  <button type="button" className="cbtn btn-call" onClick={go("/app/appels")}>📞 Rappeler</button>
                  <button type="button" className="cbtn btn-view" onClick={go("/app/appels")}>Transcription</button>
                </div>
              </div>
              <div className="call-row">
                <div className="ctime"><span className="ct-h">14:18</span><span className="ct-d">5'31</span></div>
                <div className="cdot cd-g"></div>
                <div className="cbody">
                  <div className="cname">Jacques Moreau <span className="agent-badge">Sophie</span></div>
                  <div className="ctext">Question résultats d'analyses — message transmis, rappel 16h</div>
                  <span className="ctag tg-n">Info transmise</span>
                </div>
                <div className="cbtns">
                  <button type="button" className="cbtn btn-call" onClick={go("/app/appels")}>📞 Rappeler</button>
                  <button type="button" className="cbtn btn-view" onClick={go("/app/appels")}>Transcription</button>
                </div>
              </div>
            </div>
          </div>

        </div>

        {/* Colonne droite */}
        <div className="rstack">

          {/* Agenda */}
          <div className="card fi a4">
            <div className="ch">
              <div className="ch-left"><div className="ch-ico ico-t">📆</div><div><div className="ch-title">Planning du jour</div></div></div>
              <a className="ch-lnk" href="/app/agenda" onClick={go("/app/agenda")}>Agenda →</a>
            </div>
            <div className="week-strip">
              <div className="wday"><span className="wl">L</span><span className="wn">23</span><div className="wpip"></div></div>
              <div className="wday wt"><span className="wl">M</span><span className="wn">24</span><div className="wpip"></div></div>
              <div className="wday"><span className="wl">M</span><span className="wn">25</span><div className="wpip"></div></div>
              <div className="wday"><span className="wl">J</span><span className="wn">26</span></div>
              <div className="wday"><span className="wl">V</span><span className="wn">27</span><div className="wpip"></div></div>
            </div>
            <div className="rdv-list">
              {[
                { h: '09h', nm: 'Claire Fontaine', m: 'Consultation', src: 'UWi', cls: 'rs-uwi' },
                { h: '10h', nm: 'Marie Dupont', m: 'Tension artérielle', src: 'UWi', cls: 'rs-uwi' },
                { h: '11h', nm: 'Henri Blanc', m: 'Renouvellement', src: 'Doctolib', cls: 'rs-doc' },
                { h: '14h', nm: 'Isabelle Roy', m: 'Bilan annuel', src: 'Doctolib', cls: 'rs-doc' },
              ].map((r, i) => (
                <div className="rdv-item" key={i}>
                  <span className="rdv-t">{r.h}</span>
                  <div className="rdv-bar"></div>
                  <div style={{ flex: 1 }}><div className="rdv-nm">{r.nm}</div><div className="rdv-m">{r.m}</div></div>
                  <span className={`rdv-src ${r.cls}`}>{r.src}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Stats */}
          <div className="card fi a5">
            <div className="ch"><div className="ch-left"><div className="ch-ico ico-t">📊</div><div><div className="ch-title">{today.toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}</div></div></div></div>
            <div className="stat-grid">
              <div className="stat-cell"><div className="st-lbl">Appels</div><div className="st-val">142</div><div className="st-sub">+12% vs jan.</div></div>
              <div className="stat-cell"><div className="st-lbl">Décroché</div><div className="st-val st-t">98%</div><div className="st-sub">par UWi</div></div>
              <div className="stat-cell"><div className="st-lbl">RDV pris</div><div className="st-val">{bookingsConfirmed || 87}</div><div className="st-sub">via UWi</div></div>
              <div className="stat-cell"><div className="st-lbl">Urgences</div><div className="st-val">3</div><div className="st-sub">orientées</div></div>
            </div>
          </div>

          {/* Facturation */}
          <div className="card fi a6">
            <div className="ch">
              <div className="ch-left"><div className="ch-ico ico-t">💳</div><div><div className="ch-title">Forfait Growth</div></div></div>
              <a className="ch-lnk" href="/app/facturation" onClick={go("/app/facturation")}>Détail →</a>
            </div>
            <div className="bill-body">
              <div className="bill-top">
                <div>
                  <div className="bill-lbl">Ce mois</div>
                  <div className="bill-val">149 <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--muted)' }}>€</span></div>
                  <div className="bill-sub">Renouvellement le 1er mars</div>
                </div>
                <div className="bill-ok">✓ Dans le forfait</div>
              </div>
              <div>
                <div className="bill-row">
                  <span className="bill-row-lbl">Minutes utilisées</span>
                  <span className="bill-row-val">563 / 800</span>
                </div>
                <div className="bill-bar"><div className="bill-fill" style={{ width: '70%' }}></div></div>
                <div className="bill-hint">237 min restantes · pas de dépassement prévu</div>
              </div>
              <button type="button" className="bill-cta" onClick={go("/app/facturation")}>Voir la facturation complète</button>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
