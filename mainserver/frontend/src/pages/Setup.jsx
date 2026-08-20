import { useState } from 'react';
import { api } from '../api';

export default function Setup({ onDone }) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    if (password.length < 8) return setError('Password must be at least 8 characters');
    if (password !== confirm) return setError('Passwords do not match');

    setBusy(true);
    try {
      await api.setup(username, password);
      onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="brand-mark" style={{ width: 34, height: 34, fontSize: 14 }}>CS</div>
          <div className="auth-title">Set up the mainserver</div>
          <div className="auth-sub">Create the admin account that manages this fleet of displays.</div>
        </div>
        <form className="auth-form" onSubmit={submit}>
          {error && <div className="auth-error">{error}</div>}
          <div className="field">
            <label className="field-label">Username</label>
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
          </div>
          <div className="field">
            <label className="field-label">Password</label>
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" />
          </div>
          <div className="field">
            <label className="field-label">Confirm password</label>
            <input className="input" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </div>
          <button className="btn btn-primary" type="submit" disabled={busy} style={{ marginTop: 6 }}>
            {busy ? 'Creating…' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  );
}
