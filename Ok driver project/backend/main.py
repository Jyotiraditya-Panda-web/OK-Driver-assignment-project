from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random
from datetime import datetime
from typing import List, Optional
import mysql.connector
from mysql.connector import Error
import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="okDriver Fleet API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    "host":       os.getenv("DB_HOST", "localhost"),
    "port":       int(os.getenv("DB_PORT", 3306)),
    "user":       os.getenv("DB_USER", "root"),
    "password":   os.getenv("DB_PASSWORD", ""),
    "database":   os.getenv("DB_NAME", "okdriver"),
    "autocommit": True,
}

def get_db():
    """Get a fresh DB connection."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"[DB ERROR] {e}")
        raise RuntimeError(f"Cannot connect to database: {e}")

def init_db():
    """Create tables and seed initial data if empty."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            name       VARCHAR(100) NOT NULL,
            vehicle_id VARCHAR(20)  NOT NULL UNIQUE,
            status     ENUM('active','offline') DEFAULT 'active',
            risk_score FLOAT DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            driver_id   INT NOT NULL,
            start_time  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time    TIMESTAMP NULL,
            distance_km FLOAT DEFAULT 0.0,
            status      ENUM('active','completed') DEFAULT 'active',
            FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            driver_id  INT NOT NULL,
            trip_id    INT NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            speed      FLOAT NOT NULL,
            severity   ENUM('low','medium','high') DEFAULT 'low',
            latitude   FLOAT,
            longitude  FLOAT,
            timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE CASCADE,
            FOREIGN KEY (trip_id)   REFERENCES trips(id)   ON DELETE CASCADE
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM drivers")
    if cursor.fetchone()[0] == 0:
        drivers = [
            ("Arjun Sharma",  "KA-01-AB-1234"),
            ("Priya Mehta",   "MH-02-CD-5678"),
            ("Ravi Kumar",    "DL-03-EF-9012"),
            ("Sneha Patel",   "TN-04-GH-3456"),
            ("Vikram Singh",  "UP-05-IJ-7890"),
        ]
        cursor.executemany(
            "INSERT INTO drivers (name, vehicle_id) VALUES (%s, %s)", drivers
        )
        cursor.execute("SELECT id FROM drivers")
        for (driver_id,) in cursor.fetchall():
            cursor.execute("INSERT INTO trips (driver_id) VALUES (%s)", (driver_id,))
        print("[DB] Seeded drivers and trips.")

    cursor.close()
    conn.close()
    print("[DB] Initialized successfully.")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_json(data)
            except:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = ConnectionManager()

class EventIn(BaseModel):
    driver_id:  int
    trip_id:    int
    event_type: str
    speed:      float
    latitude:   Optional[float] = None
    longitude:  Optional[float] = None

def get_severity(event_type: str, speed: float) -> str:
    if event_type == "speeding":
        if speed > 100: return "high"
        if speed > 80:  return "medium"
        return "low"
    if event_type == "drowsiness":    return "high"
    if event_type == "harsh_braking": return "medium"
    return "low"

def calc_risk(violations: int) -> float:
    if violations >= 5: return min(100.0, violations * 15.0)
    if violations >= 3: return violations * 12.0
    return violations * 8.0

@app.get("/")
def root():
    return {"status": "okDriver API running", "version": "1.0.0"}


@app.post("/events")
async def ingest_event(event: EventIn):
    severity = get_severity(event.event_type, event.speed)
    lat = event.latitude  or (12.9716 + random.uniform(-0.5, 0.5))
    lng = event.longitude or (77.5946 + random.uniform(-0.5, 0.5))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Insert event
    cursor.execute("""
        INSERT INTO events (driver_id, trip_id, event_type, speed, severity, latitude, longitude)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (event.driver_id, event.trip_id, event.event_type,
          event.speed, severity, lat, lng))
    event_id = cursor.lastrowid

    # Count violations for this driver+trip
    cursor.execute("""
        SELECT COUNT(*) AS cnt FROM events
        WHERE driver_id = %s AND trip_id = %s
    """, (event.driver_id, event.trip_id))
    vcount = cursor.fetchone()["cnt"]
    risk = calc_risk(vcount)

    # Update driver risk score
    cursor.execute(
        "UPDATE drivers SET risk_score = %s WHERE id = %s",
        (risk, event.driver_id)
    )

    # Get driver name
    cursor.execute("SELECT name FROM drivers WHERE id = %s", (event.driver_id,))
    row = cursor.fetchone()
    driver_name = row["name"] if row else "Unknown"

    cursor.close()
    conn.close()

    ev = {
        "id":              event_id,
        "driver_id":       event.driver_id,
        "driver_name":     driver_name,
        "trip_id":         event.trip_id,
        "event_type":      event.event_type,
        "speed":           event.speed,
        "severity":        severity,
        "latitude":        lat,
        "longitude":       lng,
        "timestamp":       datetime.now().isoformat(),
        "risk_score":      risk,
        "violation_count": vcount,
    }

    await manager.broadcast({
        "type":    "new_event",
        "event":   ev,
        "metrics": get_metrics_data(),
    })

    return {"status": "ok", "event_id": event_id, "severity": severity, "risk_score": risk}


@app.get("/drivers")
def get_drivers():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM drivers ORDER BY risk_score DESC")
    rows = cursor.fetchall()
    cursor.close(); conn.close()
    for r in rows:
        for k, v in r.items():
            if isinstance(v, datetime): r[k] = v.isoformat()
    return rows


@app.get("/trips")
def get_trips():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT t.*, d.name AS driver_name, d.vehicle_id
        FROM trips t JOIN drivers d ON t.driver_id = d.id
        ORDER BY t.start_time DESC
    """)
    rows = cursor.fetchall()
    cursor.close(); conn.close()
    for r in rows:
        for k, v in r.items():
            if isinstance(v, datetime): r[k] = v.isoformat()
    return rows


