
CREATE DATABASE IF NOT EXISTS okdriver;
USE okdriver;

CREATE TABLE IF NOT EXISTS drivers (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    vehicle_id  VARCHAR(20) NOT NULL UNIQUE,
    status      ENUM('active', 'offline') DEFAULT 'active',
    risk_score  FLOAT DEFAULT 0.0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trips (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    driver_id    INT NOT NULL,
    start_time   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time     TIMESTAMP NULL,
    distance_km  FLOAT DEFAULT 0.0,
    status       ENUM('active', 'completed') DEFAULT 'active',
    FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS events (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    driver_id   INT NOT NULL,
    trip_id     INT NOT NULL,
    event_type  VARCHAR(50) NOT NULL,
    speed       FLOAT NOT NULL,
    severity    ENUM('low', 'medium', 'high') DEFAULT 'low',
    latitude    FLOAT,
    longitude   FLOAT,
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE CASCADE,
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
);

-- Seed drivers
INSERT INTO drivers (name, vehicle_id) VALUES
    ('Arjun Sharma',  'KA-01-AB-1234'),
    ('Priya Mehta',   'MH-02-CD-5678'),
    ('Ravi Kumar',    'DL-03-EF-9012'),
    ('Sneha Patel',   'TN-04-GH-3456'),
    ('Vikram Singh',  'UP-05-IJ-7890')
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- Seed active trips
INSERT INTO trips (driver_id) SELECT id FROM drivers WHERE status = 'active';
