/**
 * Shared labels, descriptions, and flags for events, behaviors, and severity across the web UI.
 */

export type EventTypeKey = 'motion' | 'loitering' | 'line_cross' | 'motion_alert' | string;
export type SeverityKey = 'high' | 'medium' | 'low' | string;

export const EVENT_TYPE_LABELS: Record<string, string> = {
  motion: 'Motion',
  loitering: 'Loitering',
  line_cross: 'Line crossing',
  fall: 'Fall',
  crowding: 'Crowding',
  motion_alert: 'Motion alert',
};

export const EVENT_TYPE_DESCRIPTIONS: Record<string, string> = {
  motion: 'Camera detected motion in the frame.',
  loitering: 'Person or object remained in a monitored zone longer than the threshold.',
  line_cross: 'Person or object crossed a configured virtual line.',
  fall: 'Person down detected (pose heuristic; possible fall).',
  crowding: 'Person count exceeded crowding threshold.',
  motion_alert: 'Motion-triggered alert (e.g. threshold or zone).',
};

export const BEHAVIOR_LABELS: Record<string, string> = {
  'Motion Detected': 'Motion detected',
  'Loitering Detected': 'Loitering detected',
  'Line Crossing Detected': 'Line crossing detected',
  'Fall Detected': 'Fall detected',
  'Crowding Detected': 'Crowding detected',
  'None': 'No alert',
};

export const BEHAVIOR_DESCRIPTIONS: Record<string, string> = {
  'Motion Detected': 'Pixel change or motion in the scene triggered this event.',
  'Loitering Detected': 'Subject stayed in a loiter zone beyond the configured time.',
  'Line Crossing Detected': 'Subject crossed a configured crossing line (direction may be logged).',
  'Fall Detected': 'Pose heuristic indicated person down (possible fall).',
  'Crowding Detected': 'Person count exceeded the crowding alert threshold.',
  None: 'No behavioral alert in this sample.',
};

export const SEVERITY_LABELS: Record<string, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

export const SEVERITY_DESCRIPTIONS: Record<string, string> = {
  high: 'Requires immediate attention. Review and acknowledge.',
  medium: 'Standard priority. Review when possible.',
  low: 'Informational. No urgent action required.',
};

/** Flags shown in the UI (e.g. badge text and title) */
export const FLAGS = {
  NEEDS_REVIEW: { label: 'Needs review', title: 'Unacknowledged; review and acknowledge when handled.', slug: 'needs_review' },
  ACKNOWLEDGED: { label: 'Acknowledged', title: 'Event has been reviewed and acknowledged.', slug: 'acknowledged' },
  HIGH_PRIORITY: { label: 'High priority', title: 'High severity; prioritize review.', slug: 'high_priority' },
  ALERT: { label: 'Alert', title: 'Alert-level event (motion / loitering / line cross).', slug: 'alert' },
} as const;

export function getEventTypeLabel(key: EventTypeKey): string {
  return EVENT_TYPE_LABELS[key] ?? key;
}

export function getEventTypeDescription(key: EventTypeKey): string {
  return EVENT_TYPE_DESCRIPTIONS[key] ?? '';
}

export function getBehaviorLabel(behavior: string): string {
  return BEHAVIOR_LABELS[behavior] ?? behavior;
}

export function getBehaviorDescription(behavior: string): string {
  return BEHAVIOR_DESCRIPTIONS[behavior] ?? '';
}

export function getSeverityLabel(severity: SeverityKey): string {
  return SEVERITY_LABELS[severity] ?? severity;
}

export function getSeverityDescription(severity: SeverityKey): string {
  return SEVERITY_DESCRIPTIONS[severity] ?? '';
}

