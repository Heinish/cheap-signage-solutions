import { useState } from 'react';
import { api } from '../api';

export default function Login({ onDone }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await api.login(username, password);
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
          <div className="auth-title">Sign in</div>
          <div className="auth-sub">CSS Mainserver — fleet management</div>
        </div>
        <form className="auth-form" onSubmit={submit}>
          {error && <div className="auth-error">{error}</div>}
          <div className="field">
            <label className="field-label">Username</label>
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
          </div>
          <div className="field">
            <label className="field-label">Password</label>
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <button className="btn btn-primary" type="submit" disabled={busy} style={{ marginTop: 6 }}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}
