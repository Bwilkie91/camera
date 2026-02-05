"""
Database: persistent storage for proactive surveillance.

Schema:
- detection_events: one row per detection (from parser or live); links to track_id, person_id.
- persons: long-term identity (ReID embeddings, visit stats, typical times).
- tracks: consecutive detections grouped into a "track" (session continuity).
- embeddings: raw ReID vectors for matching; optional link to person_id.

All processing is edge-only; no cloud. Use same DB file as main app optionally,
or a dedicated proactive.db to avoid touching production schema.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

# Default: same directory as this package
_DEFAULT_DB = Path(__file__).resolve().parent.parent / "proactive.db"


def get_db_path(config: dict[str, Any] | None = None) -> Path:
    """Resolve DB path from config or default."""
    if config and config.get("database", {}).get("path"):
        return Path(config["database"]["path"])
    return _DEFAULT_DB


@contextmanager
def get_connection(db_path: Path | None = None, config: dict | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager for a single connection. Enables foreign keys."""
    path = db_path or get_db_path(config)
    conn = sqlite3.connect(str(path), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_schema(conn: sqlite3.Connection) -> None:
    """
    Create tables and indexes for proactive surveillance.
    Idempotent; safe to call on every startup.
    """
    c = conn.cursor()

    # ---- detection_events: one row per AI detection ----
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
            perceived_age_range TEXT,
            hair_color TEXT,
            estimated_height_cm INTEGER,
            build TEXT,
            stress_level TEXT,
            clothing_description TEXT,
            gait_notes TEXT,
            suspicious_behavior TEXT,
            integrity_hash TEXT,
            track_id INTEGER,
            person_id INTEGER,
            embedding_id INTEGER,
            bbox_x REAL,
            bbox_y REAL,
            bbox_w REAL,
            bbox_h REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (track_id) REFERENCES tracks(id),
            FOREIGN KEY (person_id) REFERENCES persons(id),
            FOREIGN KEY (embedding_id) REFERENCES embeddings(id)
        )
    """)

    # ---- tracks: consecutive detections = one "visit" or session ----
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (person_id) REFERENCES persons(id)
        )
    """)

    # ---- persons: persistent identity (ReID + visit history) ----
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

    # ---- embeddings: ReID feature vectors (stored as blob or JSON array) ----
    c.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER,
            event_id INTEGER,
            embedding_blob BLOB,
            embedding_dim INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (person_id) REFERENCES persons(id),
            FOREIGN KEY (event_id) REFERENCES detection_events(id)
        )
    """)

    # Indexes for common queries
    for sql in (
        "CREATE INDEX IF NOT EXISTS idx_detection_events_ts ON detection_events(timestamp_utc)",
        "CREATE INDEX IF NOT EXISTS idx_detection_events_camera_ts ON detection_events(camera_id, timestamp_utc)",
        "CREATE INDEX IF NOT EXISTS idx_detection_events_track ON detection_events(track_id)",
        "CREATE INDEX IF NOT EXISTS idx_detection_events_person ON detection_events(person_id)",
        "CREATE INDEX IF NOT EXISTS idx_detection_events_object ON detection_events(object)",
        "CREATE INDEX IF NOT EXISTS idx_tracks_person ON tracks(person_id)",
        "CREATE INDEX IF NOT EXISTS idx_tracks_start ON tracks(start_utc)",
        "CREATE INDEX IF NOT EXISTS idx_persons_last_seen ON persons(last_seen_utc)",
        "CREATE INDEX IF NOT EXISTS idx_embeddings_person ON embeddings(person_id)",
    ):
        c.execute(sql)

    conn.commit()


def _serialize_value(v: Any) -> Any:
    if v is None:
        return None
    try:
        if hasattr(v, "isoformat"):
            return v.isoformat()
    except Exception:
        pass
    if isinstance(v, float):
        try:
            import math
            if math.isnan(v):
                return None
        except Exception:
            pass
    return v


def row_to_detection_event(row: dict[str, Any]) -> dict[str, Any]:
    """Map parser/DataFrame row to detection_events columns (strip extras)."""
    cols = (
        "timestamp_utc", "local_timestamp", "camera_id", "system_id", "model_version",
        "object", "event", "scene", "crowd_count", "threat_score", "anomaly_score",
        "predicted_intent", "perceived_age_range", "hair_color", "estimated_height_cm",
        "build", "stress_level", "clothing_description", "gait_notes", "suspicious_behavior",
        "integrity_hash", "track_id", "person_id", "embedding_id",
        "bbox_x", "bbox_y", "bbox_w", "bbox_h",
    )
    out = {}
    for k in cols:
        v = _serialize_value(row.get(k))
        if v is not None:
            out[k] = v
    return out


# Column order for detection_events insert (excluding id, created_at)
_DETECTION_EVENT_COLS = (
    "timestamp_utc", "local_timestamp", "camera_id", "system_id", "model_version",
    "object", "event", "scene", "crowd_count", "threat_score", "anomaly_score",
    "predicted_intent", "perceived_age_range", "hair_color", "estimated_height_cm",
    "build", "stress_level", "clothing_description", "gait_notes", "suspicious_behavior",
    "integrity_hash", "track_id", "person_id", "embedding_id",
    "bbox_x", "bbox_y", "bbox_w", "bbox_h",
)


def insert_detection_events(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> list[int]:
    """Insert detection rows; return list of inserted ids."""
    if not rows:
        return []
    cols = list(_DETECTION_EVENT_COLS)
    placeholders = ", ".join("?" * len(cols))
    col_list = ", ".join(cols)
    c = conn.cursor()
    ids = []
    for row in rows:
        d = row_to_detection_event(row)
        vals = [d.get(k) for k in cols]
        if not vals[0]:  # timestamp_utc
            ts = row.get("local_timestamp")
            vals[0] = _serialize_value(ts)
        c.execute(f"INSERT INTO detection_events ({col_list}) VALUES ({placeholders})", vals)
        ids.append(c.lastrowid)
    conn.commit()
    return ids


def create_track(
    conn: sqlite3.Connection,
    session_id: str,
    camera_id: str,
    person_id: int | None,
    start_utc: str,
    end_utc: str,
    detection_count: int,
    dwell_seconds: float | None = None,
    scene: str | None = None,
    threat_score_max: float | None = None,
    anomaly_score_max: float | None = None,
    intent_scores: dict | None = None,
) -> int:
    """Insert a track and return its id."""
    c = conn.cursor()
    c.execute("""
        INSERT INTO tracks (session_id, camera_id, person_id, start_utc, end_utc,
                           detection_count, dwell_seconds, scene, threat_score_max,
                           anomaly_score_max, intent_scores)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, camera_id, person_id, start_utc, end_utc,
        detection_count, dwell_seconds, scene, threat_score_max,
        anomaly_score_max, json.dumps(intent_scores) if intent_scores else None,
    ))
    conn.commit()
    return c.lastrowid


