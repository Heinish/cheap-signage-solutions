const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('node:path');
const Database = require('./database/db');

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
if (require('electron-squirrel-startup')) {
  app.quit();
}

let mainWindow;
let db;

const createWindow = () => {
  // Create the browser window.
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 600,
    webPreferences: {
      preload: MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY,
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false,
      allowRunningInsecureContent: true,
      experimentalFeatures: true
    },
    title: 'CSS Dashboard - Raspberry Pi Signage Management'
  });

  // and load the index.html of the app.
  mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);

  // Open the DevTools in development
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
};

// Initialize database
function initDatabase() {
  const userDataPath = app.getPath('userData');
  db = new Database(path.join(userDataPath, 'css-dashboard.db'));
  console.log('Database initialized at:', path.join(userDataPath, 'css-dashboard.json'));
}

// HTTP requests to Pi (no CSP in main process)
const axios = require('axios');

async function getPiStatus(ip) {
  try {
    const response = await axios.get(`http://${ip}:5000/api/status`, { timeout: 5000 });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

async function changeUrl(ip, url) {
  try {
    const response = await axios.post(`http://${ip}:5000/api/display/url`, { url }, { timeout: 5000 });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

async function restartBrowser(ip) {
  try {
    const response = await axios.post(`http://${ip}:5000/api/browser/restart`, {}, { timeout: 5000 });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

async function rebootPi(ip) {
  try {
    const response = await axios.post(`http://${ip}:5000/api/system/reboot`, {}, { timeout: 5000 });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

async function getScreenshot(ip) {
  try {
    const response = await axios.get(`http://${ip}:5000/api/display/screenshot`, {
      timeout: 10000,
      responseType: 'arraybuffer'
    });
    return { success: true, data: Buffer.from(response.data).toString('base64') };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

async function rotateScreen(ip, rotation) {
  try {
    const response = await axios.post(`http://${ip}:5000/api/display/rotate`, { rotation }, { timeout: 5000 });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

async function changeNetworkConfig(ip, config) {
  try {
    const response = await axios.post(`http://${ip}:5000/api/network/config`, config, { timeout: 5000 });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

async function getAutoUpdateSettings(ip) {
  try {
    const response = await axios.get(`http://${ip}:5000/api/settings/autoupdate`, { timeout: 5000 });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

async function setAutoUpdateSettings(ip, enabled) {
  try {
    const response = await axios.post(`http://${ip}:5000/api/settings/autoupdate`, { enabled }, { timeout: 5000 });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

async function getRebootSettings(ip) {
  try {
    const response = await axios.get(`http://${ip}:5000/api/settings/reboot`, { timeout: 5000 });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

async function setRebootSettings(ip, enabled) {
  try {
    const response = await axios.post(`http://${ip}:5000/api/settings/reboot`, { enabled }, { timeout: 5000 });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

async function updatePiNow(ip) {
  try {
    const response = await axios.post(`http://${ip}:5000/api/update`, {}, { timeout: 60000 }); // 60s timeout for git pull
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// IPC Handlers for database operations
function setupIpcHandlers() {
  // Pi HTTP operations (done in main process to avoid CSP)
  ipcMain.handle('pi:getStatus', async (event, ip) => {
    return getPiStatus(ip);
  });

  ipcMain.handle('pi:changeUrl', async (event, ip, url) => {
    return changeUrl(ip, url);
  });

  ipcMain.handle('pi:restartBrowser', async (event, ip) => {
    return restartBrowser(ip);
  });

  ipcMain.handle('pi:reboot', async (event, ip) => {
    return rebootPi(ip);
  });

  ipcMain.handle('pi:getScreenshot', async (event, ip) => {
    return getScreenshot(ip);
  });

  ipcMain.handle('pi:rotateScreen', async (event, ip, rotation) => {
    return rotateScreen(ip, rotation);
  });

  ipcMain.handle('pi:changeNetwork', async (event, ip, config) => {
    return changeNetworkConfig(ip, config);
  });

  // System settings operations
  ipcMain.handle('pi:getAutoUpdateSettings', async (event, ip) => {
    return getAutoUpdateSettings(ip);
  });

  ipcMain.handle('pi:setAutoUpdateSettings', async (event, ip, enabled) => {
    return setAutoUpdateSettings(ip, enabled);
  });

  ipcMain.handle('pi:getRebootSettings', async (event, ip) => {
    return getRebootSettings(ip);
  });

  ipcMain.handle('pi:setRebootSettings', async (event, ip, enabled) => {
    return setRebootSettings(ip, enabled);
  });

  ipcMain.handle('pi:updateNow', async (event, ip) => {
    return updatePiNow(ip);
  });

  // Pi database operations
  ipcMain.handle('db:getAllPis', async () => {
    return db.getAllPis();
  });

  ipcMain.handle('db:addPi', async (event, pi) => {
    return db.addPi(pi);
  });

  ipcMain.handle('db:updatePi', async (event, id, updates) => {
    return db.updatePi(id, updates);
  });

  ipcMain.handle('db:removePi', async (event, id) => {
    return db.removePi(id);
  });

  // Room operations
  ipcMain.handle('db:getAllRooms', async () => {
    return db.getAllRooms();
  });

  ipcMain.handle('db:addRoom', async (event, name) => {
    return db.addRoom(name);
  });

  ipcMain.handle('db:removeRoom', async (event, id) => {
    return db.removeRoom(id);
  });

  ipcMain.handle('db:assignPiToRoom', async (event, piId, roomId) => {
    return db.assignPiToRoom(piId, roomId);
  });

  // URL operations
  ipcMain.handle('db:getAllUrls', async () => {
    return db.getAllUrls();
  });

  ipcMain.handle('db:addUrl', async (event, url, name) => {
    return db.addUrl(url, name);
  });

  ipcMain.handle('db:removeUrl', async (event, id) => {
    return db.removeUrl(id);
  });
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
  initDatabase();
  setupIpcHandlers();
  createWindow();

  // On OS X it's common to re-create a window in the app when the
  // dock icon is clicked and there are no other windows open.
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (db) {
    db.close();
  }
});

// In this file you can include the rest of your app's specific main process
// code. You can also put them in separate files and import them here.
