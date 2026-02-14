const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('api', {
  // Pi HTTP operations (via main process to bypass CSP)
  getPiStatus: (ip) => ipcRenderer.invoke('pi:getStatus', ip),
  changePiUrl: (ip, url) => ipcRenderer.invoke('pi:changeUrl', ip, url),
  restartPiBrowser: (ip) => ipcRenderer.invoke('pi:restartBrowser', ip),
  rebootPi: (ip) => ipcRenderer.invoke('pi:reboot', ip),
  getScreenshot: (ip) => ipcRenderer.invoke('pi:getScreenshot', ip),
  rotateScreen: (ip, rotation) => ipcRenderer.invoke('pi:rotateScreen', ip, rotation),
  changeNetwork: (ip, config) => ipcRenderer.invoke('pi:changeNetwork', ip, config),

  // System settings operations
  getAutoUpdateSettings: (ip) => ipcRenderer.invoke('pi:getAutoUpdateSettings', ip),
  setAutoUpdateSettings: (ip, enabled) => ipcRenderer.invoke('pi:setAutoUpdateSettings', ip, enabled),
  getRebootSettings: (ip) => ipcRenderer.invoke('pi:getRebootSettings', ip),
  setRebootSettings: (ip, enabled) => ipcRenderer.invoke('pi:setRebootSettings', ip, enabled),
  updatePiNow: (ip) => ipcRenderer.invoke('pi:updateNow', ip),

  // Pi database operations
  getAllPis: () => ipcRenderer.invoke('db:getAllPis'),
  addPi: (pi) => ipcRenderer.invoke('db:addPi', pi),
  updatePi: (id, updates) => ipcRenderer.invoke('db:updatePi', id, updates),
  removePi: (id) => ipcRenderer.invoke('db:removePi', id),

  // Room operations
  getAllRooms: () => ipcRenderer.invoke('db:getAllRooms'),
  addRoom: (name) => ipcRenderer.invoke('db:addRoom', name),
  removeRoom: (id) => ipcRenderer.invoke('db:removeRoom', id),
  assignPiToRoom: (piId, roomId) => ipcRenderer.invoke('db:assignPiToRoom', piId, roomId),

  // URL operations
  getAllUrls: () => ipcRenderer.invoke('db:getAllUrls'),
  addUrl: (url, name) => ipcRenderer.invoke('db:addUrl', url, name),
  removeUrl: (id) => ipcRenderer.invoke('db:removeUrl', id)
});
