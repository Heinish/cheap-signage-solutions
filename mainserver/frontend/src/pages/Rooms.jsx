import { useState } from 'react';
import { api } from '../api';
import { toast } from '../toast';
import { IconPlus, IconTrash } from '../icons';

export default function Rooms({ rooms, onChanged }) {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);

  const add = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      await api.createRoom(name.trim());
      setName('');
      onChanged();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    if (!confirm('Delete this room? Displays in it will become unassigned.')) return;
    await api.deleteRoom(id);
    onChanged();
  };

  return (
    <div className="card" style={{ maxWidth: 520 }}>
      <div style={{ padding: '16px 18px', borderBottom: '1px solid var(--border)' }}>
        <form onSubmit={add} style={{ display: 'flex', gap: 8 }}>
          <input className="input" placeholder="New room name" value={name} onChange={(e) => setName(e.target.value)} />
          <button className="btn btn-primary btn-sm" disabled={busy}><IconPlus width={13} height={13} /> Add</button>
        </form>
      </div>
      {rooms.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">No rooms yet</div>
          <div>Group displays by room to filter the fleet view.</div>
        </div>
      ) : (
        rooms.map((r) => (
          <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 18px', borderBottom: '1px solid var(--border)' }}>
            <span style={{ fontSize: 13.5 }}>{r.name}</span>
            <button className="btn btn-ghost btn-icon" onClick={() => remove(r.id)}><IconTrash width={14} height={14} /></button>
          </div>
        ))
      )}
    </div>
  );
}
