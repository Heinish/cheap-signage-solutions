import { useEffect, useState } from 'react';
import { api } from '../api';
import { toast } from '../toast';
import { IconX } from '../icons';

export default function AddDisplayModal({ rooms, onClose, onClaimed }) {
  const [pending, setPending] = useState([]);
  const [claiming, setClaiming] = useState(null); // device_uid being claimed
  const [name, setName] = useState('');
  const [roomId, setRoomId] = useState('');
  const [manualCode, setManualCode] = useState('');
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    try {
      setPending(await api.pendingPairings());
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, []);

  const startClaim = (code) => {
    setClaiming(code);
    setName('');
    setRoomId('');
  };

  const confirmClaim = async (code) => {
    setBusy(true);
    try {
      await api.claimPairing(code, name, roomId || null);
      toast.success('Display added');
      onClaimed();
      onClose();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={{ width: 460 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="auth-title">Add a display</div>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><IconX width={16} height={16} /></button>
        </div>
        <div className="modal-body">
          <p style={{ fontSize: 12.5, color: 'var(--text-tertiary)' }}>
            Power on a Pi running the CSS agent. It will show a pairing code on its screen and appear below within a few seconds.
          </p>

          {pending.length === 0 && !claiming && (
            <div className="empty-state" style={{ padding: '24px 8px' }}>
              <div className="spinner" style={{ margin: '0 auto 10px', color: 'var(--text-tertiary)' }} />
              <div style={{ fontSize: 12.5 }}>Waiting for a display to request pairing…</div>
            </div>
          )}

          {!claiming && pending.map((p) => (
            <div key={p.device_uid} className="card" style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div className="pairing-code-display" style={{ fontSize: 18, padding: '6px 12px' }}>{p.code}</div>
              <button className="btn btn-primary btn-sm" onClick={() => startClaim(p.code)}>Add this display</button>
            </div>
          ))}

          {claiming && (
            <>
              <div className="pairing-code-display">{claiming}</div>
              <div className="field">
                <label className="field-label">Display name</label>
                <input className="input" autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Lobby — Entrance" />
              </div>
              <div className="field">
                <label className="field-label">Room (optional)</label>
                <select className="input" value={roomId} onChange={(e) => setRoomId(e.target.value)}>
                  <option value="">No room</option>
                  {rooms.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </div>
            </>
          )}

          <hr className="divider" />
          <div className="field">
            <label className="field-label">Or enter a code manually</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input className="input mono" value={manualCode} onChange={(e) => setManualCode(e.target.value.toUpperCase())} placeholder="ABC123" />
              <button className="btn btn-sm" disabled={!manualCode} onClick={() => startClaim(manualCode)}>Use code</button>
            </div>
          </div>
        </div>
        {claiming && (
          <div className="modal-footer">
            <button className="btn btn-ghost" onClick={() => setClaiming(null)}>Back</button>
            <button className="btn btn-primary" disabled={busy || !name.trim()} onClick={() => confirmClaim(claiming)}>
              {busy ? 'Adding…' : 'Confirm'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
