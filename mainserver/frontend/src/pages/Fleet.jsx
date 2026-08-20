import { useMemo, useState } from 'react';
import { useLiveDevices } from '../useLiveDevices';
import DeviceDetail from '../components/DeviceDetail';
import AddDisplayModal from '../components/AddDisplayModal';
import { IconPlus } from '../icons';

function fmtAgo(iso) {
  if (!iso) return 'never';
  const diff = (Date.now() - new Date(iso + 'Z').getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export default function Fleet({ rooms, savedUrls }) {
  const { devices, loading, refresh } = useLiveDevices();
  const [selectedId, setSelectedId] = useState(null);
  const [roomFilter, setRoomFilter] = useState('');
  const [showAdd, setShowAdd] = useState(false);

  const filtered = useMemo(
    () => (roomFilter ? devices.filter((d) => String(d.room_id) === roomFilter) : devices),
    [devices, roomFilter],
  );

  const onlineCount = devices.filter((d) => d.online).length;
  const selected = devices.find((d) => d.id === selectedId);

  return (
    <>
      <div className="stat-row">
        <div className="stat-card">
          <div className="stat-card-label">Total displays</div>
          <div className="stat-card-value">{devices.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card-label">Online</div>
          <div className="stat-card-value online">{onlineCount}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card-label">Offline</div>
          <div className="stat-card-value offline">{devices.length - onlineCount}</div>
        </div>
        <div className="stat-card">
          <div className="stat-card-label">Rooms</div>
          <div className="stat-card-value">{rooms.length}</div>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <select className="input" style={{ width: 200 }} value={roomFilter} onChange={(e) => setRoomFilter(e.target.value)}>
          <option value="">All rooms</option>
          {rooms.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
        <button className="btn btn-primary btn-sm" onClick={() => setShowAdd(true)}>
          <IconPlus width={13} height={13} /> Add display
        </button>
      </div>

      <div className="card">
        {!loading && filtered.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-title">No displays yet</div>
            <div>Power on a Pi running the CSS agent, then click "Add display" to pair it.</div>
          </div>
        ) : (
          <table className="device-table">
            <thead>
              <tr>
                <th>Display</th>
                <th>Room</th>
                <th>Status</th>
                <th>Current URL</th>
                <th>Last seen</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((d) => (
                <tr key={d.id} className={d.id === selectedId ? 'selected' : ''} onClick={() => setSelectedId(d.id)}>
                  <td>
                    <div className="device-name-cell">
                      <span className="device-name">{d.name}</span>
                      <span className="device-uid mono">{d.device_uid.slice(0, 12)}</span>
                    </div>
                  </td>
                  <td>{d.room_name ? <span className="badge">{d.room_name}</span> : <span style={{ color: 'var(--text-tertiary)' }}>—</span>}</td>
                  <td>
                    <span className={`status-pill ${d.online ? 'online' : 'offline'}`}>
                      <span className={`status-dot ${d.online ? 'pulse' : ''}`} />
                      {d.online ? 'Online' : 'Offline'}
                    </span>
                  </td>
                  <td className="mono" style={{ fontSize: 12, color: 'var(--text-secondary)', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {d.current_url || '—'}
                  </td>
                  <td style={{ fontSize: 12.5, color: 'var(--text-tertiary)' }}>{fmtAgo(d.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <DeviceDetail
          device={selected}
          rooms={rooms}
          savedUrls={savedUrls}
          onClose={() => setSelectedId(null)}
          onChanged={refresh}
        />
      )}

      {showAdd && (
        <AddDisplayModal rooms={rooms} onClose={() => setShowAdd(false)} onClaimed={refresh} />
      )}
    </>
  );
}
