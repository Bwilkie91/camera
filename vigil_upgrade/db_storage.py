"""
Storage layer for upgrade pipeline: detection_events, tracks, persons, embeddings.

Uses same schema as proactive/db.py so you can share proactive.db or use a
dedicated vigil_upgrade.db. All local SQLite; no cloud.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

def _default_db_path() -> Path:
    return Path(__file__).resolve().parent.parent / "vigil_upgrade.db"


@contextmanager
def get_connection(db_path: str | Path | None = None, config: dict[str, Any] | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or (config and config.get("database", {}).get("path")) or _default_db_path()
    path = Path(path) if path else _default_db_path()
    conn = sqlite3.connect(str(path), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_schema(conn: sqlite3.Connection) -> None:
    """Create detection_events, tracks, persons, embeddings if not exist."""
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS detection_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT NOT NULL,
            local_timestamp TEXT,
            camera_id TEXT DEFAULT '0',
            system_id TEXT,
            model_version TEXT,
            object TEXT,
            event TEXT,
            scene TEXT,
            crowd_count INTEGER,
            threat_score REAL,
            anomaly_score REAL,
            predicted_intent TEXT,
            track_id INTEGER,
            person_id INTEGER,
            embedding_id INTEGER,
            bbox_x REAL, bbox_y REAL, bbox_w REAL, bbox_h REAL,
            track_uid INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            camera_id TEXT DEFAULT '0',
            person_id INTEGER,
            start_utc TEXT NOT NULL,
            end_utc TEXT NOT NULL,
            detection_count INTEGER DEFAULT 0,
            dwell_seconds REAL,
            scene TEXT,
            threat_score_max REAL,
            anomaly_score_max REAL,
            intent_scores TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT UNIQUE,
            first_seen_utc TEXT NOT NULL,
            last_seen_utc TEXT NOT NULL,
            visit_count INTEGER DEFAULT 1,
            total_dwell_seconds REAL DEFAULT 0,
            typical_hours TEXT,
            clothing_history TEXT,
            height_estimate_cm INTEGER,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER,
            event_id INTEGER,
            embedding_blob BLOB,
            embedding_dim INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for sql in (
        "CREATE INDEX IF NOT EXISTS idx_detection_events_ts ON detection_events(timestamp_utc)",
        "CREATE INDEX IF NOT EXISTS idx_detection_events_track_uid ON detection_events(track_uid)",
        "CREATE INDEX IF NOT EXISTS idx_detection_events_person ON detection_events(person_id)",
        "CREATE INDEX IF NOT EXISTS idx_tracks_person ON tracks(person_id)",
        "CREATE INDEX IF NOT EXISTS idx_embeddings_person ON embeddings(person_id)",
    ):
        c.execute(sql)
    conn.commit()


def insert_detection(
    conn: sqlite3.Connection,
    timestamp_utc: str,
    camera_id: str = "0",
    object_name: str | None = None,
    event: str | None = None,
    scene: str | None = None,
    crowd_count: int | None = None,
    threat_score: float | None = None,
    anomaly_score: float | None = None,
    predicted_intent: str | None = None,
    track_uid: int | None = None,
    person_id: int | None = None,
    embedding_id: int | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    model_version: str | None = None,
    system_id: str | None = None,
    local_timestamp: str | None = None,
) -> int:
    """Insert one detection_events row; return id."""
    c = conn.cursor()
    bbox = bbox or (None, None, None, None)
    c.execute("""
        INSERT INTO detection_events (
            timestamp_utc, local_timestamp, camera_id, system_id, model_version,
            object, event, scene, crowd_count, threat_score, anomaly_score,
            predicted_intent, track_id, person_id, embedding_id,
            bbox_x, bbox_y, bbox_w, bbox_h, track_uid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)
    """, (
        timestamp_utc, local_timestamp, camera_id, system_id, model_version,
        object_name, event, scene, crowd_count, threat_score, anomaly_score,
        predicted_intent, person_id, embedding_id,
        bbox[0], bbox[1], bbox[2], bbox[3], track_uid,
    ))
    conn.commit()
    return c.lastrowid


def insert_track(
    conn: sqlite3.Connection,
    start_utc: str,
    end_utc: str,
    camera_id: str = "0",
    person_id: int | None = None,
    detection_count: int = 0,
    dwell_seconds: float | None = None,
    scene: str | None = None,
    threat_score_max: float | None = None,
    anomaly_score_max: float | None = None,
    intent_scores: dict | None = None,
    session_id: str | None = None,
) -> int:
    """Insert one track; return id."""
    c = conn.cursor()
    c.execute("""
        INSERT INTO tracks (session_id, camera_id, person_id, start_utc, end_utc,
            detection_count, dwell_seconds, scene, threat_score_max, anomaly_score_max, intent_scores)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (session_id, camera_id, person_id, start_utc, end_utc,
          detection_count, dwell_seconds, scene, threat_score_max, anomaly_score_max,
          json.dumps(intent_scores) if intent_scores else None))
    conn.commit()
    return c.lastrowid


def upsert_person(
    conn: sqlite3.Connection,
    external_id: str | None,
    first_seen_utc: str,
    last_seen_utc: str,
    visit_count_delta: int = 1,
    total_dwell_delta: float = 0,
    typical_hours: list[int] | None = None,
    clothing_history: list[str] | None = None,
    height_estimate_cm: int | None = None,
) -> int:
    """Insert new person or update last_seen/visit_count; return person id."""
    c = conn.cursor()
    if external_id:
        c.execute("SELECT id, visit_count, total_dwell_seconds FROM persons WHERE external_id = ?", (external_id,))
        row = c.fetchone()
        if row:
            pid, vc, dwell = row[0], row[1], row[2]
            c.execute("""
                UPDATE persons SET last_seen_utc = ?, visit_count = ?, total_dwell_seconds = ?,
                    updated_at = CURRENT_TIMESTAMP WHERE id = ?
            """, (last_seen_utc, vc + visit_count_delta, dwell + total_dwell_delta, pid))
            conn.commit()
            return pid
    c.execute("""
        INSERT INTO persons (external_id, first_seen_utc, last_seen_utc, visit_count,
            total_dwell_seconds, typical_hours, clothing_history, height_estimate_cm)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (external_id, first_seen_utc, last_seen_utc, visit_count_delta, total_dwell_delta,
          json.dumps(typical_hours) if typical_hours else None,
          json.dumps(clothing_history) if clothing_history else None, height_estimate_cm))
    conn.commit()
    return c.lastrowid


def store_embedding(conn: sqlite3.Connection, blob: bytes, dim: int, person_id: int | None = None, event_id: int | None = None) -> int:
    """Store ReID embedding; return embedding id."""
    c = conn.cursor()
    c.execute("INSERT INTO embeddings (person_id, event_id, embedding_blob, embedding_dim) VALUES (?, ?, ?, ?)",
              (person_id, event_id, blob, dim))
    conn.commit()
    return c.lastrowid


def get_all_embeddings(conn: sqlite3.Connection) -> list[tuple[int, int | None, bytes, int]]:
    """Return (embedding_id, person_id, blob, dim) for matching."""
    c = conn.cursor()
    c.execute("SELECT id, person_id, embedding_blob, embedding_dim FROM embeddings")
    return c.fetchall()
