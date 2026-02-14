const fs = require('fs');
const path = require('path');

/**
 * Simple JSON-based database for CSS Dashboard
 * Stores Pis and Rooms in a JSON file
 */
class CSSDatabase {
  constructor(dbPath) {
    // Store as JSON file instead of SQLite
    this.dbPath = dbPath.replace('.db', '.json');
    this.data = { pis: [], rooms: [], urls: [], nextPiId: 1, nextRoomId: 1, nextUrlId: 1 };
    this.load();
  }

  load() {
    try {
      if (fs.existsSync(this.dbPath)) {
        const content = fs.readFileSync(this.dbPath, 'utf8');
        this.data = JSON.parse(content);
      } else {
        this.save(); // Create initial file
      }
    } catch (error) {
      console.error('Failed to load database:', error);
      this.data = { pis: [], rooms: [], nextPiId: 1, nextRoomId: 1 };
    }
  }

  save() {
    try {
      // Ensure directory exists
      const dir = path.dirname(this.dbPath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      fs.writeFileSync(this.dbPath, JSON.stringify(this.data, null, 2), 'utf8');
    } catch (error) {
      console.error('Failed to save database:', error);
    }
  }

  // ========== Pi Operations ==========

  getAllPis() {
    // Join with rooms to add room_name
    return this.data.pis.map(pi => {
      const room = this.data.rooms.find(r => r.id === pi.room_id);
      return { ...pi, room_name: room ? room.name : null };
    });
  }

  addPi(pi) {
    const newPi = {
      id: this.data.nextPiId++,
      name: pi.name,
      ip_address: pi.ip_address,
      room_id: pi.room_id || null,
      last_seen: null,
      created_at: new Date().toISOString()
    };
    this.data.pis.push(newPi);
    this.save();
    return newPi;
  }

  updatePi(id, updates) {
    const pi = this.data.pis.find(p => p.id === id);
    if (!pi) return false;

    if (updates.name !== undefined) pi.name = updates.name;
    if (updates.ip_address !== undefined) pi.ip_address = updates.ip_address;
    if (updates.room_id !== undefined) pi.room_id = updates.room_id;
    if (updates.last_seen !== undefined) pi.last_seen = updates.last_seen;

    this.save();
    return true;
  }

  removePi(id) {
    const index = this.data.pis.findIndex(p => p.id === id);
    if (index === -1) return false;

    this.data.pis.splice(index, 1);
    this.save();
    return true;
  }

  getPiByIp(ip) {
    return this.data.pis.find(p => p.ip_address === ip);
  }

  updateLastSeen(id) {
    const pi = this.data.pis.find(p => p.id === id);
    if (!pi) return false;

    pi.last_seen = new Date().toISOString();
    this.save();
    return true;
  }

  // ========== Room Operations ==========

  getAllRooms() {
    return this.data.rooms;
  }

  addRoom(name) {
    const newRoom = {
      id: this.data.nextRoomId++,
      name,
      created_at: new Date().toISOString()
    };
    this.data.rooms.push(newRoom);
    this.save();
    return newRoom;
  }

  removeRoom(id) {
    const index = this.data.rooms.findIndex(r => r.id === id);
    if (index === -1) return false;

    // Set room_id to null for all pis in this room
    this.data.pis.forEach(pi => {
      if (pi.room_id === id) {
        pi.room_id = null;
      }
    });

    this.data.rooms.splice(index, 1);
    this.save();
    return true;
  }

  assignPiToRoom(piId, roomId) {
    const pi = this.data.pis.find(p => p.id === piId);
    if (!pi) return false;

    pi.room_id = roomId;
    this.save();
    return true;
  }

  getPisByRoom(roomId) {
    return this.data.pis.filter(p => p.room_id === roomId);
  }

  // ========== URL Operations ==========

  getAllUrls() {
    return this.data.urls || [];
  }

  addUrl(url, name) {
    if (!this.data.urls) this.data.urls = [];
    if (!this.data.nextUrlId) this.data.nextUrlId = 1;

    const newUrl = {
      id: this.data.nextUrlId++,
      url,
      name,
      created_at: new Date().toISOString()
    };
    this.data.urls.push(newUrl);
    this.save();
    return newUrl;
  }

  removeUrl(id) {
    if (!this.data.urls) return false;

    const index = this.data.urls.findIndex(u => u.id === id);
    if (index === -1) return false;

    this.data.urls.splice(index, 1);
    this.save();
    return true;
  }

  // ========== Cleanup ==========

  close() {
    this.save();
  }
}

module.exports = CSSDatabase;
