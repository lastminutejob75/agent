import { useOutletContext } from "react-router-dom";

export default function AppProfil() {
  const { me } = useOutletContext() || {};
  const initials = (me?.tenant_name || "U").split(/\s+/).map((w) => w[0]).join("").toUpperCase().slice(0, 2);

  return (
    <div className="page">
      <div className="dcard">
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px', padding: '28px', borderBottom: '1px solid var(--border)' }}>
          <div className="doc-av" style={{ width: 66, height: 66, fontSize: 22 }}>{initials}</div>
          <div>
            <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--navy)', letterSpacing: '-0.025em' }}>{me?.tenant_name || 'Mon Cabinet'}</div>
            <div style={{ fontSize: '12.5px', color: 'var(--muted)', marginTop: '3px' }}>{me?.contact_email || me?.email || '—'}</div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', marginTop: '8px', fontSize: '11px', fontWeight: 700, background: 'var(--green-lt)', color: '#059669', padding: '4px 11px', borderRadius: '8px' }}>✓ Compte certifié</div>
          </div>
        </div>
        <div className="form-wrap">
          <div>
            <label className="flbl">Nom du cabinet</label>
            <input readOnly className="fin" value={me?.tenant_name || ''} />
          </div>
          <div>
            <label className="flbl">Email</label>
            <input readOnly className="fin" value={me?.contact_email || me?.email || ''} />
          </div>
          <button type="button" className="save-btn" onClick={() => window.location.href = '/app/settings'}>Modifier dans Paramètres</button>
        </div>
      </div>
    </div>
  );
}
