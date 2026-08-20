import { useState } from 'react';
import { api } from '../api';
import { toast } from '../toast';
import { IconPlus, IconTrash } from '../icons';

export default function Urls({ urls, onChanged }) {
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);

  const add = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    setBusy(true);
    try {
      await api.createUrl(name.trim(), url.trim());
      setName('');
      setUrl('');
      onChanged();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    await api.deleteUrl(id);
    onChanged();
  };

  return (
    <div className="card" style={{ maxWidth: 620 }}>
      <div style={{ padding: '16px 18px', borderBottom: '1px solid var(--border)' }}>
        <form onSubmit={add} style={{ display: 'flex', gap: 8 }}>
          <input className="input" style={{ flex: '0 0 160px' }} placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
          <input className="input" placeholder="https://…" value={url} onChange={(e) => setUrl(e.target.value)} />
          <button className="btn btn-primary btn-sm" disabled={busy}><IconPlus width={13} height={13} /> Save</button>
        </form>
      </div>
      {urls.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">No saved URLs</div>
          <div>Save frequently used URLs to quickly assign them to any display.</div>
        </div>
      ) : (
        urls.map((u) => (
          <div key={u.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 18px', borderBottom: '1px solid var(--border)', gap: 12 }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 13.5, fontWeight: 500 }}>{u.name}</div>
              <div className="mono" style={{ fontSize: 11.5, color: 'var(--text-tertiary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.url}</div>
            </div>
            <button className="btn btn-ghost btn-icon" onClick={() => remove(u.id)}><IconTrash width={14} height={14} /></button>
          </div>
        ))
      )}
    </div>
  );
}
