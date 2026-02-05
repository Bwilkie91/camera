# Surveillance log analysis report

## Data quality summary

- **Total rows:** 5
- **Hours covered:** 0.1
- **Missing key fields:** None critical.

## Most likely field meanings (evidence)

- **value / estimated_height_cm:** 3-digit number after hair_color. In sample, clusters 170–178; indoor often ~170–172, outdoor 178. Could be height_cm, bbox height px, or confidence×100; stability indoors suggests fixed camera/distance.

- **hair_color, clothing_description:** From parser keyword matching (gray, brown, dark, top/body).

- **timestamp_utc / local_timestamp:** Parsed from leading M/D/YY H:MM:SS and trailing ISO UTC.

## Revised interpretation of events

Likely 1–2 subjects transiting; indoor cluster suggests entry/exit. Value stability indoors may indicate fixed camera distance estimation rather than true height. Recommend cross-check with YOLO/Frigate docs for attribute semantics.

## Key visuals

- ![value_over_time.png](value_over_time.png)

- ![detections_per_minute.png](detections_per_minute.png)

- ![value_distribution.png](value_distribution.png)

## Recommendations

- If this is YOLO attribute output, cross-check with official Ultralytics/Frigate docs for column semantics.
- Emit JSON Lines per event for reliable parsing and audit.
- Add camera_id and model_version to each line for multi-camera correlation.