@app.get("/events")
def get_events(limit: int = 50):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.*, d.name AS driver_name
        FROM events e JOIN drivers d ON e.driver_id = d.id
        ORDER BY e.timestamp DESC LIMIT %s
    """, (limit,))
    rows = cursor.fetchall()
    cursor.close(); conn.close()
    for r in rows:
        for k, v in r.items():
            if isinstance(v, datetime): r[k] = v.isoformat()
    return rows


def get_metrics_data():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS cnt FROM trips")
    total_trips = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) AS cnt FROM drivers WHERE status = 'active'")
    live_drivers = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) AS cnt FROM events")
    violation_count = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) AS cnt FROM drivers WHERE risk_score >= 36")
    high_risk = cursor.fetchone()["cnt"]

    cursor.execute("SELECT AVG(speed) AS avg FROM events WHERE event_type = 'speeding'")
    row = cursor.fetchone()
    avg_speed = round(float(row["avg"] or 0), 1)

    cursor.execute("SELECT COUNT(*) AS cnt FROM events")
    total_events = cursor.fetchone()["cnt"]

    cursor.execute("SELECT event_type, COUNT(*) AS cnt FROM events GROUP BY event_type")
    event_breakdown = {r["event_type"]: r["cnt"] for r in cursor.fetchall()}

    cursor.execute("SELECT name, vehicle_id, risk_score FROM drivers ORDER BY risk_score DESC")
    driver_risks = [
        {"name": r["name"], "vehicle": r["vehicle_id"], "risk": float(r["risk_score"])}
        for r in cursor.fetchall()
    ]

    cursor.close(); conn.close()

    return {
        "total_trips":       total_trips,
        "live_drivers":      live_drivers,
        "violation_count":   violation_count,
        "high_risk_drivers": high_risk,
        "avg_speed":         avg_speed,
        "total_events":      total_events,
        "event_breakdown":   event_breakdown,
        "driver_risks":      driver_risks,
    }


@app.get("/metrics")
def get_metrics():
    return get_metrics_data()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        await ws.send_json({
            "type":    "init",
            "drivers": get_drivers(),
            "events":  get_events(20),
            "metrics": get_metrics_data(),
        })
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


@app.on_event("startup")
async def startup():
    init_db()
    asyncio.create_task(auto_generate_events())


async def auto_generate_events():
    """Pushes a random driver event every 2–3 seconds into MySQL."""
    event_types = ["speeding", "harsh_braking", "drowsiness", "lane_departure", "tailgating"]
    weights     = [0.35,       0.25,            0.15,         0.15,             0.10]

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT d.id AS driver_id, t.id AS trip_id
        FROM drivers d JOIN trips t ON t.driver_id = d.id
        WHERE t.status = 'active'
    """)
    pairs = cursor.fetchall()
    cursor.close(); conn.close()

    await asyncio.sleep(2)
    while True:
        pair       = random.choice(pairs)
        event_type = random.choices(event_types, weights=weights)[0]
        speed      = round(
            random.uniform(30, 130) if event_type == "speeding"
            else random.uniform(20, 90), 1
        )
        ev = EventIn(
            driver_id  = pair["driver_id"],
            trip_id    = pair["trip_id"],
            event_type = event_type,
            speed      = speed,
            latitude   = 12.9716 + random.uniform(-0.5, 0.5),
            longitude  = 77.5946 + random.uniform(-0.5, 0.5),
        )
        await ingest_event(ev)
        await asyncio.sleep(random.uniform(2, 3))