/** Extended detection attributes (person description, behavior, intent, sci-fi style scores). */
export const EXTENDED_ATTRIBUTE_LABELS: Record<string, string> = {
  perceived_gender: 'Gender (perceived)',
  perceived_age: 'Age (years)',
  perceived_age_range: 'Age (raw)',
  perceived_ethnicity: 'Ethnicity (perceived)',
  hair_color: 'Hair color',
  estimated_height_cm: 'Height (cm)',
  build: 'Build',
  intoxication_indicator: 'Intoxication',
  drug_use_indicator: 'Drug use indicator',
  suspicious_behavior: 'Suspicious behavior',
  predicted_intent: 'Predicted intent',
  stress_level: 'Stress level',
  micro_expression: 'Micro-expression',
  gait_notes: 'Gait notes',
  clothing_description: 'Clothing',
  threat_score: 'Threat score',
  anomaly_score: 'Anomaly score',
  attention_region: 'Attention region',
  detection_confidence: 'Detection confidence',
};

export const EXTENDED_ATTRIBUTE_DESCRIPTIONS: Record<string, string> = {
  perceived_gender: 'Raw model-inferred gender (DeepFace).',
  perceived_age: 'Raw estimated age in years (model output).',
  perceived_age_range: 'Raw age as string (same as perceived_age).',
  perceived_ethnicity: 'Raw model-inferred ethnicity (DeepFace).',
  hair_color: 'Dominant color in head region (heuristic).',
  estimated_height_cm: 'Approximate height from pose/bbox scale.',
  build: 'Body build: slim, medium, heavy (from bbox aspect).',
  intoxication_indicator: 'Possible intoxication from gait/behavior (stub: none/possible/likely).',
  drug_use_indicator: 'Possible drug use indicator (stub).',
  suspicious_behavior: 'Behavior flag: none, loitering, line_crossing.',
  predicted_intent: 'Inferred intent: passing, loitering, crossing, unknown.',
  stress_level: 'Stress proxy from emotion: low, medium, high.',
  micro_expression: 'Brief facial expression (or dominant emotion).',
  gait_notes: 'Gait description: normal, unsteady, rapid (stub).',
  clothing_description: 'Dominant body-region color/description.',
  threat_score: 'Heuristic 0–100 risk score from behavior and stress.',
  anomaly_score: 'Behavioral anomaly 0–1 (e.g. loiter/line_cross).',
  attention_region: 'Where subject is looking (stub; needs gaze model).',
  detection_confidence: 'YOLO confidence for primary person (0–1); NIST AI 100-4 provenance.',
};

/** Extended audio attributes (same intensity as visual pipeline). */
export const AUDIO_ATTRIBUTE_LABELS: Record<string, string> = {
  audio_transcription: 'Transcription',
  audio_emotion: 'Audio emotion',
  audio_stress_level: 'Audio stress',
  audio_speaker_gender: 'Speaker gender',
  audio_speaker_age_range: 'Speaker age range',
  audio_intoxication_indicator: 'Audio intoxication',
  audio_sentiment: 'Audio sentiment',
  audio_energy_db: 'Energy (dB)',
  audio_background_type: 'Background type',
  audio_threat_score: 'Audio threat score',
  audio_anomaly_score: 'Audio anomaly score',
  audio_speech_rate: 'Speech rate (wpm)',
  audio_language: 'Language',
  audio_keywords: 'Keywords',
};

export const AUDIO_ATTRIBUTE_DESCRIPTIONS: Record<string, string> = {
  audio_transcription: 'Speech-to-text from microphone.',
  audio_emotion: 'Emotion inferred from keywords (angry, sad, happy, fear, calm, distress).',
  audio_stress_level: 'Stress from keywords and threat cues: low, medium, high.',
  audio_speaker_gender: 'Speaker gender from voice (stub; needs voice model).',
  audio_speaker_age_range: 'Speaker age band from voice (stub).',
  audio_intoxication_indicator: 'Possible intoxication from speech (stub).',
  audio_sentiment: 'Sentiment: positive, negative, neutral, threat.',
  audio_energy_db: 'RMS level in dB (loudness).',
  audio_background_type: 'silence, speech, quiet_speech, loud_speech_or_noise.',
  audio_threat_score: '0–100 from threat keywords.',
  audio_anomaly_score: 'Anomaly from energy or threat keywords.',
  audio_speech_rate: 'Words per minute.',
  audio_language: 'Detected language (e.g. en).',
  audio_keywords: 'Extracted threat/emotion keywords.',
};
