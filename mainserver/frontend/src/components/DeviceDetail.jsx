import { useEffect, useState } from 'react';
import { api } from '../api';
import { toast } from '../toast';
import {
  IconX, IconPower, IconRefresh, IconRotate, IconTrash, IconCamera, IconImage,
} from '../icons';

function fmtUptime(seconds) {
  if (!seconds && seconds !== 0) return '—';
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function fmtAgo(iso) {
  if (!iso) return 'never';
  const diff = (Date.now() - new Date(iso + 'Z').getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export default function DeviceDetail({ device, rooms, savedUrls, onClose, onChanged }) {
  const [name, setName] = useState(device.name);
  const [roomId, setRoomId] = useState(device.room_id || '');
  const [url, setUrl] = useState(device.current_url || '');
  const [screenshot, setScreenshot] = useState(null);
  const [loadingShot, setLoadingShot] = useState(false);
  const [busyAction, setBusyAction] = useState(null);
  const [settings, setSettingsState] = useState(null);
  const [playlist, setPlaylist] = useState(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    setName(device.name);
    setRoomId(device.room_id || '');
    setUrl(device.current_url || '');
    setScreenshot(null);
    api.getSettings(device.id).then((r) => setSettingsState(r.settings)).catch(() => {});
    api.getPlaylist(device.id).then(setPlaylist).catch(() => {});
  }, [device.id]);

  const refreshPlaylist = () => api.getPlaylist(device.id).then(setPlaylist).catch(() => {});

  const handleUploadImages = async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = '';
    if (!files.length) return;
    setUploading(true);
    try {
      for (const file of files) {
        await api.uploadPlaylistImage(device.id, file);
      }
      toast.success(`Uploaded ${files.length} image${files.length > 1 ? 's' : ''}`);
      refreshPlaylist();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setUploading(false);
    }
  };

  const savePlaylistSettings = async () => {
    try {
      const result = await api.setPlaylist(device.id, {
        display_time: playlist.display_time,
        fade_time: playlist.fade_time,
        fallback_enabled: playlist.fallback_enabled,
      });
      setPlaylist(result.playlist);
      toast.success('Playlist settings saved');
    } catch (err) {
      toast.error(err.message);
    }
  };

  const run = async (label, fn) => {
    setBusyAction(label);
    try {
      const result = await fn();
      if (result && result.success === false) throw new Error(result.error || 'Command failed');
      toast.success(`${label} sent`);
      onChanged();
    } catch (err) {
      toast.error(err.message || `${label} failed`);
    } finally {
      setBusyAction(null);
    }
  };

  const saveMeta = async () => {
    try {
      await api.updateDevice(device.id, { name, room_id: roomId ? Number(roomId) : 0 });
      toast.success('Saved');
      onChanged();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const takeScreenshot = async () => {
    setLoadingShot(true);
    try {
      const { image_base64 } = await api.screenshot(device.id);
      setScreenshot(`data:image/png;base64,${image_base64}`);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoadingShot(false);
    }
  };

  const remove = async () => {
    if (!confirm(`Remove "${device.name}" from the fleet? The device can re-pair later.`)) return;
    try {
      await api.deleteDevice(device.id);
      toast.success('Device removed');
      onChanged();
      onClose();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const toggleSetting = async (key, val) => {
    try {
      await api.setSettings(device.id, { [key]: { enabled: val } });
      setSettingsState((s) => ({ ...s, [key]: { ...s[key], enabled: val } }));
      toast.success('Setting saved');
    } catch (err) {
      toast.error(err.message);
    }
  };

  const status = device.status || {};

  return (
    <>
      <div className="overlay" onClick={onClose} />
      <div className="detail-panel">
        <div className="detail-header">
          <div style={{ flex: 1, minWidth: 0 }}>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={saveMeta}
              style={{ fontSize: 15, fontWeight: 600, padding: '4px 8px', marginLeft: -8, marginBottom: 8 }}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className={`status-pill ${device.online ? 'online' : 'offline'}`}>
                <span className={`status-dot ${device.online ? 'pulse' : ''}`} />
                {device.online ? 'Online' : 'Offline'}
              </span>
              <span className="badge mono">{device.device_uid.slice(0, 10)}</span>
            </div>
          </div>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><IconX width={16} height={16} /></button>
        </div>

        <div className="detail-body">
          <div>
            <div className="detail-section-label">Room</div>
            <select className="input" value={roomId} onChange={(e) => { setRoomId(e.target.value); }} onBlur={saveMeta}>
              <option value="">No room</option>
              {rooms.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </div>

          <div>
            <div className="detail-section-label">Status</div>
            <div className="kv-grid">
              <div className="kv-item"><span className="kv-label">CPU</span><span className="kv-value">{status.cpu_percent != null ? `${status.cpu_percent}%` : '—'}</span></div>
              <div className="kv-item"><span className="kv-label">Memory</span><span className="kv-value">{status.memory_percent != null ? `${status.memory_percent}%` : '—'}</span></div>
              <div className="kv-item"><span className="kv-label">Temperature</span><span className="kv-value">{status.temperature != null ? `${status.temperature}°C` : '—'}</span></div>
              <div className="kv-item"><span className="kv-label">Uptime</span><span className="kv-value">{fmtUptime(status.uptime)}</span></div>
              <div className="kv-item"><span className="kv-label">IP address</span><span className="kv-value">{status.ip_address || '—'}</span></div>
              <div className="kv-item"><span className="kv-label">Agent version</span><span className="kv-value">{status.version || '—'}</span></div>
              <div className="kv-item"><span className="kv-label">Last seen</span><span className="kv-value">{fmtAgo(device.last_seen)}</span></div>
              <div className="kv-item"><span className="kv-label">Rotation</span><span className="kv-value">{status.screen_rotation ?? 0}°</span></div>
            </div>
          </div>

          <div>
            <div className="detail-section-label">Preview</div>
            <div className="screenshot-frame">
              {screenshot
                ? <img src={screenshot} alt="Display preview" />
                : <span className="screenshot-placeholder">{loadingShot ? 'Capturing…' : 'No preview captured'}</span>}
            </div>
            <button className="btn btn-sm" style={{ marginTop: 8 }} disabled={!device.online || loadingShot} onClick={takeScreenshot}>
              <IconCamera width={13} height={13} /> {loadingShot ? 'Capturing…' : 'Capture screenshot'}
            </button>
          </div>

          <div>
            <div className="detail-section-label">Display URL</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input className="input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
              <button className="btn btn-primary btn-sm" disabled={!device.online || busyAction === 'Set URL'}
                onClick={() => run('Set URL', () => api.setUrl(device.id, url))}>Set</button>
            </div>
            {savedUrls.length > 0 && (
              <select className="input" style={{ marginTop: 8 }} value="" onChange={(e) => e.target.value && setUrl(e.target.value)}>
                <option value="">Saved URLs…</option>
                {savedUrls.map((u) => <option key={u.id} value={u.url}>{u.name}</option>)}
              </select>
            )}
          </div>

          {playlist && (
            <div>
              <div className="detail-section-label">Playlist ({playlist.images.length}/20)</div>
              {playlist.images.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 10 }}>
                  {playlist.images.map((img, i) => (
                    <div key={img} className="badge" style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 8px' }}>
                      <span className="mono" style={{ fontSize: 11 }}>{img}</span>
                      <button className="btn btn-ghost btn-icon" style={{ width: 18, height: 18, padding: 0 }}
                        onClick={async () => { await api.deletePlaylistImage(device.id, i); refreshPlaylist(); }}>
                        <IconX width={11} height={11} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <label className="btn btn-sm" style={{ display: 'inline-flex', cursor: playlist.images.length >= 20 ? 'not-allowed' : 'pointer' }}>
                <IconImage width={13} height={13} /> {uploading ? 'Uploading…' : 'Add images'}
                <input type="file" accept="image/*" multiple hidden disabled={uploading || playlist.images.length >= 20} onChange={handleUploadImages} />
              </label>

              <div className="kv-grid" style={{ marginTop: 12 }}>
                <div className="field">
                  <label className="field-label">Display time (s)</label>
                  <input className="input" type="number" min="1" value={playlist.display_time}
                    onChange={(e) => setPlaylist({ ...playlist, display_time: Number(e.target.value) })} />
                </div>
                <div className="field">
                  <label className="field-label">Fade time (s)</label>
                  <input className="input" type="number" min="0" step="0.5" value={playlist.fade_time}
                    onChange={(e) => setPlaylist({ ...playlist, fade_time: Number(e.target.value) })} />
                </div>
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, marginTop: 10 }}>
                <input type="checkbox" checked={playlist.fallback_enabled}
                  onChange={(e) => setPlaylist({ ...playlist, fallback_enabled: e.target.checked })} />
                Show as network-offline fallback
              </label>
              <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                <button className="btn btn-sm" onClick={savePlaylistSettings}>Save settings</button>
                <button className="btn btn-sm btn-primary" disabled={!device.online || !playlist.images.length}
                  onClick={() => run('Activate playlist', () => api.activatePlaylist(device.id))}>Show slideshow now</button>
              </div>
            </div>
          )}

          <div>
            <div className="detail-section-label">Actions</div>
            <div className="action-grid">
              <button className="btn btn-sm" disabled={!device.online || busyAction === 'Restart browser'}
                onClick={() => run('Restart browser', () => api.restartBrowser(device.id))}>
                <IconRefresh width={13} height={13} /> Restart browser
              </button>
              <button className="btn btn-sm" disabled={!device.online || busyAction === 'Update agent'}
                onClick={() => run('Update agent', () => api.updateAgent(device.id))}>
                <IconRefresh width={13} height={13} /> Update agent
              </button>
              {[0, 90, 180, 270].map((deg) => (
                <button key={deg} className="btn btn-sm" disabled={!device.online || busyAction === `Rotate ${deg}`}
                  onClick={() => run(`Rotate ${deg}`, () => api.rotate(device.id, deg))}>
                  <IconRotate width={13} height={13} /> {deg}°
                </button>
              ))}
              <button className="btn btn-sm btn-danger" disabled={!device.online || busyAction === 'Reboot'}
                onClick={() => confirm('Reboot this display?') && run('Reboot', () => api.reboot(device.id))}>
                <IconPower width={13} height={13} /> Reboot
              </button>
            </div>
          </div>

          {settings && (
            <div>
              <div className="detail-section-label">Schedules</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 13 }}>
                  Auto-update from GitHub
                  <input type="checkbox" checked={settings.autoupdate?.enabled || false}
                    onChange={(e) => toggleSetting('autoupdate', e.target.checked)} />
                </label>
                <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 13 }}>
                  Daily reboot (03:00)
                  <input type="checkbox" checked={settings.daily_reboot?.enabled || false}
                    onChange={(e) => toggleSetting('daily_reboot', e.target.checked)} />
                </label>
              </div>
            </div>
          )}

          <hr className="divider" />
          <button className="btn btn-danger btn-sm" onClick={remove} style={{ alignSelf: 'flex-start' }}>
            <IconTrash width={13} height={13} /> Remove device
          </button>
        </div>
      </div>
    </>
  );
}
