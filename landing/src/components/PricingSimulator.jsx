// Simulateur tarifaire : slider minutes → plan recommandé + CTA vers inscription avec plan pré-sélectionné
import { useState, useMemo } from "react";
import { Link } from "react-router-dom";

const PLANS = [
  { name: "Starter", base: 99, included: 400, overRate: 0.19 },
  { name: "Growth", base: 149, included: 800, overRate: 0.17 },
  { name: "Pro", base: 199, included: 1200, overRate: 0.15 },
];

function cost(plan, minutes) {
  const over = Math.max(0, minutes - plan.included);
  return plan.base + over * plan.overRate;
}

function getRecommended(minutes) {
  let best = PLANS[0];
  let bestCost = cost(best, minutes);
  for (const p of PLANS) {
    const c = cost(p, minutes);
    if (c < bestCost) {
      bestCost = c;
      best = p;
    }
  }
  const over = Math.max(0, minutes - best.included);
  const overCost = over * best.overRate;
  return {
    ...best,
    total: Math.round(bestCost * 100) / 100,
    overMinutes: over,
    overCost: Math.round(overCost * 100) / 100,
  };
}

const MIN_MINUTES = 100;
const MAX_MINUTES = 1500;
const STEP = 50;

export default function PricingSimulator() {
  const [minutes, setMinutes] = useState(400);
  const r = useMemo(() => getRecommended(minutes), [minutes]);

  return (
    <div className="simulator">
      <p className="sim-title">Estimez votre forfait</p>
      <p className="sim-subtitle">Déplacez le curseur selon vos besoins en minutes par mois.</p>
      <label className="sim-label" htmlFor="sim-slider">
        Minutes / mois
      </label>
      <input
        id="sim-slider"
        type="range"
        className="sim-slider"
        min={MIN_MINUTES}
        max={MAX_MINUTES}
        step={STEP}
        value={minutes}
        onChange={(e) => setMinutes(Number(e.target.value))}
      />
      <div className="sim-ticks">
        <span>100</span>
        <span>500</span>
        <span>800</span>
        <span>1200</span>
        <span><small>1500</small></span>
      </div>
      <div className="sim-result">
        <p className="sim-plan-rec">
          Forfait recommandé : <strong>{r.name}</strong>
        </p>
        <div className="sim-cost-row">
          <div className="sim-cost-item">
            <span className="sim-cost-label">Forfait</span>
            <span className="sim-cost-val">{r.base} €</span>
          </div>
          {r.overMinutes > 0 && (
            <>
              <span className="sim-cost-plus">+</span>
              <div className="sim-cost-item">
                <span className="sim-cost-label">Au-delà</span>
                <span className="sim-cost-val">{r.overCost} €</span>
              </div>
            </>
          )}
          <span className="sim-cost-plus">=</span>
          <div className="sim-cost-item sim-cost-total">
            <span className="sim-cost-label">Total</span>
            <span className="sim-cost-val">{r.total} €</span>
          </div>
        </div>
        <p className="sim-guarantee">✓ Bascule automatique au meilleur prix appliquée</p>
        <Link
          to={`/creer-assistante?new=1&plan=${r.name.toLowerCase()}`}
          className="sim-cta-btn"
        >
          Démarrer avec {r.name} — Essai gratuit 1 mois →
        </Link>
      </div>
    </div>
  );
}
