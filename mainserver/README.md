# CSS Mainserver

Central server for the CSS signage fleet. Each Pi agent connects out to this
server over WebSocket (works from any network — no port-forwarding needed on
the Pi side); the web UI here talks to the same server over REST + WebSocket.

## Run in development

Backend:

```bash
cd mainserver
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # .venv/bin/pip on Linux/Mac
.venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend (separate terminal):

```bash
cd mainserver/frontend
npm install
npm run dev
```

Open http://localhost:5173 — first run walks you through creating the admin
account. The Vite dev server proxies `/api` and `/ws` to `localhost:8000`.

## Run in production

```bash
cd mainserver/frontend && npm install && npm run build   # produces frontend/dist
cd ..
docker compose up -d --build
```

This serves the built frontend directly from FastAPI on port 8000 — no
separate frontend process needed. SQLite data persists in the `css-data`
Docker volume (`CSS_DATA_DIR` env var if running outside Docker).

## Pointing a Pi at this server

On the Pi, set `mainserver_url` in `/etc/css/config.json` to this server's
URL (e.g. `http://192.168.1.50:8000` for LAN, or your domain if deployed
behind a reverse proxy with TLS), then restart the agent:

```bash
sudo systemctl restart css-agent
```

The Pi will show a pairing code on its waiting screen — enter it in the web
UI's "Add display" dialog to claim it.

## Dev helper: fake_agent.py

`tools/fake_agent.py` speaks the same WebSocket protocol as a real Pi agent
without needing hardware — useful for exercising the mainserver UI/API
locally. Not part of the shipped product.
