# okDriver — Fleet Command Dashboard

Real-time fleet monitoring platform with live WebSocket event streaming.

---

## Project Structure

```
okdriver/
├── backend/
│   ├── main.py           ← FastAPI app (APIs + WebSocket + auto event generator)
│   ├── requirements.txt  ← Python dependencies
│   └── schema.sql        ← MySQL database schema
└── frontend/
    └── index.html        ← Full dashboard (single-file, no build step needed)
```

---

## Quick Start

### 1. Install Python dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. (Optional) Set up MySQL

If you have MySQL installed:

```bash
mysql -u root -p < schema.sql
```

Then create a `.env` file in `/backend`:

```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=yourpassword
DB_NAME=okdriver
```

> **Skip MySQL entirely?** The app works without it using an in-memory store — perfect for testing.

### 3. Run the backend

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be live at: http://localhost:8000

### 4. Open the frontend

Just open `frontend/index.html` in your browser.

> Tip: Use VS Code's Live Server extension or `python -m http.server 3000` in the frontend folder.

---

## How It Works

```
[Auto Generator]
  Every 2–3 sec, picks a random driver + event type
        ↓
[POST /events]
  Stores event, calculates risk score, severity
        ↓
[WebSocket Broadcast]
  Pushes to all connected browser tabs instantly
        ↓
[Dashboard Updates]
  Charts, feed, metrics, alerts — all update live
```

---

## API Endpoints

| Method | Endpoint       | Description                         |
|--------|----------------|-------------------------------------|
| GET    | `/`            | Health check                        |
| POST   | `/events`      | Ingest a driver event               |
| GET    | `/events`      | List recent events (`?limit=50`)    |
| GET    | `/drivers`     | List all drivers with risk scores   |
| GET    | `/trips`       | List all trips                      |
| GET    | `/metrics`     | Summary: violations, risk, speeds   |
| WS     | `/ws`          | WebSocket live stream               |

### POST /events — Request Body

```json
{
  "driver_id": 1,
  "trip_id": 1,
  "event_type": "speeding",
  "speed": 95.5,
  "latitude": 12.97,
  "longitude": 77.59
}
```

**Event types:** `speeding`, `harsh_braking`, `drowsiness`, `lane_departure`, `tailgating`

---

## Business Logic

| Rule | Behavior |
|------|----------|
| Speed > 80 km/h | Severity = medium, red alert in dashboard |
| Speed > 100 km/h | Severity = high, flashing WARNING on dashcam HUD |
| 3+ violations in trip | Risk score escalates (×12 per violation) |
| 5+ violations | Risk capped at 100, driver flagged High Risk |
| Drowsiness event | Always HIGH severity regardless of speed |

---

## Tech Stack

- **Backend:** Python FastAPI + Uvicorn
- **Database:** MySQL (optional — falls back to in-memory)
- **Real-time:** Native WebSockets (FastAPI built-in)
- **Frontend:** Vanilla HTML/CSS/JS + Chart.js
- **No frameworks, no boilerplates**

---

## Submission Checklist

- [x] GitHub repository
- [x] Architecture diagram (see below)
- [x] API documentation (above)
- [ ] Demo video (record your screen with the dashboard running)

### Architecture Diagram

```
┌──────────────────────────────────────────────────────┐
│                   Browser Client                     │
│  Dashboard (HTML/CSS/JS + Chart.js)                  │
│  WebSocket Client ←──────── REST Fallback Polling    │
└──────────────┬───────────────────────────────────────┘
               │ WebSocket (ws://localhost:8000/ws)
               │ REST (http://localhost:8000/*)
┌──────────────▼───────────────────────────────────────┐
│              FastAPI Backend                         │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ REST Routes │  │  WebSocket   │  │  Auto Event│  │
│  │ /events     │  │  Manager     │  │  Generator │  │
│  │ /metrics    │  │  (broadcast) │  │  (2-3 sec) │  │
│  │ /drivers    │  └──────────────┘  └────────────┘  │
│  └─────────────┘                                     │
│  ┌─────────────────────────────────────────────────┐ │
│  │  In-Memory Store (+ optional MySQL via ORM)     │ │
│  └─────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────┐
│              MySQL Database (optional)               │
│  drivers | trips | events                            │
└──────────────────────────────────────────────────────┘
```
"# OK-Driver-assignment-project" 