def update_track_event_refs(conn: sqlite3.Connection, event_ids: list[int], track_id: int) -> None:
    """Set track_id on the given detection_events."""
    if not event_ids:
        return
    c = conn.cursor()
    c.execute(
        f"UPDATE detection_events SET track_id = ? WHERE id IN ({','.join('?' * len(event_ids))})",
        [track_id] + event_ids,
    )
    conn.commit()


def insert_or_update_person(
    conn: sqlite3.Connection,
    external_id: str | None,
    first_seen_utc: str,
    last_seen_utc: str,
    visit_count: int = 1,
    total_dwell_seconds: float = 0,
    typical_hours: list[int] | None = None,
    clothing_history: list[str] | None = None,
    height_estimate_cm: int | None = None,
    notes: str | None = None,
) -> int:
    """Insert new person or update last_seen/visit_count; return person id."""
    c = conn.cursor()
    if external_id:
        c.execute(
            "SELECT id, visit_count, total_dwell_seconds FROM persons WHERE external_id = ?",
            (external_id,),
        )
        row = c.fetchone()
        if row:
            pid, vc, dwell = row[0], row[1], row[2]
            c.execute(
                """UPDATE persons SET last_seen_utc = ?, visit_count = ?, total_dwell_seconds = ?,
                   updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                (last_seen_utc, vc + visit_count, dwell + total_dwell_seconds, pid),
            )
            conn.commit()
            return pid
    c.execute("""
        INSERT INTO persons (external_id, first_seen_utc, last_seen_utc, visit_count,
                             total_dwell_seconds, typical_hours, clothing_history, height_estimate_cm, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        external_id,
        first_seen_utc,
        last_seen_utc,
        visit_count,
        total_dwell_seconds,
        json.dumps(typical_hours) if typical_hours else None,
        json.dumps(clothing_history) if clothing_history else None,
        height_estimate_cm,
        notes,
    ))
    conn.commit()
    return c.lastrowid


