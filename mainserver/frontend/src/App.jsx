import { useEffect, useState } from 'react';
import { api } from './api';
import Setup from './pages/Setup';
import Login from './pages/Login';
import Fleet from './pages/Fleet';
import Rooms from './pages/Rooms';
import Urls from './pages/Urls';
import ToastStack from './components/ToastStack';
import { IconMonitor, IconRooms, IconLink, IconLogout } from './icons';

const PAGES = {
  fleet: { label: 'Displays', title: 'Displays', icon: IconMonitor },
  rooms: { label: 'Rooms', title: 'Rooms', icon: IconRooms },
  urls: { label: 'Saved URLs', title: 'Saved URLs', icon: IconLink },
};

export default function App() {
  const [authState, setAuthState] = useState('loading'); // loading | needs_setup | needs_login | ready
  const [username, setUsername] = useState('');
  const [page, setPage] = useState('fleet');
  const [rooms, setRooms] = useState([]);
  const [urls, setUrls] = useState([]);

  const bootstrap = async () => {
    try {
      const status = await api.authStatus();
      if (status.needs_setup) return setAuthState('needs_setup');
      const me = await api.me();
      setUsername(me.username);
      setAuthState('ready');
    } catch {
      setAuthState('needs_login');
    }
  };

  useEffect(() => { bootstrap(); }, []);

  const loadData = async () => {
    const [r, u] = await Promise.all([api.listRooms(), api.listUrls()]);
    setRooms(r);
    setUrls(u);
  };

  useEffect(() => {
    if (authState === 'ready') loadData();
  }, [authState]);

  if (authState === 'loading') return null;
  if (authState === 'needs_setup') return <Setup onDone={bootstrap} />;
  if (authState === 'needs_login') return <Login onDone={bootstrap} />;

  const logout = async () => {
    await api.logout();
    setAuthState('needs_login');
  };

  const current = PAGES[page];

  return (
    <div className="app-shell">
      <ToastStack />
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">CS</div>
          <div>
            <div className="brand-name">CSS Mainserver</div>
            <div className="brand-sub">fleet control</div>
          </div>
        </div>

        <div className="nav-group">
          <div className="nav-label">Fleet</div>
          {Object.entries(PAGES).map(([key, cfg]) => {
            const Icon = cfg.icon;
            return (
              <button key={key} className={`nav-item ${page === key ? 'active' : ''}`} onClick={() => setPage(key)}>
                <Icon className="nav-icon" />
                {cfg.label}
              </button>
            );
          })}
        </div>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="sidebar-user-avatar">{username.slice(0, 2).toUpperCase()}</div>
            <div className="sidebar-user-name">{username}</div>
          </div>
          <button className="btn btn-ghost btn-icon" onClick={logout} title="Sign out">
            <IconLogout width={15} height={15} />
          </button>
        </div>
      </aside>

      <div className="main">
        <div className="topbar">
          <div>
            <div className="page-title">{current.title}</div>
          </div>
        </div>
        <div className="content">
          {page === 'fleet' && <Fleet rooms={rooms} savedUrls={urls} />}
          {page === 'rooms' && <Rooms rooms={rooms} onChanged={loadData} />}
          {page === 'urls' && <Urls urls={urls} onChanged={loadData} />}
        </div>
      </div>
    </div>
  );
}
