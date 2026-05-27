import { useNavigate } from "react-router-dom";

export default function AppFacturation() {
  const navigate = useNavigate();
  const go = (path) => (e) => { if (e && e.preventDefault) e.preventDefault(); navigate(path); };

  return (
    <div className="page">
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '18px', marginBottom: '20px' }}>
        <div className="card" style={{ padding: '22px' }}>
          <div className="st-lbl" style={{ marginBottom: '8px' }}>Forfait actuel</div>
          <div style={{ fontSize: '30px', fontWeight: 800, color: 'var(--navy)', letterSpacing: '-0.03em', marginBottom: '4px' }}>Growth — 149€</div>
          <div style={{ fontSize: '12px', color: 'var(--muted)' }}>800 min incluses · 0,17€/min suppl.</div>
        </div>
        <div className="card" style={{ padding: '22px' }}>
          <div className="st-lbl" style={{ marginBottom: '8px' }}>Facture estimée — Ce mois</div>
          <div style={{ fontSize: '30px', fontWeight: 800, color: 'var(--navy)', letterSpacing: '-0.03em' }}>149 €</div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', marginTop: '10px', fontSize: '12px', fontWeight: 700, background: 'var(--green-lt)', color: '#059669', padding: '5px 12px', borderRadius: '9px' }}>✓ Aucun dépassement prévu</div>
        </div>
      </div>
      <div className="dcard">
        <div className="ch">
          <div className="ch-left">
            <div className="ch-ico ico-t">🧾</div>
            <div><div className="ch-title">Historique des factures</div></div>
          </div>
        </div>
        <div className="bill-body" style={{ borderTop: '1px solid var(--border)' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  <th style={{ textAlign: 'left', padding: '12px 16px', color: 'var(--muted)', fontWeight: 700 }}>Période</th>
                  <th style={{ textAlign: 'right', padding: '12px 16px', color: 'var(--muted)', fontWeight: 700 }}>Montant</th>
                  <th style={{ textAlign: 'left', padding: '12px 16px', color: 'var(--muted)', fontWeight: 700 }}>Statut</th>
                </tr>
              </thead>
              <tbody>
                {['Février 2026', 'Janvier 2026', 'Décembre 2025', 'Novembre 2025', 'Octobre 2025'].map((period, i) => (
                  <tr key={period} style={{ borderBottom: '1px solid var(--border-lt)' }}>
                    <td style={{ padding: '12px 16px', color: 'var(--navy)' }}>{period}</td>
                    <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 700, color: 'var(--navy)' }}>149 €</td>
                    <td style={{ padding: '12px 16px' }}><span style={{ fontSize: '11px', fontWeight: 700, background: 'var(--green-lt)', color: '#059669', padding: '4px 10px', borderRadius: '8px' }}>Payée</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
