#!/usr/bin/env python3
"""
Proactive Surveillance — main entry point.

Orchestrates: parse log → DB → tracks → ReID (optional) → predictor → deterrence → viz.
Edge-only; no cloud. Mac/GPU friendly (MPS when available).

Usage:
  python -m proactive.main
  python -m proactive.main --log path/to/raw_log.txt
  SURVEILLANCE_LOG_PATH=/path/to/log.txt python -m proactive.main
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure project root on path for parser script
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Proactive surveillance pipeline")
    parser.add_argument("--log", type=str, default=os.environ.get("SURVEILLANCE_LOG_PATH", ""), help="Path to raw log file")
    parser.add_argument("--config", type=str, default="", help="Path to config.yaml")
    parser.add_argument("--no-viz", action="store_true", help="Skip plots")
    parser.add_argument("--no-alerts", action="store_true", help="Do not run deterrence")
    args = parser.parse_args()

    from proactive.config_loader import load_config
    from proactive.db import get_connection, get_db_path, init_schema, insert_detection_events, build_tracks_from_events
    from proactive.predictor import predict_intent_forest, fit_isolation_forest, extract_track_features

    config = load_config(args.config or None)
    db_path = get_db_path(config)
    print(f"Config loaded. DB: {db_path}")

    with get_connection(config=config) as conn:
        init_schema(conn)
        print("Schema ready.")

        # ---- Ingest: from log file or skip ----
        log_path = args.log or config.get("parser", {}).get("log_path") or ""
        if log_path and Path(log_path).is_file():
            from proactive.parser import parse_log_file
            df = parse_log_file(log_path)
            print(f"Parsed log: {len(df)} rows")
            if not df.empty:
                rows = df.to_dict("records")
                ids = insert_detection_events(conn, rows)
                print(f"Inserted {len(ids)} detection_events")
        else:
            import pandas as pd
            from proactive.db import detection_events_dataframe
            try:
                df = detection_events_dataframe(conn)
            except Exception:
                df = pd.DataFrame()
            if df.empty:
                print("No log path provided and DB has no events. Use --log /path/to/log or set SURVEILLANCE_LOG_PATH.")
                return
            print(f"Using existing DB: {len(df)} events")

        # ---- Tracks ----
        gap = config.get("predictor", {}).get("loiter_duration_sec", 300)
        n_tracks = build_tracks_from_events(conn, gap_seconds=gap, object_filter="person")
        print(f"Built {n_tracks} tracks from events")

        # ---- Predictor: fit Isolation Forest on tracks, then score ----
        import pandas as _pd
        tracks_df = _pd.read_sql_query("SELECT * FROM tracks ORDER BY start_utc", conn)
        tracks_list = tracks_df.to_dict("records")
        forest = None
        if config.get("predictor", {}).get("use_isolation_forest") and tracks_list:
            forest = fit_isolation_forest(tracks_list)
        feature_vectors = None
        if tracks_list:
            import numpy as np
            feature_vectors = np.vstack([extract_track_features(t) for t in tracks_list])

        for t in tracks_list:
            pred = predict_intent_forest(t, forest, feature_vectors)
            print(f"  Track {t.get('id')}: intent={pred.intent} threat={pred.threat_score:.0f} flags={pred.rule_flags}")

            if not args.no_alerts and config.get("deterrence", {}).get("enabled"):
                from proactive.alerts import run_deterrence
                run_deterrence(pred.threat_score, config)

        # ---- Viz ----
        if not args.no_viz and not df.empty:
            from proactive.visualization import plot_detections_per_hour, plot_anomaly_timeline
            viz = config.get("viz", {})
            plot_detections_per_hour(df, output_path=viz.get("detections_per_hour_path", "detections_per_hour.png"))
            plot_anomaly_timeline(df, output_path=viz.get("timeline_path", "timeline_anomalies.png"))
            print("Saved plots.")

        # ---- ReID status ----
        from proactive.reid import is_reid_available, get_embedding_dim
        print(f"ReID: available={is_reid_available()}, dim={get_embedding_dim()}")

    print("Done. See config.yaml and docs/LEGAL_AND_ETHICS.md for legal/ethical use.")


if __name__ == "__main__":
    main()
