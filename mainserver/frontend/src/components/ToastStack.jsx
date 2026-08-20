import { useEffect, useState } from 'react';
import { onToast } from '../toast';

export default function ToastStack() {
  const [toasts, setToasts] = useState([]);

  useEffect(() => onToast((t) => {
    setToasts((prev) => [...prev, t]);
    setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== t.id)), 4000);
  }), []);

  if (!toasts.length) return null;

  return (
    <div className="toast-stack">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.type}`}>{t.message}</div>
      ))}
    </div>
  );
}