def insert_embedding(
    conn: sqlite3.Connection,
    embedding_blob: bytes,
    embedding_dim: int,
    person_id: int | None = None,
    event_id: int | None = None,
) -> int:
    """Store one ReID embedding; return embedding id."""
    c = conn.cursor()
    c.execute(
        "INSERT INTO embeddings (person_id, event_id, embedding_blob, embedding_dim) VALUES (?, ?, ?, ?)",
        (person_id, event_id, embedding_blob, embedding_dim),
    )
    conn.commit()
    return c.lastrowid


def get_embeddings_for_person(conn: sqlite3.Connection, person_id: int) -> list[tuple[int, bytes]]:
    """Return (embedding_id, blob) for a person."""
    c = conn.cursor()
    c.execute("SELECT id, embedding_blob FROM embeddings WHERE person_id = ?", (person_id,))
    return [(r[0], r[1]) for r in c.fetchall()]


def get_all_embeddings(conn: sqlite3.Connection) -> list[tuple[int, int | None, bytes, int]]:
    """Return (id, person_id, blob, dim) for all embeddings (for matching)."""
    c = conn.cursor()
    c.execute("SELECT id, person_id, embedding_blob, embedding_dim FROM embeddings")
    return c.fetchall()


def detection_events_dataframe(conn: sqlite3.Connection) -> "pd.DataFrame":
    """Read detection_events into a pandas DataFrame (requires pandas)."""
    import pandas as pd
    return pd.read_sql_query("SELECT * FROM detection_events ORDER BY timestamp_utc", conn)


def build_tracks_from_events(
    conn: sqlite3.Connection,
    gap_seconds: float = 300.0,
    object_filter: str = "person",
) -> int:
    """
    Group detection_events (with track_id IS NULL) into tracks by consecutive time.
    object_filter: only group rows where object = this (e.g. 'person').
    Returns number of tracks created.
    """
    import pandas as pd
    df = pd.read_sql_query(
        "SELECT id, timestamp_utc, camera_id, object, threat_score, anomaly_score, scene "
        "FROM detection_events WHERE track_id IS NULL ORDER BY timestamp_utc",
        conn,
    )
    if df.empty:
        return 0
    df["ts"] = pd.to_datetime(df["timestamp_utc"], errors="coerce")
    df = df.dropna(subset=["ts"])
    if object_filter:
        df = df[df["object"].astype(str).str.lower() == object_filter.lower()]
    if df.empty:
        return 0
    df = df.sort_values("ts")
    gap = pd.Timedelta(seconds=gap_seconds)
    df["gap"] = df["ts"].diff() > gap
    df["session"] = df["gap"].cumsum()
    created = 0
    for _, grp in df.groupby("session"):
        ids = grp["id"].tolist()
        start_utc = grp["ts"].min().isoformat()
        end_utc = grp["ts"].max().isoformat()
        dwell = (grp["ts"].max() - grp["ts"].min()).total_seconds()
        track_id = create_track(
            conn,
            session_id=f"auto_{grp['ts'].min().strftime('%Y%m%d_%H%M%S')}",
            camera_id=grp["camera_id"].iloc[0] or "0",
            person_id=None,
            start_utc=start_utc,
            end_utc=end_utc,
            detection_count=len(grp),
            dwell_seconds=dwell,
            scene=grp["scene"].mode().iloc[0] if grp["scene"].notna().any() else None,
            threat_score_max=float(grp["threat_score"].max()) if grp["threat_score"].notna().any() else None,
            anomaly_score_max=float(grp["anomaly_score"].max()) if grp["anomaly_score"].notna().any() else None,
        )
        update_track_event_refs(conn, ids, track_id)
        created += 1
    return created
