"""
Vigil — Edge Video Security. Flask backend.
AI-powered surveillance with real-time analytics, multi-camera support, and compliance-ready export.
GPIO, PyAudio, and Scapy are optional (enable via env or run on Pi/Jetson).
"""
import os
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    load_dotenv(_env_path)
except ImportError:
    pass
from flask import Flask, render_template, Response, jsonify, request, session, abort, redirect, make_response
from functools import wraps
try:
    from flask_sock import Sock
    SOCK_AVAILABLE = True
except ImportError:
    Sock = None
    SOCK_AVAILABLE = False
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    bcrypt = None
    BCRYPT_AVAILABLE = False
import cv2
import numpy as np
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO = None
    YOLO_AVAILABLE = False
try:
    from deepface import DeepFace  # type: ignore[reportMissingImports]
    DEEPFACE_AVAILABLE = True
except ImportError:
    DeepFace = None
    DEEPFACE_AVAILABLE = False
try:
    from emotiefflib.facial_analysis import EmotiEffLibRecognizer, get_model_list as _emotieff_get_models  # type: ignore[reportMissingImports]
    EMOTIEFFLIB_AVAILABLE = True
except Exception:
    EmotiEffLibRecognizer = None
    _emotieff_get_models = None
    EMOTIEFFLIB_AVAILABLE = False
import pytesseract
# MediaPipe pose: prefer legacy solutions API; fall back to Tasks API (0.10.30+)
mp = None
mp_pose = None
MEDIAPIPE_AVAILABLE = False
try:
    import mediapipe as mp
    if getattr(mp, 'solutions', None) is not None:
        mp_pose = mp.solutions.pose.Pose()
        MEDIAPIPE_AVAILABLE = True
except (ImportError, AttributeError):
    pass
if not MEDIAPIPE_AVAILABLE and mp is not None:
    try:
        from mediapipe.tasks.python.vision import PoseLandmarker
        from mediapipe.tasks.python.vision.core import image as mp_image
        _mp_image = mp_image
        _PoseLandmarker = PoseLandmarker

        def _mediapipe_pose_model_path():
            """Return path to pose_landmarker.task; download from CDN if missing."""
            env_path = os.environ.get('MEDIAPIPE_POSE_MODEL_PATH', '').strip()
            if env_path and os.path.isfile(env_path):
                return env_path
            cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
            os.makedirs(cache_dir, exist_ok=True)
            path = os.path.join(cache_dir, 'pose_landmarker_lite.task')
            if os.path.isfile(path):
                return path
            url = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task'
            try:
                import urllib.request
                urllib.request.urlretrieve(url, path)
                return path
            except Exception:
                return None

        _pose_model_path = _mediapipe_pose_model_path()
        if _pose_model_path:
            _pose_landmarker = _PoseLandmarker.create_from_model_path(_pose_model_path)

            class _LegacyPoseResult:
                """Wrapper so Tasks API result looks like legacy pose result (pose_landmarks.landmark)."""
                def __init__(self, task_result):
                    if task_result and task_result.pose_landmarks and len(task_result.pose_landmarks) > 0:
                        self.pose_landmarks = type('LM', (), {'landmark': task_result.pose_landmarks[0]})()
                    else:
                        self.pose_landmarks = None

            class _MediaPipePoseAdapter:
                def process(self, rgb_frame):
                    if rgb_frame is None or rgb_frame.size == 0:
                        return _LegacyPoseResult(None)
                    try:
                        h, w = rgb_frame.shape[:2]
                        if rgb_frame.ndim == 2:
                            rgb_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_GRAY2RGB)
                        if rgb_frame.dtype != np.uint8:
                            rgb_frame = (np.clip(rgb_frame, 0, 1) * 255).astype(np.uint8) if rgb_frame.max() <= 1 else rgb_frame.astype(np.uint8)
                        mp_img = _mp_image.Image(_mp_image.ImageFormat.SRGB, np.ascontiguousarray(rgb_frame))
                        result = _pose_landmarker.detect(mp_img)
                        return _LegacyPoseResult(result)
                    except Exception:
                        return _LegacyPoseResult(None)

            mp_pose = _MediaPipePoseAdapter()
            MEDIAPIPE_AVAILABLE = True
    except Exception:
        pass
import hashlib
import logging
import math
import re
import shutil
import sqlite3
import time
import threading
import io
import platform
import queue
import json
from collections import deque, Counter

import PIL.Image

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-change-in-production')
# Ensure session cookie is sent on same-origin requests (avoid sign-in loop after POST /login)
app.config['SESSION_COOKIE_SAMESITE'] = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', '').lower() in ('1', 'true', 'yes')
SESSION_TIMEOUT_MINUTES = int(os.environ.get('SESSION_TIMEOUT_MINUTES', '60'))
_app_start_time = time.time()
_camera_last_frame_time = {}  # camera_id -> last time we got a frame (for status)
_camera_prev_status = {}  # camera_id -> last computed status ('ok'|'no_signal'|'offline')
_camera_last_offline_at = {}  # camera_id -> time when it last transitioned to offline/no_signal
_camera_status_change_times = {}  # camera_id -> list of (timestamp,) for recent transitions (flapping detection)
_gait_notes_enabled_cached = None


def _is_gait_notes_enabled():
    """Cached read of ENABLE_GAIT_NOTES (avoids repeated os.environ in hot path)."""
    global _gait_notes_enabled_cached
    if _gait_notes_enabled_cached is None:
        _gait_notes_enabled_cached = os.environ.get('ENABLE_GAIT_NOTES', '1').strip().lower() in ('1', 'true', 'yes')
    return _gait_notes_enabled_cached


def _check_session_timeout():
    """Enforce inactivity timeout (NIST/CJIS-style session control). Returns response to return from before_request, or None."""
    if not session.get('user_id'):
        return None
    path = (request.path or '').rstrip('/')
    if path in ('', 'login', 'logout') or path.startswith('/video_feed') or path.startswith('/thermal_feed') or path == '/health' or path == '/recording':
        return None
    now = time.time()
    last = session.get('last_activity')
    session['last_activity'] = now
    if last is not None and (now - last) > SESSION_TIMEOUT_MINUTES * 60:
        session.clear()
        from flask import make_response
        resp = make_response(json.dumps({'error': 'session_timeout', 'message': 'Session expired'}), 401)
        resp.headers['Content-Type'] = 'application/json'
        return resp
    return None


@app.before_request
def _before_request():
    if os.environ.get('ENABLE_CORS', '').lower() in ('1', 'true', 'yes') and request.method == 'OPTIONS':
        from flask import make_response
        return make_response('', 204)
    if os.environ.get('ENFORCE_HTTPS', '').lower() in ('1', 'true', 'yes'):
        if not request.is_secure and request.headers.get('X-Forwarded-Proto') != 'https':
            from flask import redirect
            return redirect(request.url.replace('http://', 'https://', 1), code=302)
    return _check_session_timeout()


@app.after_request
def _security_headers(resp):
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'DENY'
    if os.environ.get('STRICT_TRANSPORT_SECURITY', '').lower() in ('1', 'true', 'yes'):
        resp.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    csp = os.environ.get('CONTENT_SECURITY_POLICY', '').strip()
    if csp:
        resp.headers['Content-Security-Policy'] = csp
    return resp


if os.environ.get('ENABLE_CORS', '').lower() in ('1', 'true', 'yes'):
    @app.after_request
    def _cors(resp):
        # Never use '*' with credentials: browsers ignore Set-Cookie (sign-in loop).
        origin = request.origin or os.environ.get('CORS_ORIGIN', '').strip()
        if not origin and request.url_root:
            origin = request.url_root.rstrip('/')
        if origin:
            resp.headers['Access-Control-Allow-Origin'] = origin
        resp.headers['Access-Control-Allow-Credentials'] = 'true'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PATCH, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return resp

if SOCK_AVAILABLE:
    sock = Sock(app)
else:
    sock = None
_ws_clients = []

_redis_url = os.environ.get('REDIS_URL', '').strip()
if _redis_url:
    try:
        import redis  # type: ignore[reportMissingImports]
        _redis_pub = redis.from_url(_redis_url)
        _redis_sub = redis.from_url(_redis_url)
        _redis_sub = _redis_sub.pubsub()
        _redis_sub.subscribe('vms:events')
    except Exception:
        _redis_pub = None
        _redis_sub = None
else:
    _redis_pub = None
    _redis_sub = None


_sse_listeners = []  # list of queue.Queue for Server-Sent Events (live feed updates)


def _broadcast_event(msg):
    if sock:
        dead = []
        for i, ws in enumerate(_ws_clients):
            try:
                ws.send(json.dumps(msg))
            except Exception:
                dead.append(i)
        for i in reversed(dead):
            _ws_clients.pop(i)
    if _redis_pub:
        try:
            _redis_pub.publish('vms:events', json.dumps(msg))
        except Exception:
            pass
    for q in _sse_listeners:
        try:
            q.put_nowait(msg)
        except Exception:
            pass


def _redis_subscriber():
    global _redis_sub
    if not _redis_sub or not sock:
        return
    for message in _redis_sub.listen():
        if message.get('type') != 'message':
            continue
        try:
            payload = message.get('data')
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
            data = json.loads(payload)
            dead = []
            for i, ws in enumerate(_ws_clients):
                try:
                    ws.send(json.dumps(data))
                except Exception:
                    dead.append(i)
            for i in reversed(dead):
                _ws_clients.pop(i)
        except Exception:
            pass


def _audit(user_id: str, action: str, resource: str = None, details: str = None):
    try:
        get_cursor().execute(
            'INSERT INTO audit_log (user_id, action, resource, details) VALUES (?, ?, ?, ?)',
            (user_id or 'anonymous', action, resource, details)
        )
        get_conn().commit()
        row_id = get_cursor().lastrowid
        get_cursor().execute('SELECT timestamp FROM audit_log WHERE id = ?', (row_id,))
        row = get_cursor().fetchone()
        if row_id and row:
            ts = row[0] or ''
            u, a, r, d = (user_id or 'anonymous', action, resource or '', details or '')
            payload = f'{row_id}|{u}|{a}|{r}|{ts}|{d}'
            h = hashlib.sha256(payload.encode('utf-8')).hexdigest()
            get_cursor().execute('UPDATE audit_log SET integrity_hash = ? WHERE id = ?', (h, row_id))
            get_conn().commit()
    except Exception:
        pass


def _log_structured(event: str, **kwargs):
    """Emit one JSON line for log aggregation (e.g. NIST AU-2, SI-4). Keys should be safe for JSON."""
    try:
        _vigil_log = logging.getLogger('vigil')
        if not _vigil_log.handlers:
            _vigil_log.setLevel(logging.INFO)
            _h = logging.StreamHandler()
            _h.setFormatter(logging.Formatter('%(message)s'))
            _vigil_log.addHandler(_h)
        payload = {'event': event, 'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **kwargs}
        _vigil_log.info(json.dumps(payload))
    except Exception:
        pass


def _client_context():
    """IP and User-Agent for audit (NIST AU-2)."""
    ip = request.remote_addr or ''
    ua = (request.user_agent.string or '')[:200]
    return f'ip={ip} ua={ua}' if (ip or ua) else None


# Account lockout (NIST AC-7 / CJIS): max attempts, lock duration minutes
LOCKOUT_MAX_ATTEMPTS = int(os.environ.get('LOCKOUT_MAX_ATTEMPTS', '5'))
LOCKOUT_DURATION_MINUTES = int(os.environ.get('LOCKOUT_DURATION_MINUTES', '15'))


def _is_locked(username: str) -> bool:
    try:
        get_cursor().execute('SELECT locked_until FROM login_attempts WHERE username = ?', (username,))
        row = get_cursor().fetchone()
        if not row or row[0] is None:
            return False
        if row[0] <= time.time():
            get_cursor().execute('UPDATE login_attempts SET attempt_count = 0, locked_until = NULL WHERE username = ?', (username,))
            get_conn().commit()
            return False
        return True
    except Exception:
        return False


def _record_failed_login(username: str):
    try:
        now_ts = time.time()
        get_cursor().execute('SELECT attempt_count, locked_until FROM login_attempts WHERE username = ?', (username,))
        row = get_cursor().fetchone()
        if not row:
            locked_until = (now_ts + LOCKOUT_DURATION_MINUTES * 60) if LOCKOUT_MAX_ATTEMPTS <= 1 else None
            get_cursor().execute('INSERT INTO login_attempts (username, attempt_count, locked_until) VALUES (?, 1, ?)',
                           (username, locked_until))
        else:
            count, locked = row[0], row[1]
            if locked and locked > now_ts:
                return
            count += 1
            locked_until = (now_ts + LOCKOUT_DURATION_MINUTES * 60) if count >= LOCKOUT_MAX_ATTEMPTS else None
            get_cursor().execute('UPDATE login_attempts SET attempt_count = ?, locked_until = ? WHERE username = ?', (count, locked_until, username))
        get_conn().commit()
    except Exception:
        pass


def _clear_login_attempts(username: str):
    try:
        get_cursor().execute('DELETE FROM login_attempts WHERE username = ?', (username,))
        get_conn().commit()
    except Exception:
        pass


# Password policy (NIST/CJIS): configurable strength, expiry, history
PASSWORD_MIN_LENGTH = int(os.environ.get('PASSWORD_MIN_LENGTH', '8'))
PASSWORD_REQUIRE_DIGIT = os.environ.get('PASSWORD_REQUIRE_DIGIT', '1').lower() in ('1', 'true', 'yes')
PASSWORD_REQUIRE_SPECIAL = os.environ.get('PASSWORD_REQUIRE_SPECIAL', '1').lower() in ('1', 'true', 'yes')
PASSWORD_EXPIRY_DAYS = int(os.environ.get('PASSWORD_EXPIRY_DAYS', '0'))  # 0 = no expiry
PASSWORD_HISTORY_COUNT = int(os.environ.get('PASSWORD_HISTORY_COUNT', '5'))  # 0 = no history check


def _validate_password(password: str):
    """Returns (valid, error_message)."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f'At least {PASSWORD_MIN_LENGTH} characters required'
    if PASSWORD_REQUIRE_DIGIT and not re.search(r'\d', password):
        return False, 'At least one digit required'
    if PASSWORD_REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;/\'`~]', password):
        return False, 'At least one special character required'
    return True, ''


# Optional MFA (NIST IR 8523 / CJIS 6.0) - TOTP for admin/operator
ENABLE_MFA = os.environ.get('ENABLE_MFA', '').lower() in ('1', 'true', 'yes')
try:
    import pyotp  # type: ignore[reportMissingImports]
    PYOTP_AVAILABLE = True
except ImportError:
    pyotp = None
    PYOTP_AVAILABLE = False

MFA_TOKEN_TTL_SECONDS = 300  # 5 min for mfa_token after password OK


def _user_has_mfa_enabled(uid: int) -> bool:
    if not ENABLE_MFA or not PYOTP_AVAILABLE:
        return False
    try:
        get_cursor().execute('SELECT 1 FROM user_mfa WHERE user_id = ? AND enabled = 1', (uid,))
        return get_cursor().fetchone() is not None
    except Exception:
        return False


def _clean_expired_mfa_tokens():
    try:
        get_cursor().execute('DELETE FROM mfa_tokens WHERE expires < ?', (time.time(),))
        get_conn().commit()
    except Exception:
        pass


def require_role(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not allowed_roles:
                return f(*args, **kwargs)
            role = session.get('role')
            if role not in allowed_roles:
                return jsonify({'error': 'Forbidden', 'required': list(allowed_roles)}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator


def _get_user_allowed_site_ids():
    """Resource-level RBAC: if user has site restrictions, return list of site_ids; else None (all sites)."""
    if not session.get('user_id'):
        return None
    if session.get('role') == 'admin':
        return None
    try:
        get_cursor().execute('SELECT site_id FROM user_site_roles WHERE user_id = ?', (int(session['user_id']),))
        rows = get_cursor().fetchall()
        if not rows:
            return None
        return [r[0] for r in rows]
    except Exception:
        return None


def _trigger_alert(event_type: str, severity: str, metadata: str = None):
    """Send alerts: SMS (ALERT_SMS_URL), generic webhook (ALERT_WEBHOOK_URL), and optional MQTT (ALERT_MQTT_BROKER)."""
    if severity != 'high' and event_type not in ('motion', 'line_cross', 'loitering', 'fall', 'crowding'):
        return
    payload = {
        'event_type': event_type,
        'severity': severity,
        'metadata': metadata,
        'camera_id': '0',
        'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    # Generic webhook (POST JSON)
    webhook_url = os.environ.get('ALERT_WEBHOOK_URL', '').strip()
    if webhook_url:
        try:
            from urllib.request import Request, urlopen
            req = Request(webhook_url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
            urlopen(req, timeout=5)
        except Exception:
            pass
    # SMS (legacy Node service)
    url = os.environ.get('ALERT_SMS_URL')
    if url:
        try:
            from urllib.request import Request, urlopen
            body = json.dumps({'phone': os.environ.get('ALERT_PHONE', ''), 'message': f'Alert: {event_type} ({severity})'})
            req = Request(url, data=body.encode(), headers={'Content-Type': 'application/json'}, method='POST')
            urlopen(req, timeout=5)
        except Exception:
            pass
    # Optional MQTT (paho-mqtt)
    mqtt_broker = os.environ.get('ALERT_MQTT_BROKER', '').strip()
    if mqtt_broker:
        try:
            from urllib.parse import urlparse
            import paho.mqtt.client as mqtt  # type: ignore[reportMissingModuleSource]
            parsed = urlparse(mqtt_broker if '://' in mqtt_broker else 'tcp://' + mqtt_broker)
            host = parsed.hostname or parsed.path or 'localhost'
            port = parsed.port or 1883
            topic = os.environ.get('ALERT_MQTT_TOPIC', 'vms/events')
            client_id = os.environ.get('ALERT_MQTT_CLIENT_ID', 'vigil')
            client = mqtt.Client(client_id=client_id)
            client.connect(host, port, 10)
            client.publish(topic, json.dumps(payload), qos=0)
            client.disconnect()
        except Exception:
            pass


def _perimeter_action(event_type: str, camera_id: str, timestamp_utc: str):
    """On perimeter breach (line_cross or loitering): POST to PERIMETER_ACTION_URL and/or set ALERT_GPIO_PIN high for N sec. Civilian deterrence (spotlight/siren relay)."""
    if event_type not in ('line_cross', 'loitering'):
        return
    payload = {'event_type': event_type, 'camera_id': camera_id, 'timestamp': timestamp_utc}
    url = os.environ.get('PERIMETER_ACTION_URL', '').strip()
    if url:
        try:
            from urllib.request import Request, urlopen
            req = Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
            urlopen(req, timeout=5)
        except Exception:
            pass
    try:
        pin = int(os.environ.get('ALERT_GPIO_PIN', '0'))
    except (TypeError, ValueError):
        pin = 0
    if pin > 0 and GPIO_AVAILABLE:
        try:
            import RPi.GPIO as GPIO  # type: ignore[reportMissingModuleSource]
            dur = max(1, min(60, int(os.environ.get('PERIMETER_GPIO_DURATION_SEC', '5'))))
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)
            def _gpio_low():
                time.sleep(dur)
                try:
                    GPIO.output(pin, GPIO.LOW)
                except Exception:
                    pass
            threading.Thread(target=_gpio_low, daemon=True).start()
        except Exception:
            pass


def _autonomous_action(event_type: str, camera_id: str, timestamp_utc: str, threat_score, metadata: str = None):
    """Opt-in: when threat_score >= AUTONOMOUS_ACTION_THRESHOLD and event_type in AUTONOMOUS_ACTION_EVENT_TYPES, POST to AUTONOMOUS_ACTION_URL (e.g. home-automation lock). High liability; operator config and disclaimer required."""
    url = os.environ.get('AUTONOMOUS_ACTION_URL', '').strip()
    if not url:
        return
    try:
        threshold = int(os.environ.get('AUTONOMOUS_ACTION_THRESHOLD', '70'))
    except (TypeError, ValueError):
        threshold = 70
    raw_types = (os.environ.get('AUTONOMOUS_ACTION_EVENT_TYPES') or 'line_cross,loitering').strip()
    allowed = {s.strip().lower() for s in raw_types.split(',') if s.strip()}
    if event_type.lower() not in allowed:
        return
    score = 0
    if threat_score is not None:
        try:
            score = int(threat_score) if isinstance(threat_score, (int, float)) else (int(threat_score) if isinstance(threat_score, str) and threat_score.isdigit() else 0)
        except (TypeError, ValueError):
            pass
    if score < threshold:
        return
    payload = {
        'event_type': event_type,
        'camera_id': camera_id,
        'timestamp': timestamp_utc,
        'threat_score': score,
        'metadata': metadata,
        'source': 'vigil_autonomous_action',
    }
    try:
        from urllib.request import Request, urlopen
        req = Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
        urlopen(req, timeout=5)
    except Exception:
        pass


# Optional GPIO: only on Raspberry Pi / Jetson (arm) or when USE_GPIO=1
USE_GPIO = os.environ.get('USE_GPIO', '').lower() in ('1', 'true', 'yes')
IS_ARM = 'aarch64' in platform.machine() or 'arm' in platform.machine()
GPIO_AVAILABLE = False
motor_pwm = None

if USE_GPIO or IS_ARM:
    try:
        import RPi.GPIO as GPIO  # type: ignore[reportMissingModuleSource]
        GPIO.setmode(GPIO.BCM)
        MOTOR_PINS = [23, 24, 25]
        for pin in MOTOR_PINS:
            GPIO.setup(pin, GPIO.OUT)
        motor_pwm = GPIO.PWM(25, 100)
        motor_pwm.start(0)
        GPIO_AVAILABLE = True
    except (ImportError, RuntimeError):
        pass

# Optional ONVIF PTZ (env: ONVIF_HOST, ONVIF_PORT=80, ONVIF_USER, ONVIF_PASS)
_onvif_ptz = None
_onvif_profile_token = None
try:
    from onvif import ONVIFCamera  # type: ignore[reportMissingImports]
    _host = os.environ.get('ONVIF_HOST')
    _port = int(os.environ.get('ONVIF_PORT', '80'))
    _user = os.environ.get('ONVIF_USER', '')
    _pass = os.environ.get('ONVIF_PASS', '')
    if _host and _user and _pass:
        _cam = ONVIFCamera(_host, _port, _user, _pass)
        _media = _cam.create_media_service()
        _profiles = _media.GetProfiles()
        if _profiles:
            _onvif_profile_token = _profiles[0].token
            _onvif_ptz = _cam.create_ptz_service()
except Exception:
    pass

# Multi-camera config: env CAMERA_SOURCES=0,1 or rtsp://... for RTSP; use "auto" or leave unset to auto-detect
# macOS: use CAP_AVFOUNDATION for built-in MacBook/iSight so laptop camera works reliably
def _open_video_capture(source):
    """Open VideoCapture for source (int index or URL). On macOS, use AVFoundation for device indices.
    Sets CAP_PROP_BUFFERSIZE=1 when supported to reduce latency (research: OpenCV buffer lag).
    For RTSP/URL, sets open/read timeout when RTSP_TIMEOUT_MS is set (OpenCV 4.6+ where available)."""
    cap = None
    if isinstance(source, str) and not source.isdigit():
        cap = cv2.VideoCapture(source)  # RTSP/URL
        if cap.isOpened():
            _rtsp_ms = os.environ.get('RTSP_TIMEOUT_MS', '').strip()
            if _rtsp_ms.isdigit():
                try:
                    t = int(_rtsp_ms)
                    for prop in ('CAP_PROP_OPEN_TIMEOUT_MS', 'CAP_PROP_READ_TIMEOUT_MS'):
                        if hasattr(cv2, prop):
                            cap.set(getattr(cv2, prop), t)
                            break
                except Exception:
                    pass
    else:
        idx = int(source) if isinstance(source, str) else source
        cap = None
        if platform.system() == 'Darwin':
            try:
                cap = cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION)
                if not cap.isOpened():
                    cap.release()
                    cap = None
            except Exception:
                cap = None
        if cap is None:
            cap = cv2.VideoCapture(idx)
    if cap is not None and cap.isOpened():
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
    return cap


def _auto_detect_camera_indices(max_probe=10):
    """Probe OpenCV indices 0..max_probe-1; return list of index strings for cameras that open (for laptop/device auto-integration)."""
    detected = []
    for idx in range(max_probe):
        cap = _open_video_capture(idx)
        if cap.isOpened():
            detected.append(str(idx))
            cap.release()
    return detected if detected else ['0']  # at least one stream slot

_raw_camera_sources = os.environ.get('CAMERA_SOURCES', '0').strip()
_config_dir_for_cameras = os.environ.get('CONFIG_DIR', '').strip()
if _raw_camera_sources.lower() in ('', 'auto'):
    _camera_sources = _auto_detect_camera_indices()
elif _raw_camera_sources.lower() == 'yaml':
    # Load camera list from config/cameras.yaml or CONFIG_DIR/cameras.yaml (optional; requires PyYAML)
    _camera_sources = []
    _cameras_yaml_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'cameras.yaml'),
        os.path.join(_config_dir_for_cameras, 'cameras.yaml') if _config_dir_for_cameras else None,
    ]
    for _cam_path in _cameras_yaml_paths:
        if _cam_path and os.path.isfile(_cam_path):
            try:
                import yaml
                with open(_cam_path) as _f:
                    _cam_cfg = yaml.safe_load(_f)
                _cam_list = _cam_cfg.get('cameras') or []
                for _c in _cam_list:
                    _url = _c.get('url')
                    _idx = _c.get('index')
                    if _url is not None:
                        _camera_sources.append(str(_url).strip())
                    elif _idx is not None:
                        _camera_sources.append(str(_idx))
                break
            except Exception:
                pass
    if not _camera_sources:
        _camera_sources = ['0']
else:
    _camera_sources = _raw_camera_sources.split(',')
_cameras = {}
for i, src in enumerate(_camera_sources):
    src = src.strip()
    if not src:
        continue
    try:
        idx = int(src)
        cap = _open_video_capture(idx)
    except ValueError:
        cap = _open_video_capture(src)  # RTSP or URL (buffer set inside)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        _cameras[str(i)] = cap
if not _cameras:
    camera = _open_video_capture(0)
    if camera.isOpened():
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    _cameras['0'] = camera  # always show at least one stream; gen_frames yields placeholder if not opened
camera = _cameras['0']

# AI models — YOLO: configurable via YOLO_MODEL, YOLO_DEVICE, YOLO_IMGSZ, YOLO_CONF (accuracy: filter low-confidence detections)
# JETSON_MODE=1: tuned defaults (imgsz 640, conf 0.3). YOLO_EXPORT_FORMAT=onnx|engine: prefer .onnx/.engine when file exists.
yolo_model = None
_yolo_imgsz = 640
_yolo_conf = 0.25
if YOLO_AVAILABLE and YOLO:
    _yolo_path = os.environ.get('YOLO_MODEL', os.environ.get('YOLO_WEIGHTS', 'yolov8n.pt'))
    _yolo_device = os.environ.get('YOLO_DEVICE', '')
    _jetson = os.environ.get('JETSON_MODE', '').strip().lower() in ('1', 'true', 'yes')
    _export_fmt = (os.environ.get('YOLO_EXPORT_FORMAT') or '').strip().lower()
    if _export_fmt in ('onnx', 'engine') and _yolo_path.endswith('.pt'):
        _base = _yolo_path[:-3]
        _ext = '.onnx' if _export_fmt == 'onnx' else '.engine'
        if os.path.isfile(_base + _ext):
            _yolo_path = _base + _ext
    try:
        _yolo_imgsz = int(os.environ.get('YOLO_IMGSZ', '640'))
    except (TypeError, ValueError):
        _yolo_imgsz = 640
    if _jetson:
        _yolo_imgsz = 640
    try:
        _yolo_conf = float(os.environ.get('YOLO_CONF', '0.25'))
        _yolo_conf = max(0.01, min(0.95, _yolo_conf))
    except (TypeError, ValueError):
        _yolo_conf = 0.25
    if _jetson:
        _yolo_conf = 0.3
    _yolo_ignore_classes = set()
    _raw_ignore = (os.environ.get('YOLO_IGNORE_CLASSES') or '').strip()
    if _raw_ignore:
        _yolo_ignore_classes = {s.strip().lower() for s in _raw_ignore.split(',') if s.strip()}
    _yolo_class_conf = {}
    _raw_class_conf = (os.environ.get('YOLO_CLASS_CONF') or '').strip()
    if _raw_class_conf:
        if _raw_class_conf.startswith('{'):
            try:
                _yolo_class_conf = json.loads(_raw_class_conf)
                _yolo_class_conf = {str(k).strip().lower(): float(v) for k, v in _yolo_class_conf.items()}
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        else:
            for part in _raw_class_conf.split(','):
                if ':' in part:
                    k, v = part.split(':', 1)
                    try:
                        _yolo_class_conf[k.strip().lower()] = max(0.01, min(0.95, float(v.strip())))
                    except (TypeError, ValueError):
                        pass
    try:
        yolo_model = YOLO(_yolo_path)
        if _yolo_device:
            yolo_model.to(_yolo_device)
    except Exception:
        yolo_model = None
else:
    _yolo_ignore_classes = set()
    _yolo_class_conf = {}


def _filter_yolo_results(results):
    """Apply YOLO_IGNORE_CLASSES and YOLO_CLASS_CONF: drop ignored classes and low per-class confidence detections."""
    if not results or not results[0].boxes or not hasattr(results[0].boxes, 'cls'):
        return
    global _yolo_ignore_classes, _yolo_class_conf, _yolo_conf
    boxes = results[0].boxes
    names = getattr(results[0], 'names', None) or {}
    n = len(boxes.cls)
    if n == 0:
        return
    keep = []
    for i in range(n):
        cls_idx = int(boxes.cls[i].item())
        class_name = (names.get(cls_idx) or '').strip().lower()
        conf = float(boxes.conf[i].item()) if hasattr(boxes, 'conf') and boxes.conf is not None and i < len(boxes.conf) else _yolo_conf
        if class_name in _yolo_ignore_classes:
            continue
        thresh = _yolo_class_conf.get(class_name, _yolo_conf)
        if conf < thresh:
            continue
        keep.append(i)
    if len(keep) == n:
        return
    try:
        import torch
        mask = torch.zeros(n, dtype=torch.bool, device=boxes.cls.device)
        for i in keep:
            mask[i] = True
        results[0].boxes = results[0].boxes[mask]
    except Exception:
        pass


# MJPEG stream tuning (env read once at startup)
try:
    _stream_jpeg_quality = int(os.environ.get('STREAM_JPEG_QUALITY', '82'))
except (TypeError, ValueError):
    _stream_jpeg_quality = 82
try:
    _stream_max_width = int(os.environ.get('STREAM_MAX_WIDTH', '0'))
except (TypeError, ValueError):
    _stream_max_width = 0

# Optional: low-light and clarity enhancement for laptop/MacBook-style cameras (see docs/MACBOOK_LOW_LIGHT_VIDEO.md)
# ENHANCE_PRESET=macbook_air: stronger defaults for MacBook Air built-in camera in dim conditions (gamma 1.35, CLAHE 2.2)
_enhance_preset = (os.environ.get('ENHANCE_PRESET') or '').strip().lower()
_enable_enhance = os.environ.get('ENHANCE_VIDEO', '').strip().lower() in ('1', 'true', 'yes')
_enable_low_light = _enable_enhance or os.environ.get('ENHANCE_LOW_LIGHT', '').strip().lower() in ('1', 'true', 'yes')
_enable_clarity = _enable_enhance or os.environ.get('ENHANCE_CLARITY', '').strip().lower() in ('1', 'true', 'yes')
if _enhance_preset == 'macbook_air':
    _enable_low_light = True
    _enable_clarity = True
_default_clahe = 2.2 if _enhance_preset == 'macbook_air' else 2.0
_default_gamma = 1.35 if _enhance_preset == 'macbook_air' else 1.2
try:
    _enhance_clahe_clip = float(os.environ.get('ENHANCE_CLAHE_CLIP', str(_default_clahe)))
except (TypeError, ValueError):
    _enhance_clahe_clip = _default_clahe
try:
    _enhance_gamma = float(os.environ.get('ENHANCE_GAMMA', str(_default_gamma)))
except (TypeError, ValueError):
    _enhance_gamma = _default_gamma
_clahe = None
if _enable_low_light:
    try:
        _clahe = cv2.createCLAHE(clipLimit=_enhance_clahe_clip, tileGridSize=(8, 8))
    except Exception:
        _clahe = None
        _enable_low_light = False

# SQLite: one connection per thread to avoid SIGSEGV from concurrent access (Flask request threads + analyze_frame).
_db_local = threading.local()
# Batch commit for ai_data: buffer up to AI_DATA_BATCH_SIZE rows then commit once (analyze_frame thread only).
_ai_data_batch = []
try:
    _batch_size = int(os.environ.get('AI_DATA_BATCH_SIZE', '10'))
    AI_DATA_BATCH_SIZE = max(1, min(50, _batch_size))
except (TypeError, ValueError):
    AI_DATA_BATCH_SIZE = 10
# Analysis interval (seconds) between frame analyses when recording; research: 5–60s trade-off latency vs load.
try:
    _interval = int(os.environ.get('ANALYZE_INTERVAL_SECONDS', '10'))
    ANALYZE_INTERVAL_SECONDS = max(5, min(60, _interval))
except (TypeError, ValueError):
    ANALYZE_INTERVAL_SECONDS = 10

def _init_schema(c):
    """Create tables and run migrations. Idempotent per connection."""
    c.execute('''CREATE TABLE IF NOT EXISTS ai_data (
    date TEXT, time TEXT, individual TEXT, facial_features TEXT, object TEXT,
    pose TEXT, emotion TEXT, scene TEXT, license_plate TEXT, event TEXT, crowd_count INTEGER,
    audio_event TEXT, device_mac TEXT, thermal_signature TEXT
)''')
    c.execute('''CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    camera_id TEXT,
    site_id TEXT DEFAULT 'default',
    timestamp TEXT NOT NULL,
    metadata TEXT,
    severity TEXT DEFAULT 'medium',
    acknowledged_by TEXT,
    acknowledged_at TEXT
)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sites (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    map_url TEXT,
    timezone TEXT
)''')
    c.execute('''CREATE TABLE IF NOT EXISTS camera_positions (
    camera_id TEXT PRIMARY KEY,
    site_id TEXT,
    x REAL,
    y REAL,
    label TEXT,
    FOREIGN KEY (site_id) REFERENCES sites(id)
)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer'
)''')
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    action TEXT NOT NULL,
    resource TEXT,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details TEXT,
    integrity_hash TEXT
)''')
    try:
        c.execute('ALTER TABLE audit_log ADD COLUMN integrity_hash TEXT')
        c.commit()
    except sqlite3.OperationalError:
        pass
    c.execute('''CREATE TABLE IF NOT EXISTS login_attempts (
    username TEXT PRIMARY KEY,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    locked_until REAL
)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_mfa (
    user_id INTEGER PRIMARY KEY,
    secret TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mfa_tokens (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    expires REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
)''')
    c.execute('''CREATE TABLE IF NOT EXISTS password_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    password_hash TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
)''')
    c.execute('''CREATE TABLE IF NOT EXISTS legal_hold (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resource_type TEXT NOT NULL,
        resource_id TEXT NOT NULL,
        held_at TEXT NOT NULL,
        held_by TEXT NOT NULL,
        reason TEXT,
        UNIQUE(resource_type, resource_id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS saved_searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    params_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)''')
    c.execute('''CREATE TABLE IF NOT EXISTS recording_fixity (
    path TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    checked_at TEXT NOT NULL
)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_site_roles (
    user_id INTEGER NOT NULL,
    site_id TEXT NOT NULL,
    PRIMARY KEY (user_id, site_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (site_id) REFERENCES sites(id)
)''')
    c.execute('''CREATE TABLE IF NOT EXISTS notable_screenshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc TEXT NOT NULL,
    reason TEXT NOT NULL,
    reason_detail TEXT,
    file_path TEXT NOT NULL,
    camera_id TEXT DEFAULT '0',
    event_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)''')
    c.execute('''CREATE TABLE IF NOT EXISTS watchlist_faces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    embedding BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)''')
    for sql in (
        "ALTER TABLE events ADD COLUMN site_id TEXT DEFAULT 'default'",
        "ALTER TABLE ai_data ADD COLUMN camera_id TEXT DEFAULT '0'",
        "ALTER TABLE users ADD COLUMN password_expires_at REAL",
        "ALTER TABLE users ADD COLUMN expires_at REAL",
        "ALTER TABLE ai_data ADD COLUMN timestamp_utc TEXT",
        "ALTER TABLE ai_data ADD COLUMN model_version TEXT",
        "ALTER TABLE ai_data ADD COLUMN system_id TEXT",
        "ALTER TABLE ai_data ADD COLUMN integrity_hash TEXT",
        "ALTER TABLE events ADD COLUMN timestamp_utc TEXT",
        "ALTER TABLE events ADD COLUMN integrity_hash TEXT",
        "ALTER TABLE ai_data ADD COLUMN perceived_gender TEXT",
        "ALTER TABLE ai_data ADD COLUMN perceived_age_range TEXT",
        "ALTER TABLE ai_data ADD COLUMN hair_color TEXT",
        "ALTER TABLE ai_data ADD COLUMN estimated_height_cm INTEGER",
        "ALTER TABLE ai_data ADD COLUMN build TEXT",
        "ALTER TABLE ai_data ADD COLUMN intoxication_indicator TEXT",
        "ALTER TABLE ai_data ADD COLUMN drug_use_indicator TEXT",
        "ALTER TABLE ai_data ADD COLUMN suspicious_behavior TEXT",
        "ALTER TABLE ai_data ADD COLUMN predicted_intent TEXT",
        "ALTER TABLE ai_data ADD COLUMN stress_level TEXT",
        "ALTER TABLE ai_data ADD COLUMN micro_expression TEXT",
        "ALTER TABLE ai_data ADD COLUMN gait_notes TEXT",
        "ALTER TABLE ai_data ADD COLUMN clothing_description TEXT",
        "ALTER TABLE ai_data ADD COLUMN threat_score INTEGER",
        "ALTER TABLE ai_data ADD COLUMN anomaly_score REAL",
        "ALTER TABLE ai_data ADD COLUMN attention_region TEXT",
        "ALTER TABLE ai_data ADD COLUMN perceived_ethnicity TEXT",
        "ALTER TABLE ai_data ADD COLUMN audio_transcription TEXT",
        "ALTER TABLE ai_data ADD COLUMN audio_emotion TEXT",
        "ALTER TABLE ai_data ADD COLUMN audio_stress_level TEXT",
        "ALTER TABLE ai_data ADD COLUMN audio_speaker_gender TEXT",
        "ALTER TABLE ai_data ADD COLUMN audio_speaker_age_range TEXT",
        "ALTER TABLE ai_data ADD COLUMN audio_intoxication_indicator TEXT",
        "ALTER TABLE ai_data ADD COLUMN audio_sentiment TEXT",
        "ALTER TABLE ai_data ADD COLUMN audio_energy_db REAL",
        "ALTER TABLE ai_data ADD COLUMN audio_background_type TEXT",
        "ALTER TABLE ai_data ADD COLUMN audio_threat_score INTEGER",
        "ALTER TABLE ai_data ADD COLUMN audio_anomaly_score REAL",
        "ALTER TABLE ai_data ADD COLUMN audio_speech_rate REAL",
        "ALTER TABLE ai_data ADD COLUMN audio_language TEXT",
        "ALTER TABLE ai_data ADD COLUMN audio_keywords TEXT",
        "ALTER TABLE ai_data ADD COLUMN device_oui_vendor TEXT",
        "ALTER TABLE ai_data ADD COLUMN device_probe_ssids TEXT",
        "ALTER TABLE ai_data ADD COLUMN zone_presence TEXT",
        "ALTER TABLE ai_data ADD COLUMN face_match_confidence REAL",
        "ALTER TABLE ai_data ADD COLUMN illumination_band TEXT",
        "ALTER TABLE ai_data ADD COLUMN period_of_day_utc TEXT",
        "ALTER TABLE ai_data ADD COLUMN centroid_nx REAL",
        "ALTER TABLE ai_data ADD COLUMN centroid_ny REAL",
        "ALTER TABLE ai_data ADD COLUMN world_x REAL",
        "ALTER TABLE ai_data ADD COLUMN world_y REAL",
    ):
        try:
            c.execute(sql)
            c.commit()
        except sqlite3.OperationalError:
            pass
    # Indexes for list/export/retention (OPTIMIZATION_AUDIT)
    for sql in (
        "CREATE INDEX IF NOT EXISTS idx_ai_data_date_time ON ai_data(date, time)",
        "CREATE INDEX IF NOT EXISTS idx_ai_data_camera_date ON ai_data(camera_id, date, time)",
        "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_events_site_ts ON events(site_id, timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_ai_data_timestamp_utc ON ai_data(timestamp_utc)",
        "CREATE INDEX IF NOT EXISTS idx_events_timestamp_utc ON events(timestamp_utc)",
    ):
        try:
            c.execute(sql)
            c.commit()
        except sqlite3.OperationalError:
            pass

def _system_id():
    """Equipment/system identifier for chain of custody (NISTIR 8161, SWGDE)."""
    try:
        return os.environ.get('SYSTEM_ID') or platform.node() or 'vigil'
    except Exception:
        return 'vigil'

def _yolo_model_version():
    """AI model identifier for provenance (NIST AI 100-4)."""
    return os.environ.get('YOLO_MODEL', os.environ.get('YOLO_WEIGHTS', 'yolov8n.pt'))

# Canonical column order for ai_data integrity hash (reproducible verification).
_AI_DATA_HASH_ORDER = (
    'timestamp_utc', 'date', 'time', 'camera_id', 'system_id', 'model_version',
    'event', 'object', 'individual', 'facial_features', 'pose', 'emotion', 'scene',
    'license_plate', 'crowd_count', 'audio_event', 'device_mac', 'thermal_signature',
    'perceived_gender', 'perceived_age_range', 'hair_color', 'estimated_height_cm', 'build',
    'intoxication_indicator', 'drug_use_indicator', 'suspicious_behavior', 'predicted_intent',
    'stress_level', 'micro_expression', 'gait_notes', 'clothing_description',
    'threat_score', 'anomaly_score', 'attention_region', 'illumination_band', 'period_of_day_utc', 'centroid_nx', 'centroid_ny', 'world_x', 'world_y', 'perceived_ethnicity',
    'audio_transcription', 'audio_emotion', 'audio_stress_level', 'audio_speaker_gender', 'audio_speaker_age_range',
    'audio_intoxication_indicator', 'audio_sentiment', 'audio_energy_db', 'audio_background_type',
    'audio_threat_score', 'audio_anomaly_score', 'audio_speech_rate', 'audio_language', 'audio_keywords',
    'device_oui_vendor', 'device_probe_ssids', 'zone_presence', 'face_match_confidence',
)

# Canonical column order for ai_data CSV/export (matches standard schema header).
AI_DATA_EXPORT_COLUMNS = (
    'date', 'time', 'individual', 'facial_features', 'object', 'pose', 'emotion', 'scene',
    'license_plate', 'event', 'crowd_count', 'audio_event', 'device_mac', 'thermal_signature',
    'camera_id', 'timestamp_utc', 'model_version', 'system_id', 'integrity_hash',
    'perceived_gender', 'perceived_age_range', 'hair_color', 'estimated_height_cm', 'build',
    'intoxication_indicator', 'drug_use_indicator', 'suspicious_behavior', 'predicted_intent',
    'stress_level', 'micro_expression', 'gait_notes', 'clothing_description',
    'threat_score', 'anomaly_score', 'attention_region', 'illumination_band', 'period_of_day_utc', 'centroid_nx', 'centroid_ny', 'world_x', 'world_y', 'perceived_ethnicity',
    'audio_transcription', 'audio_emotion', 'audio_stress_level', 'audio_speaker_gender', 'audio_speaker_age_range',
    'audio_intoxication_indicator', 'audio_sentiment', 'audio_energy_db', 'audio_background_type',
    'audio_threat_score', 'audio_anomaly_score', 'audio_speech_rate', 'audio_language', 'audio_keywords',
    'device_oui_vendor', 'device_probe_ssids', 'zone_presence', 'face_match_confidence',
)

def _ai_data_integrity_hash(data):
    """Compute SHA-256 over canonical row payload for chain of custody."""
    parts = []
    for k in _AI_DATA_HASH_ORDER:
        v = data.get(k)
        parts.append(str(v) if v is not None else '')
    payload = '|'.join(parts)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def _event_integrity_hash(timestamp_utc, event_type, camera_id, site_id, metadata, severity):
    """Compute SHA-256 for event row (NISTIR 8161 / SWGDE chain of custody)."""
    payload = '|'.join(str(x) if x is not None else '' for x in (timestamp_utc, event_type, camera_id, site_id, metadata or '', severity))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def _db_path():
    """Database file path; use DATA_DIR if set (e.g. Docker /app/data)."""
    base = os.environ.get('DATA_DIR', '').strip()
    if base:
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, 'surveillance.db')
    return 'surveillance.db'


def get_conn():
    if not getattr(_db_local, 'conn', None):
        _db_local.conn = sqlite3.connect(_db_path())
        _db_local.conn.execute('PRAGMA journal_mode=WAL')
        _db_local.conn.execute('PRAGMA synchronous=NORMAL')
        _db_local.conn.execute('PRAGMA cache_size=-64000')  # ~64 MB
        _db_local.conn.execute('PRAGMA busy_timeout=5000')
        _init_schema(_db_local.conn)
    return _db_local.conn

def get_cursor():
    if not getattr(_db_local, 'cursor', None):
        _db_local.cursor = get_conn().cursor()
    return _db_local.cursor

# Bootstrap main thread DB and default data
get_conn()
try:
    cur = get_cursor()
    cur.execute("INSERT OR IGNORE INTO sites (id, name, map_url, timezone) VALUES ('default', 'Default Site', '', NULL)")
    for cid in _cameras.keys():
        cur.execute("INSERT OR IGNORE INTO camera_positions (camera_id, site_id, x, y, label) VALUES (?, 'default', ?, ?, ?)",
                   (cid, 0.2 + int(cid) * 0.3, 0.5, f'Camera {cid}'))
    get_conn().commit()
except Exception:
    pass

# Video recording state (shared across request threads; VideoWriter is not thread-safe)
is_recording = False
out = None
_recording_lock = threading.Lock()

# Recording gather config (what to record): event_types, capture_audio, capture_thermal, capture_wifi, ai_detail
_recording_config = {
    'event_types': ['motion', 'loitering', 'line_cross', 'fall'],
    'capture_audio': True,
    'capture_thermal': True,
    'capture_wifi': True,
    'ai_detail': 'full',  # 'full' | 'minimal'
}

# AI pipeline state for UI "how the AI is thinking" (research: transparency / interpretability)
_ai_pipeline_state = {
    'current_step': 'idle',
    'message': '',
    'steps': [],
    'timestamp': None,
    'last_event': None,
    'confidence_estimate': None,
}

# Temporal consistency (research: reduce false positives — require 2 of last 3 frames to agree)
_event_history = deque(maxlen=3)
# Event deduplication: same (event_type, camera_id) within 5s not re-inserted
_LAST_EVENT_DEDUPE_SEC = 5
_last_event_insert = {}  # (ev_type, camera_id) -> unix timestamp
_last_motion_time = 0.0  # for idle-skip: last time motion was detected

# Optional audio (PyAudio + SpeechRecognition) — extended: transcription + energy, duration for analysis
def _env_audio_enabled():
    raw = os.environ.get('ENABLE_AUDIO', '1').strip().lower()
    return raw in ('1', 'true', 'yes')
AUDIO_AVAILABLE = _env_audio_enabled()
_audio_capture_enabled = AUDIO_AVAILABLE  # runtime toggle (e.g. from fullscreen UI)
audio_result_queue = queue.Queue()
# Last result: str (legacy) or dict with keys text, energy_db, duration_sec for extended pipeline
audio_result = 'None'

def _audio_rms_to_db(rms, ref=1.0):
    """Convert RMS amplitude to approximate dB (ref 1.0). Avoid log(0)."""
    if rms is None or rms <= 0:
        return None
    try:
        return 20.0 * math.log10(max(rms / ref, 1e-10))
    except Exception:
        return None

def _audio_worker():
    """One-shot worker (legacy): single listen then exit."""
    global audio_result
    if not AUDIO_AVAILABLE:
        return
    try:
        import pyaudio  # type: ignore[reportMissingModuleSource]
        import speech_recognition as sr  # type: ignore[reportMissingImports]
        import struct
        audio = pyaudio.PyAudio()
        stream = audio.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source)
            try:
                audio_data = recognizer.listen(source, timeout=2)
                text = recognizer.recognize_google(audio_data)
                text = text if text else 'None'
                raw = audio_data.get_raw_data()
                duration_sec = len(raw) / (2.0 * audio_data.sample_rate) if raw and audio_data.sample_rate else None
                rms = None
                if raw and len(raw) >= 2:
                    try:
                        n = len(raw) // 2
                        samples = struct.unpack('{:d}h'.format(n), raw[:n * 2])
                        rms = (sum(s * s for s in samples) / n) ** 0.5 if n else 0
                        rms = rms / 32768.0
                    except Exception:
                        pass
                energy_db = _audio_rms_to_db(rms)
                audio_result = {
                    'text': text,
                    'energy_db': energy_db,
                    'duration_sec': duration_sec,
                }
            except Exception:
                audio_result = 'None'
        stream.stop_stream()
        stream.close()
        audio.terminate()
    except Exception:
        audio_result = 'None'


_audio_loop_running = False


def _audio_worker_loop():
    """Continuous speech-to-text: keep listening and updating audio_result so pipeline always has latest transcription."""
    global audio_result, _audio_loop_running
    if not AUDIO_AVAILABLE:
        return
    _audio_loop_running = True
    try:
        import pyaudio  # type: ignore[reportMissingModuleSource]
        import speech_recognition as sr  # type: ignore[reportMissingImports]
        import struct
        audio = pyaudio.PyAudio()
        stream = audio.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            while True:
                if not _audio_capture_enabled:
                    time.sleep(0.5)
                    continue
                try:
                    audio_data = recognizer.listen(source, timeout=2, phrase_time_limit=5)
                    text = recognizer.recognize_google(audio_data)
                    text = text if text else 'None'
                    raw = audio_data.get_raw_data()
                    duration_sec = len(raw) / (2.0 * audio_data.sample_rate) if raw and audio_data.sample_rate else None
                    rms = None
                    if raw and len(raw) >= 2:
                        try:
                            n = len(raw) // 2
                            samples = struct.unpack('{:d}h'.format(n), raw[:n * 2])
                            rms = (sum(s * s for s in samples) / n) ** 0.5 if n else 0
                            rms = rms / 32768.0
                        except Exception:
                            pass
                    energy_db = _audio_rms_to_db(rms)
                    audio_result = {'text': text, 'energy_db': energy_db, 'duration_sec': duration_sec}
                except Exception:
                    audio_result = 'None'
        stream.stop_stream()
        stream.close()
        audio.terminate()
    except Exception:
        audio_result = 'None'
    finally:
        _audio_loop_running = False


def get_audio_event():
    """Non-blocking: return last audio result (str for backward compat, or dict with text/energy_db/duration_sec)."""
    global audio_result
    if not AUDIO_AVAILABLE or not _audio_capture_enabled:
        return 'None'
    if not _audio_loop_running and (not hasattr(get_audio_event, '_thread') or not get_audio_event._thread.is_alive()):
        get_audio_event._thread = threading.Thread(target=_audio_worker_loop, daemon=True)
        get_audio_event._thread.start()
        time.sleep(0.3)
    try:
        return audio_result
    except Exception:
        return 'None'


# Keyword sets for audio sentiment/emotion/threat (same intensity as visual pipeline)
_AUDIO_THREAT_KEYWORDS = frozenset([
    'kill', 'bomb', 'gun', 'weapon', 'attack', 'hurt', 'destroy', 'fire', 'shoot', 'stab',
    'threat', 'threaten', 'die', 'dead', 'run', 'hide', 'help', 'emergency', 'police',
])
_AUDIO_NEGATIVE_KEYWORDS = frozenset([
    'angry', 'hate', 'stupid', 'wrong', 'bad', 'terrible', 'awful', 'no', 'stop', 'don\'t',
    'shut', 'leave', 'get out', 'fight', 'hit', 'scream', 'yell', 'cry', 'sad', 'scared',
])
_AUDIO_POSITIVE_KEYWORDS = frozenset([
    'happy', 'good', 'great', 'yes', 'thanks', 'love', 'nice', 'ok', 'okay', 'please', 'hello',
])
_AUDIO_STRESS_KEYWORDS = frozenset([
    'help', 'emergency', 'hurry', 'quick', 'scared', 'afraid', 'panic', 'anxious', 'stress',
])
_AUDIO_EMOTION_MAP = (
    (frozenset(['angry', 'mad', 'furious']), 'angry'),
    (frozenset(['sad', 'cry', 'crying', 'depressed']), 'sad'),
    (frozenset(['happy', 'joy', 'glad', 'love']), 'happy'),
    (frozenset(['scared', 'fear', 'afraid', 'panic']), 'fear'),
    (frozenset(['calm', 'quiet', 'peaceful']), 'calm'),
    (frozenset(['help', 'emergency']), 'distress'),
)


def _extract_audio_attributes(transcription, energy_db, duration_sec):
    """
    Extract extended audio attributes (same intensity as visual): sentiment, emotion, stress,
    threat/anomaly scores, speech rate, keywords. Speaker gender/age and intoxication are stubs
    for future voice models.
    """
    out = {}
    if not transcription or transcription == 'None':
        out['audio_transcription'] = 'None'
        out['audio_sentiment'] = 'neutral'
        out['audio_emotion'] = 'neutral'
        out['audio_stress_level'] = 'low'
        out['audio_threat_score'] = 0
        out['audio_anomaly_score'] = 0.0
        out['audio_speaker_gender'] = None
        out['audio_speaker_age_range'] = None
        out['audio_intoxication_indicator'] = 'none'
        out['audio_background_type'] = 'silence'
        out['audio_speech_rate'] = None
        out['audio_language'] = None
        out['audio_keywords'] = None
        if energy_db is not None:
            out['audio_energy_db'] = round(energy_db, 1)
        return out

    out['audio_transcription'] = transcription[:2000] if len(transcription) > 2000 else transcription
    words = [w.lower().strip(".,?!") for w in transcription.split() if w.strip()]
    word_set = frozenset(words)

    # Sentiment
    pos = sum(1 for w in _AUDIO_POSITIVE_KEYWORDS if w in word_set)
    neg = sum(1 for w in _AUDIO_NEGATIVE_KEYWORDS if w in word_set)
    threat_k = sum(1 for w in _AUDIO_THREAT_KEYWORDS if w in word_set)
    if threat_k > 0:
        out['audio_sentiment'] = 'threat'
    elif neg > pos:
        out['audio_sentiment'] = 'negative'
    elif pos > neg:
        out['audio_sentiment'] = 'positive'
    else:
        out['audio_sentiment'] = 'neutral'

    # Emotion from keywords
    out['audio_emotion'] = 'neutral'
    for kset, emo in _AUDIO_EMOTION_MAP:
        if kset & word_set:
            out['audio_emotion'] = emo
            break

    # Stress
    stress_k = sum(1 for w in _AUDIO_STRESS_KEYWORDS if w in word_set)
    if threat_k > 0 or stress_k >= 2:
        out['audio_stress_level'] = 'high'
    elif stress_k >= 1 or neg > 0:
        out['audio_stress_level'] = 'medium'
    else:
        out['audio_stress_level'] = 'low'

    # Threat score 0-100
    out['audio_threat_score'] = min(100, threat_k * 30 + stress_k * 15)

    # Anomaly from energy (very loud or very quiet) or threat
    out['audio_anomaly_score'] = 0.0
    if energy_db is not None:
        out['audio_energy_db'] = round(energy_db, 1)
        if energy_db > -20:
            out['audio_anomaly_score'] = 0.5
        elif energy_db < -55 and len(words) > 5:
            out['audio_anomaly_score'] = 0.3
    if threat_k > 0:
        out['audio_anomaly_score'] = max(out.get('audio_anomaly_score', 0), 0.7)

    # Background type heuristic
    if not words:
        out['audio_background_type'] = 'silence'
    elif energy_db is not None and energy_db < -50:
        out['audio_background_type'] = 'quiet_speech'
    elif energy_db is not None and energy_db > -25:
        out['audio_background_type'] = 'loud_speech_or_noise'
    else:
        out['audio_background_type'] = 'speech'

    # Speech rate (words per minute)
    if duration_sec and duration_sec > 0.1 and words:
        out['audio_speech_rate'] = round(len(words) / (duration_sec / 60.0), 1)
    else:
        out['audio_speech_rate'] = None

    out['audio_language'] = 'en'
    out['audio_keywords'] = ','.join(sorted(word_set & (_AUDIO_THREAT_KEYWORDS | _AUDIO_NEGATIVE_KEYWORDS | _AUDIO_POSITIVE_KEYWORDS | _AUDIO_STRESS_KEYWORDS))[:15]) if word_set else None
    if not out['audio_keywords']:
        out['audio_keywords'] = None

    out['audio_speaker_gender'] = None
    out['audio_speaker_age_range'] = None
    out['audio_intoxication_indicator'] = 'none'
    return out


def _detect_microphones():
    """List available audio input devices (microphones). Returns list of {index, name, sample_rate, channels} or [] if PyAudio unavailable."""
    try:
        import pyaudio  # type: ignore[reportMissingModuleSource]
        pa = pyaudio.PyAudio()
        devices = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get('maxInputChannels', 0) > 0:
                devices.append({
                    'index': i,
                    'name': info.get('name', f'Microphone {i}'),
                    'sample_rate': int(info.get('defaultSampleRate', 44100)),
                    'channels': info.get('maxInputChannels', 1),
                })
        pa.terminate()
        return devices
    except Exception:
        return []

# Optional Wi-Fi (Scapy) - monitor mode: log nearby device MACs, OUI vendor, probe-request SSIDs (identity tie-in)
WIFI_AVAILABLE = os.environ.get('ENABLE_WIFI_SNIFF', '0').lower() in ('1', 'true', 'yes')
_wifi_devices = set()
_wifi_probe_ssids = set()
_wifi_result = 'None'  # str (legacy) or dict with macs, oui_vendor, probe_ssids
_oui_cache = {}
MAX_NEARBY_MACS = int(os.environ.get('NEARBY_DEVICES_MAX_MACS', '10'))

def _oui_lookup(mac):
    """Resolve OUI (first 3 bytes) to vendor name. Cached; optional HTTP lookup (macvendors.com)."""
    if not mac or mac == 'None':
        return None
    mac_n = mac.replace('-', ':').upper().strip()
    oui_key = (mac_n + ':00:00:00')[:8]
    if oui_key in _oui_cache:
        return _oui_cache[oui_key]
    try:
        import urllib.request
        url = 'https://api.macvendors.com/' + urllib.request.quote(mac_n)
        req = urllib.request.Request(url, headers={'User-Agent': 'Vigil/1.0'})
        with urllib.request.urlopen(req, timeout=2) as r:
            vendor = r.read().decode('utf-8').strip() or None
        _oui_cache[oui_key] = vendor
        return vendor
    except Exception:
        _oui_cache[oui_key] = None
        return None

def _wifi_worker():
    global _wifi_result
    if not WIFI_AVAILABLE:
        return
    _wifi_devices.clear()
    _wifi_probe_ssids.clear()
    try:
        from scapy.all import sniff, Dot11, Dot11ProbeReq, Dot11Elt  # type: ignore[reportMissingImports]
        def packet_handler(pkt):
            if not pkt.haslayer(Dot11):
                return
            mac = getattr(pkt, 'addr2', None)
            if mac:
                _wifi_devices.add(mac)
            if pkt.haslayer(Dot11ProbeReq) and pkt.haslayer(Dot11Elt):
                elt = pkt.getlayer(Dot11Elt)
                while elt:
                    if getattr(elt, 'ID', None) == 0 and getattr(elt, 'info', None):
                        try:
                            ssid = (elt.info or b'').decode('utf-8', errors='ignore').strip()
                            if ssid and len(ssid) < 64:
                                _wifi_probe_ssids.add(ssid)
                        except Exception:
                            pass
                    elt = elt.payload.getlayer(Dot11Elt) if elt.payload else None
        sniff(iface=os.environ.get('WIFI_INTERFACE', 'wlan0mon'), prn=packet_handler, count=20, timeout=2)
        macs = list(_wifi_devices)[:MAX_NEARBY_MACS]
        probe_ssids = list(_wifi_probe_ssids)[:20]
        oui_vendor = _oui_lookup(macs[0]) if macs else None
        _wifi_result = {
            'macs': macs,
            'oui_vendor': oui_vendor,
            'probe_ssids': probe_ssids,
        }
    except Exception:
        _wifi_result = 'None'

def get_wifi_device():
    """Return last WiFi sniff result: str (one MAC, legacy) or dict with macs, oui_vendor, probe_ssids."""
    if not WIFI_AVAILABLE:
        return 'None'
    if not hasattr(get_wifi_device, '_thread') or not get_wifi_device._thread.is_alive():
        get_wifi_device._thread = threading.Thread(target=_wifi_worker, daemon=True)
        get_wifi_device._thread.start()
        return 'None'
    try:
        return _wifi_result
    except Exception:
        return 'None'

# Thermal: try flirpy (FLIR Lepton); no hardware = no thermal stream
thermal_frame = np.zeros((80, 60), dtype=np.uint8)
_thermal_capture = None
try:
    from flirpy.camera.lepton import Lepton  # type: ignore[reportMissingImports]
    _thermal_capture = Lepton()
except Exception:
    pass

# Motion detection: previous frame and threshold
_prev_frame = None
MOTION_THRESHOLD = 500
VEHICLE_CLASSES = {'car', 'truck', 'bus', 'motorcycle'}

# Loitering / line-crossing config (from config.json or defaults)
_analytics_config = {
    'loiter_zones': [[[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]],
    'loiter_seconds': 30,
    'crossing_lines': [[0.5, 0, 0.5, 1]],
    'privacy_preset': 'full',  # 'minimal' | 'full' — civilian ethics
    'home_away_mode': 'away',  # 'home' | 'away'
    'recording_signage_reminder': '',
    'privacy_policy_url': '',
}
_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
_config_dir = os.environ.get('CONFIG_DIR', '').strip()
if _config_dir:
    _alt = os.path.join(_config_dir, 'config.json')
    if os.path.isfile(_alt):
        _config_path = _alt
if os.path.isfile(_config_path):
    try:
        with open(_config_path) as f:
            _analytics_config.update(json.load(f))
    except Exception:
        pass

# Optional per-camera homography for world/floor-plane mapping (see docs/MAPPING_OPTIMIZATION_RESEARCH.md)
_homography_by_camera = {}
_homography_path = os.path.join(os.path.dirname(_config_path), 'homography.json')
if _config_dir:
    _homography_alt = os.path.join(_config_dir, 'homography.json')
    if os.path.isfile(_homography_alt):
        _homography_path = _homography_alt
if os.path.isfile(_homography_path):
    try:
        with open(_homography_path) as f:
            raw = json.load(f)
        for cam_id, h in (raw.items() if isinstance(raw, dict) else []):
            if isinstance(h, (list, tuple)) and len(h) >= 3 and isinstance(h[0], (list, tuple)) and len(h[0]) >= 3:
                _homography_by_camera[str(cam_id)] = [list(row[:3]) for row in h[:3]]
    except Exception:
        pass


def _apply_homography(camera_id, nx, ny):
    """Map normalized image point (nx, ny) to world plane (wx, wy) in [0,1] using per-camera 3x3 H. Returns (wx, wy) or (None, None)."""
    H = _homography_by_camera.get(str(camera_id)) if camera_id else None
    if not H or nx is None or ny is None:
        return None, None
    try:
        x = float(nx)
        y = float(ny)
        w = H[2][0] * x + H[2][1] * y + H[2][2]
        if abs(w) < 1e-9:
            return None, None
        wx = (H[0][0] * x + H[0][1] * y + H[0][2]) / w
        wy = (H[1][0] * x + H[1][1] * y + H[1][2]) / w
        wx = max(0.0, min(1.0, wx))
        wy = max(0.0, min(1.0, wy))
        return round(wx, 4), round(wy, 4)
    except (TypeError, IndexError, ZeroDivisionError):
        return None, None
_zone_ticks = {}  # zone_index -> consecutive cycles with person in zone
_prev_centroids = []  # for line-cross detection


def _point_in_polygon(px, py, poly):
    """Ray-cast: point inside polygon (poly list of (x,y))."""
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-9) + xi):
            inside = not inside
        j = i
    return inside


def _segment_crosses_line(p1, p2, line):
    """True if segment p1->p2 crosses line (x1,y1,x2,y2)."""
    x1, y1, x2, y2 = line
    ax, ay = p1
    bx, by = p2
    denom = (x2 - x1) * (by - ay) - (y2 - y1) * (bx - ax)
    if abs(denom) < 1e-9:
        return False
    t = ((x1 - ax) * (by - ay) - (y1 - ay) * (bx - ax)) / denom
    u = ((x1 - ax) * (y2 - y1) - (y1 - ay) * (x2 - x1)) / denom
    return 0 <= t <= 1 and 0 <= u <= 1


def _get_person_centroids(frame, results):
    """Return list of (cx, cy) for 'person' detections in pixel coords."""
    if not results or not results[0].boxes:
        return []
    h, w = frame.shape[:2]
    centroids = []
    names = results[0].names
    boxes = results[0].boxes
    for i, cls in enumerate(boxes.cls):
        if names.get(int(cls), '').lower() != 'person':
            continue
        xyxy = boxes.xyxy[i].cpu().numpy()
        cx = (xyxy[0] + xyxy[2]) / 2
        cy = (xyxy[1] + xyxy[3]) / 2
        centroids.append((float(cx), float(cy)))
    return centroids


def _get_primary_centroid_normalized(frame, results):
    """Return (nx, ny) in [0,1] for primary person (largest bbox), or (None, None). For spatial heatmaps (see docs/MAPPING_OPTIMIZATION_RESEARCH.md)."""
    if not results or not results[0].boxes or not frame.size:
        return None, None
    h, w = frame.shape[:2]
    if w <= 0 or h <= 0:
        return None, None
    names = results[0].names
    boxes = results[0].boxes
    best = None
    best_area = 0
    for i, cls in enumerate(boxes.cls):
        if names.get(int(cls), '').lower() != 'person':
            continue
        xyxy = boxes.xyxy[i].cpu().numpy()
        area = (xyxy[2] - xyxy[0]) * (xyxy[3] - xyxy[1])
        if area > best_area:
            best_area = area
            cx = (xyxy[0] + xyxy[2]) / 2
            cy = (xyxy[1] + xyxy[3]) / 2
            best = (float(cx), float(cy))
    if best is None:
        return None, None
    nx = max(0.0, min(1.0, best[0] / w))
    ny = max(0.0, min(1.0, best[1] / h))
    return nx, ny


def _detect_person_down(frame, results, results_pose):
    """
    Pose-based heuristic for person down (possible fall): single person, horizontal torso and/or
    wide bbox (width > height). Uses MediaPipe landmarks: shoulder (11,12) vs hip (23,24).
    Returns True if person-down pattern detected.
    """
    if not results or not results[0].boxes or not MEDIAPIPE_AVAILABLE or not results_pose or not getattr(results_pose, 'pose_landmarks', None):
        return False
    names = getattr(results[0], 'names', None) or {}
    boxes = results[0].boxes
    person_idxs = [i for i in range(len(boxes.cls)) if names.get(int(boxes.cls[i]), '').lower() == 'person']
    if len(person_idxs) != 1:
        return False
    idx = person_idxs[0]
    xyxy = boxes.xyxy[idx].cpu().numpy()
    w = xyxy[2] - xyxy[0]
    h = xyxy[3] - xyxy[1]
    if h <= 0:
        return False
    aspect = w / h
    # Horizontal bbox (lying) often has width > height
    bbox_horizontal = aspect >= 1.15
    lm = results_pose.pose_landmarks.landmark
    # MediaPipe: 0 nose, 11 left_shoulder, 12 right_shoulder, 23 left_hip, 24 right_hip (normalized 0-1, y down)
    if len(lm) < 25:
        return bbox_horizontal
    scy = (lm[11].y + lm[12].y) / 2
    hcy = (lm[23].y + lm[24].y) / 2
    scx = (lm[11].x + lm[12].x) / 2
    hcx = (lm[23].x + lm[24].x) / 2
    dy = hcy - scy
    dx = hcx - scx
    angle_rad = math.atan2(dy, dx)
    angle_deg = math.degrees(angle_rad)
    # Standing: torso roughly vertical => angle ~ 90° (hip below shoulder). Lying: torso horizontal => angle ~ 0 or ±180°
    torso_horizontal = abs(angle_deg) < 45 or abs(angle_deg) > 135
    return torso_horizontal or bbox_horizontal


def _gait_notes_from_pose(results_pose):
    """
    Derive simple gait/posture notes from pose landmarks (e.g. MediaPipe).
    Single-frame: posture (upright vs bent) and left/right symmetry. See docs/GAIT_AND_POSE_OPEN_SOURCE.md.
    Returns: 'normal' | 'bent_torso' | 'asymmetric' | 'bent_torso, asymmetric' | 'unknown'.
    """
    if not results_pose or not getattr(results_pose, 'pose_landmarks', None):
        return 'unknown'
    lm = results_pose.pose_landmarks.landmark
    if len(lm) < 25:
        return 'unknown'
    # MediaPipe indices 11,12 = shoulders; 23,24 = hips (normalized 0-1, y down)
    try:
        vis = getattr(lm[11], 'visibility', 1.0) or 1.0
    except (IndexError, AttributeError):
        return 'unknown'
    if vis < 0.5:
        return 'unknown'
    scy = (lm[11].y + lm[12].y) * 0.5
    hcy = (lm[23].y + lm[24].y) * 0.5
    scx = (lm[11].x + lm[12].x) * 0.5
    hcx = (lm[23].x + lm[24].x) * 0.5
    dy = hcy - scy
    dx = hcx - scx
    from_vertical = abs(abs(math.degrees(math.atan2(dy, dx))) - 90)
    bent = from_vertical > 25
    shoulder_diff = abs(lm[11].y - lm[12].y)
    hip_diff = abs(lm[23].y - lm[24].y)
    asymmetric = shoulder_diff > 0.06 or hip_diff > 0.06
    if bent and asymmetric:
        return 'bent_torso, asymmetric'
    if bent:
        return 'bent_torso'
    if asymmetric:
        return 'asymmetric'
    return 'normal'


def check_loiter_and_line_cross(frame, results):
    """Update zone ticks, check line cross. Returns (loiter_detected, line_cross_detected, zones_with_person)."""
    global _zone_ticks, _prev_centroids
    h, w = frame.shape[:2]
    centroids = _get_person_centroids(frame, results)
    zones = _analytics_config.get('loiter_zones', [])
    loiter_cycles = max(1, _analytics_config.get('loiter_seconds', 30) // 10)
    loiter_detected = False
    line_cross_detected = False
    zones_with_person = []
    # Scale zones to pixels
    for zi, poly in enumerate(zones):
        pixel_poly = [(p[0] * w, p[1] * h) for p in poly]
        any_in = any(_point_in_polygon(cx, cy, pixel_poly) for cx, cy in centroids)
        if any_in:
            zones_with_person.append(zi)
            _zone_ticks[zi] = _zone_ticks.get(zi, 0) + 1
            if _zone_ticks[zi] >= loiter_cycles:
                loiter_detected = True
                _zone_ticks[zi] = 0
        else:
            _zone_ticks[zi] = 0
    for line in _analytics_config.get('crossing_lines', []):
        x1, y1, x2, y2 = line[0] * w, line[1] * h, line[2] * w, line[3] * h
        line_pixel = (x1, y1, x2, y2)
        for curr in centroids:
            for prev in _prev_centroids:
                if _segment_crosses_line(prev, curr, line_pixel):
                    line_cross_detected = True
                    break
    _prev_centroids = centroids
    return loiter_detected, line_cross_detected, zones_with_person


def detect_motion(frame):
    global _prev_frame
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)
    if _prev_frame is None:
        _prev_frame = gray.copy()
        return False
    diff = cv2.absdiff(_prev_frame, gray)
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    count = int(np.sum(thresh) / 255)
    _prev_frame = gray.copy()
    return count > MOTION_THRESHOLD


_ENABLE_LPR_PREPROCESS = os.environ.get('ENABLE_LPR_PREPROCESS', '1').strip().lower() in ('1', 'true', 'yes')


def _lpr_preprocess(roi):
    """Preprocess vehicle ROI for OCR: grayscale, optional upscale, CLAHE, adaptive threshold, morph. Improves LPR accuracy (research: MDPI, arXiv)."""
    if roi is None or roi.size == 0:
        return None
    h, w = roi.shape[:2]
    if w < 40 or h < 12:
        roi = cv2.resize(roi, (max(80, w * 2), max(24, h * 2)), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
    try:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
    except Exception:
        pass
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    kernel = np.ones((2, 2), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    return thresh


def lpr_on_vehicle_roi(frame, results):
    if not results or not results[0].boxes:
        return 'N/A'
    names = results[0].names
    boxes = results[0].boxes
    for i, cls in enumerate(boxes.cls):
        name = names.get(int(cls), '')
        if name.lower() in VEHICLE_CLASSES:
            xyxy = boxes.xyxy[i].cpu().numpy()
            x1, y1, x2, y2 = map(int, xyxy)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
            if x2 <= x1 or y2 <= y1:
                continue
            roi = frame[y1:y2, x1:x2]
            if _ENABLE_LPR_PREPROCESS:
                roi = _lpr_preprocess(roi)
            if roi is None:
                continue
            try:
                text = pytesseract.image_to_string(roi).strip()
                text = ''.join(c for c in text if c.isalnum() or c.isspace())[:20]
                return text if text else 'N/A'
            except Exception:
                return 'N/A'
    return 'N/A'


# Lazy-loaded emotion recognizer (EmotiEffLib) for TensorFlow-free option
_emotieff_recognizer = None


def _get_dominant_emotion(frame, results=None):
    """Unified emotion from DeepFace (TensorFlow) or EmotiEffLib (PyTorch/ONNX). Returns a single label e.g. Neutral, Happy."""
    backend = (os.environ.get('EMOTION_BACKEND') or 'auto').strip().lower()
    # Prefer DeepFace if explicitly set and available
    if (backend == 'deepface' or backend == 'auto') and DEEPFACE_AVAILABLE and DeepFace:
        try:
            out = DeepFace.analyze(frame, actions=['emotion'])
            if out and isinstance(out, list):
                out = out[0]
            if isinstance(out, dict) and 'dominant_emotion' in out:
                return out['dominant_emotion']
        except Exception:
            pass
    # Prefer EmotiEffLib (no TensorFlow) when set or when DeepFace not available
    if (backend == 'emotiefflib' or (backend == 'auto' and not (DEEPFACE_AVAILABLE and DeepFace))) and EMOTIEFFLIB_AVAILABLE and EmotiEffLibRecognizer:
        global _emotieff_recognizer
        try:
            if _emotieff_recognizer is None and _emotieff_get_models:
                models = _emotieff_get_models()
                if models:
                    _emotieff_recognizer = EmotiEffLibRecognizer(device='cpu', model_name=models[0])
            if _emotieff_recognizer is not None:
                # Optionally crop to first person bbox for better accuracy
                crop = frame
                if results and results[0].boxes and hasattr(results[0], 'names'):
                    names, boxes = results[0].names, results[0].boxes
                    for i, cls in enumerate(boxes.cls):
                        if names.get(int(cls), '').lower() == 'person':
                            xyxy = boxes.xyxy[i].cpu().numpy()
                            x1, y1, x2, y2 = map(int, xyxy)
                            h, w = frame.shape[:2]
                            pad = 20
                            x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
                            x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
                            if x2 > x1 and y2 > y1 and (y2 - y1) >= 30 and (x2 - x1) >= 30:
                                crop = frame[y1:y2, x1:x2]
                            break
                # EmotiEffLib often expects RGB; OpenCV frame is BGR
                rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                pred = _emotieff_recognizer.predict_emotions([rgb])
                if pred and len(pred) and pred[0]:
                    probs = pred[0] if isinstance(pred[0], dict) else pred[0][0] if isinstance(pred[0], (list, tuple)) else None
                    if isinstance(probs, dict):
                        return max(probs, key=probs.get)
                    if isinstance(pred[0], str):
                        return pred[0]
        except Exception:
            pass
    return 'Neutral'


def _get_face_embedding(frame_or_crop):
    """Return face embedding as numpy float32 array or None. Uses DeepFace.represent (one face). Edge-only; no cloud."""
    if not DEEPFACE_AVAILABLE or not DeepFace:
        return None
    try:
        out = DeepFace.represent(frame_or_crop, enforce_detection=False)
        if out and isinstance(out, list) and len(out) and isinstance(out[0], dict) and 'embedding' in out[0]:
            emb = out[0]['embedding']
            return np.array(emb, dtype=np.float32) if not isinstance(emb, np.ndarray) else emb.astype(np.float32)
    except Exception:
        pass
    return None


def _match_watchlist(embedding):
    """Compare embedding to watchlist_faces. Returns (name, confidence 0-1) or (None, 0.0). Cosine similarity."""
    if embedding is None or not embedding.size:
        return None, 0.0
    try:
        get_cursor().execute('SELECT id, name, embedding FROM watchlist_faces')
        rows = get_cursor().fetchall()
    except sqlite3.OperationalError:
        return None, 0.0
    best_name, best_sim = None, 0.0
    for row in rows:
        _, name, blob = row
        if not blob:
            continue
        ref = np.frombuffer(blob, dtype=np.float32)
        if ref.shape != embedding.shape:
            continue
        norm = np.linalg.norm(embedding) * np.linalg.norm(ref)
        if norm <= 0:
            continue
        sim = float(np.dot(embedding, ref) / norm)
        sim = (sim + 1) / 2.0  # map [-1,1] to [0,1] for confidence
        if sim > best_sim:
            best_sim = sim
            best_name = name
    return best_name, best_sim


def _apply_watchlist(frame, data, results):
    """If ENABLE_WATCHLIST and DeepFace available, get face embedding, match watchlist, set data['individual'] and face_match_confidence."""
    if os.environ.get('ENABLE_WATCHLIST', '').strip().lower() not in ('1', 'true', 'yes') or not DEEPFACE_AVAILABLE or not DeepFace:
        return
    threshold = float(os.environ.get('WATCHLIST_SIMILARITY_THRESHOLD', '0.6'))
    crop = frame
    if results and results[0].boxes and hasattr(results[0], 'names'):
        names, boxes = results[0].names, results[0].boxes
        for i, cls in enumerate(boxes.cls):
            if names.get(int(cls), '').lower() == 'person':
                xyxy = boxes.xyxy[i].cpu().numpy()
                x1, y1, x2, y2 = map(int, xyxy)
                h, w = frame.shape[:2]
                pad = 20
                x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
                x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
                if x2 > x1 and y2 > y1 and (y2 - y1) >= 40 and (x2 - x1) >= 40:
                    crop = frame[y1:y2, x1:x2]
                break
    emb = _get_face_embedding(crop)
    name, confidence = _match_watchlist(emb)
    if name and confidence >= threshold:
        data['individual'] = name
        data['face_match_confidence'] = round(confidence, 4)
    elif emb is not None:
        data['individual'] = 'Stranger'
        data['face_match_confidence'] = round(confidence, 4)


def _dominant_color_region(img_bgr, name=''):
    """Return a simple color name from dominant BGR region. Used for hair/clothing heuristics.
    For name=='hair', uses HSV-based logic for better discrimination: black, dark_brown, brown,
    light_brown, blonde, red, auburn, gray, white."""
    if img_bgr is None or img_bgr.size == 0:
        return None
    try:
        h, w = img_bgr.shape[:2]
        if h < 5 or w < 5:
            return None
        b, g, r = np.mean(img_bgr[:, :, 0]), np.mean(img_bgr[:, :, 1]), np.mean(img_bgr[:, :, 2])
        gray = (b + g + r) / 3
        if name == 'hair':
            # Hair-specific: use HSV for better separation of browns, blonde, red, gray
            hsv = cv2.cvtColor(
                np.array([[[int(b), int(g), int(r)]]], dtype=np.uint8), cv2.COLOR_BGR2HSV
            )
            H, S, V = int(hsv[0, 0, 0]), int(hsv[0, 0, 1]), int(hsv[0, 0, 2])
            if V < 45:
                return 'black'
            if V > 220 and S < 40:
                return 'white'
            if S < 35 and 80 < V < 200:
                return 'gray'
            if S < 25 and V >= 200:
                return 'gray'
            # Red / auburn: H in 0–15 or 165–180
            if (H <= 15 or H >= 165) and S > 80 and r > g and r > b:
                return 'auburn' if V < 120 else 'red'
            # Blonde: high V, medium S, H in yellow range (20–45)
            if 20 <= H <= 45 and S < 120 and V > 160:
                return 'blonde'
            # Light brown: yellow-orange, medium V
            if 15 <= H <= 35 and 100 < V < 180 and S > 50:
                return 'light_brown'
            # Brown / dark brown: low H (brown is low saturation orange), low–mid V
            if (H <= 25 or (H >= 160 and S > 60)) and S > 40:
                return 'dark_brown' if V < 100 else 'brown'
            if 25 < H <= 45 and 80 < V < 160 and S > 50:
                return 'brown'
            if gray < 70:
                return 'black'
            if gray > 200 and S < 50:
                return 'white'
            if abs(r - g) < 35 and abs(g - b) < 35:
                return 'gray'
            return 'brown' if 50 < gray < 180 else 'unknown'
        # Clothing / generic
        if gray < 50:
            return 'black'
        if gray > 200:
            return 'white'
        if r > g and r > b and r - min(g, b) > 40:
            return 'red'
        if b > r and b > g and b - min(r, g) > 40:
            return 'blue'
        if g > r and g > b and g - min(r, b) > 40:
            return 'green'
        if abs(r - g) < 30 and abs(g - b) < 30:
            return 'gray'
        if r > 120 and g > 80 and b < 80:
            return 'brown'
        return 'unknown'
    except Exception:
        return None


def _extract_extended_attributes(frame, results, pose, emotion, event, results_pose=None):
    """
    Extract extended person attributes for logs/behaviors: demographic proxies (optional),
    physical (height, build, hair, clothing), behavioral (suspicious, intent, stress),
    intoxication/gait stubs, and sci-fi style scores. Speed-optimized: single DeepFace
    call when enabled, rest are heuristics from existing YOLO/pose/emotion.
    results_pose: optional pose result (e.g. MediaPipe) to derive gait_notes from landmarks.
    """
    out = {}
    enable_extended = os.environ.get('ENABLE_EXTENDED_ATTRIBUTES', '1').strip().lower() in ('1', 'true', 'yes')
    enable_sensitive = os.environ.get('ENABLE_SENSITIVE_ATTRIBUTES', '0').strip().lower() in ('1', 'true', 'yes')

    # Person bbox: use same primary person as centroid (largest by area) for consistent height/hair/clothing
    person_bbox = None
    if results and results[0].boxes and hasattr(results[0], 'names'):
        names, boxes = results[0].names, results[0].boxes
        best_area = 0
        for i, cls in enumerate(boxes.cls):
            if names.get(int(cls), '').lower() != 'person':
                continue
            xyxy = boxes.xyxy[i].cpu().numpy()
            area = (xyxy[2] - xyxy[0]) * (xyxy[3] - xyxy[1])
            if area > best_area:
                best_area = area
                person_bbox = (int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3]))

    if person_bbox:
        x1, y1, x2, y2 = person_bbox
        bh, bw = y2 - y1, x2 - x1
        frame_h, frame_w = frame.shape[:2]
        # Estimated height: scale with frame so resolution-independent; ~170cm when person fills ~0.45 of frame height
        ref_px = max(100, frame_h * 0.45)
        if bh >= 30:
            out['estimated_height_cm'] = int(170 * (bh / ref_px))
            out['estimated_height_cm'] = max(120, min(220, out['estimated_height_cm']))
        # Build from aspect: width/height of bbox (wider = heavier)
        if bh > 20:
            ar = bw / float(bh)
            if ar < 0.35:
                out['build'] = 'slim'
            elif ar > 0.5:
                out['build'] = 'heavy'
            else:
                out['build'] = 'medium'
        # Hair: dominant color in top 25% of person (head)
        head_y2 = y1 + max(10, int(bh * 0.25))
        if head_y2 > y1 and x2 > x1:
            head_roi = frame[y1:head_y2, x1:x2]
            out['hair_color'] = _dominant_color_region(head_roi, 'hair') or 'unknown'
        # Clothing: dominant color lower 2/3 of body
        body_y1 = y1 + int(bh * 0.3)
        if body_y1 < y2 and x2 > x1:
            body_roi = frame[body_y1:y2, x1:x2]
            color = _dominant_color_region(body_roi, 'clothing')
            out['clothing_description'] = (color + ' top/body') if color else 'unknown'
    else:
        out['build'] = 'unknown'
        out['hair_color'] = 'unknown'
        out['clothing_description'] = 'unknown'

    # Behavioral from event (and pose when event is None)
    if event == 'Fall Detected':
        out['suspicious_behavior'] = 'person_down'
        out['predicted_intent'] = 'fall_or_collapse'
        out['anomaly_score'] = 0.7
    elif event == 'Loitering Detected':
        out['suspicious_behavior'] = 'loitering'
        out['predicted_intent'] = 'loitering'
        out['anomaly_score'] = 0.5
    elif event == 'Line Crossing Detected':
        out['suspicious_behavior'] = 'line_crossing'
        out['predicted_intent'] = 'crossing'
        out['anomaly_score'] = 0.6
    elif event == 'Motion Detected':
        out['suspicious_behavior'] = 'none'
        out['predicted_intent'] = 'passing'
        out['anomaly_score'] = 0.0
    elif event == 'None' or not event:
        out['suspicious_behavior'] = 'none'
        out['predicted_intent'] = 'standing' if pose == 'Standing' else ('present' if pose == 'Person down' else 'unknown')
        out['anomaly_score'] = 0.0
    else:
        out['suspicious_behavior'] = 'none'
        out['predicted_intent'] = 'unknown'
        out['anomaly_score'] = 0.0

    # Stress from emotion (research: stress correlates with negative emotion)
    if emotion in ('Angry', 'Fear', 'Sad', 'Disgust'):
        out['stress_level'] = 'high'
    elif emotion in ('Surprise',):
        out['stress_level'] = 'medium'
    else:
        out['stress_level'] = 'low'

    # Intoxication / drug: stubs (would need temporal gait or behavioral model)
    out['intoxication_indicator'] = 'none'
    out['drug_use_indicator'] = 'none'
    out['gait_notes'] = _gait_notes_from_pose(results_pose) if (_is_gait_notes_enabled() and results_pose) else 'unknown'

    # Threat score 0-100 heuristic (suspicious_behavior already set for Fall/loiter/line_cross)
    threat = 0
    if out.get('suspicious_behavior') not in ('none', None):
        threat += 25
    if out.get('suspicious_behavior') == 'person_down':
        threat += 25
    if out.get('stress_level') == 'high':
        threat += 20
    if event == 'Loitering Detected':
        threat += 15
    out['threat_score'] = min(100, threat)

    # Illumination and time period (no extra inference)
    if frame is not None and frame.size > 0:
        mean_val = float(np.mean(frame))
        if mean_val < 80:
            out['illumination_band'] = 'dark'
        elif mean_val < 120:
            out['illumination_band'] = 'dim'
        elif mean_val < 180:
            out['illumination_band'] = 'normal'
        else:
            out['illumination_band'] = 'bright'
    else:
        out['illumination_band'] = None
    hour_utc = time.gmtime().tm_hour
    if 0 <= hour_utc < 5 or hour_utc >= 21:
        out['period_of_day_utc'] = 'night'
    elif 5 <= hour_utc < 7:
        out['period_of_day_utc'] = 'dawn'
    elif 7 <= hour_utc < 17:
        out['period_of_day_utc'] = 'day'
    else:
        out['period_of_day_utc'] = 'dusk'

    # Micro-expression: reuse emotion for now (real MER needs dedicated model)
    out['micro_expression'] = emotion or 'neutral'
    # Person position in frame (left/center/right, top/middle/bottom) from bbox center; "attention_region" until gaze model
    if person_bbox and frame is not None and frame.size > 0:
        x1, y1, x2, y2 = person_bbox
        h, w = frame.shape[:2]
        if w > 0 and h > 0:
            cx = (x1 + x2) * 0.5 / w
            cy = (y1 + y2) * 0.5 / h
            hzone = 'left' if cx < 0.33 else ('right' if cx > 0.67 else 'center')
            vzone = 'top' if cy < 0.33 else ('bottom' if cy > 0.67 else 'middle')
            out['attention_region'] = '%s,%s' % (hzone, vzone)
        else:
            out['attention_region'] = 'unknown'
    else:
        out['attention_region'] = 'unknown'

    # DeepFace: age, gender (and optionally race) when enabled - single call for speed
    if enable_extended and frame is not None and frame.size > 0:
        try:
            actions = ['age', 'gender']
            if enable_sensitive:
                actions.append('race')
            if DEEPFACE_AVAILABLE and DeepFace:
                crop = frame
                if person_bbox:
                    x1, y1, x2, y2 = person_bbox
                    h, w = frame.shape[:2]
                    pad = 20
                    x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
                    x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
                    if x2 > x1 and y2 > y1 and (y2 - y1) >= 40:
                        crop = frame[y1:y2, x1:x2]
                df_out = DeepFace.analyze(crop, actions=actions, enforce_detection=False)
                if df_out and isinstance(df_out, list):
                    df_out = df_out[0]
                if isinstance(df_out, dict):
                    if 'dominant_gender' in df_out:
                        out['perceived_gender'] = df_out['dominant_gender']
                    if 'age' in df_out:
                        age = int(df_out['age'])
                        if age < 18:
                            out['perceived_age_range'] = '0-17'
                        elif age < 30:
                            out['perceived_age_range'] = '18-29'
                        elif age < 45:
                            out['perceived_age_range'] = '30-44'
                        elif age < 60:
                            out['perceived_age_range'] = '45-59'
                        else:
                            out['perceived_age_range'] = '60+'
                    if enable_sensitive and 'dominant_race' in df_out:
                        out['perceived_ethnicity'] = df_out['dominant_race']
        except Exception:
            pass

    if not out.get('perceived_gender'):
        out['perceived_gender'] = None
    if not out.get('perceived_age_range'):
        out['perceived_age_range'] = None
    if not enable_sensitive:
        out['perceived_ethnicity'] = None

    return out


def _placeholder_frame_jpeg():
    """Return a single 'No signal' placeholder as JPEG bytes for MJPEG stream when camera is unavailable."""
    w, h = 640, 480
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:] = (40, 40, 40)
    try:
        cv2.putText(img, 'No signal', (w // 2 - 80, h // 2 - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (120, 120, 120), 2)
        cv2.putText(img, 'Camera unavailable or not connected', (w // 2 - 180, h // 2 + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 80, 80), 1)
    except Exception:
        pass
    ret, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, _stream_jpeg_quality])
    return buffer.tobytes() if ret else b''


def _enhance_frame(frame):
    """Optional low-light (CLAHE + gamma) and clarity (sharpening). Applied when ENHANCE_VIDEO / ENHANCE_LOW_LIGHT / ENHANCE_CLARITY are set."""
    if not (_enable_low_light or _enable_clarity) or frame is None or frame.size == 0:
        return frame
    out = frame.copy()
    try:
        if _enable_low_light and _clahe is not None:
            lab = cv2.cvtColor(out, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            l = _clahe.apply(l)
            lab = cv2.merge([l, a, b])
            out = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            if _enhance_gamma != 1.0 and _enhance_gamma > 0:
                inv_gamma = 1.0 / _enhance_gamma
                table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype(np.uint8)
                out = cv2.LUT(out, table)
        if _enable_clarity:
            blurred = cv2.GaussianBlur(out, (0, 0), 1.0)
            out = cv2.addWeighted(out, 1.4, blurred, -0.4, 0)
            out = np.clip(out, 0, 255).astype(np.uint8)
    except Exception:
        pass
    return out


def gen_frames(camera_id='0'):
    global is_recording, out
    cap = _cameras.get(camera_id, camera)
    placeholder = _placeholder_frame_jpeg()
    if not placeholder:
        placeholder = (b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff'
                     b'\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xd9')  # minimal 1x1 JPEG fallback
    boundary = b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
    while True:
        frame_bytes = None
        if cap is not None and cap.isOpened():
            success, frame = cap.read()
            if success:
                _camera_last_frame_time[camera_id] = time.time()
                frame = _enhance_frame(frame)
                if is_recording:
                    rec_size = (1280, 720)
                    with _recording_lock:
                        if out is None:
                            fourcc = cv2.VideoWriter_fourcc(*'XVID')
                            rec_path = os.path.join(_recordings_dir(), 'recording_%d.avi' % int(time.time()))
                            out = cv2.VideoWriter(rec_path, fourcc, 20.0, rec_size)
                    if out is not None and frame is not None and frame.size > 0:
                        h, w = frame.shape[:2]
                        if (w, h) != rec_size:
                            rec_frame = cv2.resize(frame, rec_size, interpolation=cv2.INTER_AREA)
                        else:
                            rec_frame = np.ascontiguousarray(frame) if not frame.flags['C_CONTIGUOUS'] else frame
                        # Validate to avoid SIGSEGV in OpenCV/FFmpeg (null or invalid buffer)
                        ok = (
                            isinstance(rec_frame, np.ndarray)
                            and rec_frame.dtype == np.uint8
                            and rec_frame.ndim == 3
                            and rec_frame.shape == (rec_size[1], rec_size[0], 3)
                            and rec_frame.flags['C_CONTIGUOUS']
                        )
                        if ok:
                            try:
                                with _recording_lock:
                                    out.write(rec_frame.copy())
                            except Exception:
                                pass  # avoid process crash on VideoWriter/FFmpeg errors (e.g. Python 3.14 + opencv/ffmpeg on macOS)
                # Optional resize for lighter stream (recording stays full res)
                encode_frame = frame
                if _stream_max_width > 0 and frame.shape[1] > _stream_max_width:
                    h, w = frame.shape[:2]
                    new_w = _stream_max_width
                    new_h = int(h * new_w / w)
                    encode_frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                ret, buffer = cv2.imencode('.jpg', encode_frame, [cv2.IMWRITE_JPEG_QUALITY, _stream_jpeg_quality])
                if ret:
                    frame_bytes = buffer.tobytes()
        if frame_bytes is None:
            frame_bytes = placeholder
            time.sleep(0.5)
        yield boundary + frame_bytes + b'\r\n'


def gen_thermal_frames():
    global thermal_frame
    no_sensor_placeholder = np.zeros((80, 60), dtype=np.uint8)  # solid black when no hardware
    while True:
        if _thermal_capture is not None:
            try:
                thermal_frame = _thermal_capture.grab()
                if thermal_frame is None:
                    thermal_frame = no_sensor_placeholder
                elif thermal_frame.ndim == 3:
                    thermal_frame = thermal_frame[:, :, 0] if thermal_frame.shape[2] else np.zeros((80, 60), dtype=np.uint8)
            except Exception:
                thermal_frame = no_sensor_placeholder
        else:
            thermal_frame = no_sensor_placeholder
        img = PIL.Image.fromarray(thermal_frame.astype(np.uint8))
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        frame = buffer.getvalue()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


def analyze_thermal():
    return 'Human' if np.mean(thermal_frame) > 100 else 'None'


# Predictive threat: optional integration with proactive.predictor (rule_based_threat) for live pipeline
def _apply_predictive_threat(data, event, timestamp_utc):
    """Apply proactive predictor rule-based escalation to data (threat_score, predicted_intent). No-op if proactive not available."""
    try:
        from proactive.predictor import rule_based_threat  # type: ignore[import-untyped]
    except ImportError:
        return
    dwell_seconds = max(_zone_ticks.values(), default=0) * ANALYZE_INTERVAL_SECONDS
    anomaly = data.get('anomaly_score')
    if anomaly is not None and not isinstance(anomaly, (int, float)):
        try:
            anomaly = float(anomaly)
        except (TypeError, ValueError):
            anomaly = None
    threat_in = data.get('threat_score')
    if threat_in is not None and not isinstance(threat_in, (int, float)):
        try:
            threat_in = int(threat_in) if isinstance(threat_in, str) and threat_in.isdigit() else float(threat_in)
        except (TypeError, ValueError):
            threat_in = 0
    escalated, flags = rule_based_threat(
        dwell_seconds, timestamp_utc, event, anomaly, None, threat_in,
    )
    data['threat_score'] = min(100, int(escalated))
    if 'high_risk_combination' in flags or escalated >= 70:
        data['predicted_intent'] = 'aggressive'
    elif 'loitering_long' in flags or 'scouting' in str(flags).lower():
        data['predicted_intent'] = 'scouting'
    elif 'nighttime' in flags and data.get('predicted_intent') == 'unknown':
        data['predicted_intent'] = 'scouting'
    elif dwell_seconds < 60 and escalated < 20:
        data['predicted_intent'] = 'passing'
    else:
        data['predicted_intent'] = data.get('predicted_intent') or 'normal'


# Notable behavior screenshots: capture frame and log reason when research-backed notable behaviors are detected
NOTABLE_SCREENSHOTS_DIR = os.environ.get('NOTABLE_SCREENSHOTS_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'notable_screenshots')
NOTABLE_COOLDOWN_SECONDS = int(os.environ.get('NOTABLE_COOLDOWN_SECONDS', '60'))
NOTABLE_CROWD_THRESHOLD = int(os.environ.get('NOTABLE_CROWD_THRESHOLD', '5'))
NOTABLE_THREAT_THRESHOLD = int(os.environ.get('NOTABLE_THREAT_THRESHOLD', '50'))
_notable_cooldown = {}  # reason -> last capture timestamp


def _is_notable_behavior(data, event):
    """
    Determine if current frame/context is a notable behavior worthy of a screenshot and log.
    Based on research: loitering, line crossing, elevated threat, high stress/negative emotion,
    audio threat, behavioral anomaly, crowding (VMS/security literature).
    Returns (reason_slug, reason_detail) or (None, None).
    """
    if not data:
        return None, None
    threat = data.get('threat_score') or 0
    stress = (data.get('stress_level') or '').lower()
    emotion = data.get('emotion') or ''
    anomaly = data.get('anomaly_score')
    if anomaly is None:
        anomaly = 0.0
    crowd = data.get('crowd_count') or 0
    audio_threat = data.get('audio_threat_score') or 0
    suspicious = data.get('suspicious_behavior') or ''

    if event == 'Loitering Detected':
        return 'loitering', 'Person remained in zone beyond threshold (VMS loitering detection).'
    if event == 'Line Crossing Detected':
        return 'line_crossing', 'Virtual line crossing detected (perimeter/rule violation).'
    if data.get('pose') == 'Person down':
        return 'person_down', 'Person down detected (pose heuristic; possible fall).'
    if threat >= NOTABLE_THREAT_THRESHOLD:
        return 'elevated_threat', 'Threat score %d; suspicious behavior or high stress (security-relevant).' % threat
    if stress == 'high' and emotion in ('Angry', 'Fear', 'Sad', 'Disgust'):
        return 'high_stress_negative_emotion', 'High stress with negative emotion (%s); potential distress or aggression.' % emotion
    if audio_threat >= NOTABLE_THREAT_THRESHOLD:
        return 'audio_threat', 'Threat or distress keywords in audio (audio_threat_score %d).' % audio_threat
    if anomaly >= 0.5:
        return 'behavioral_anomaly', 'Behavioral anomaly score %.2f (loiter/line cross or deviation).' % anomaly
    if crowd >= NOTABLE_CROWD_THRESHOLD:
        return 'crowding', 'Crowd count %d (potential crowding; safety/capacity).' % crowd
    if suspicious and suspicious != 'none':
        return 'suspicious_behavior', 'Suspicious behavior: %s (logged for review).' % suspicious
    return None, None


def _capture_notable_screenshot(frame, reason, reason_detail, camera_id, event_id, timestamp_utc):
    """Save frame as JPEG to NOTABLE_SCREENSHOTS_DIR and return relative path, or None on failure."""
    try:
        os.makedirs(NOTABLE_SCREENSHOTS_DIR, exist_ok=True)
        safe_ts = (timestamp_utc or time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())).replace(':', '-').replace('Z', 'Z')
        filename = 'notable_%s_%s.jpg' % (safe_ts, reason)
        filepath = os.path.join(NOTABLE_SCREENSHOTS_DIR, filename)
        if frame is not None and frame.size > 0:
            cv2.imwrite(filepath, frame)
        else:
            return None
        return os.path.join(os.path.basename(NOTABLE_SCREENSHOTS_DIR), filename)
    except Exception:
        return None


def _maybe_capture_notable(frame, data, event, camera_id, event_id, timestamp_utc):
    """If behavior is notable and cooldown expired, capture screenshot and log to DB."""
    reason, detail = _is_notable_behavior(data, event)
    if not reason:
        return
    now = time.time()
    if _notable_cooldown.get(reason, 0) + NOTABLE_COOLDOWN_SECONDS > now:
        return
    _notable_cooldown[reason] = now
    rel_path = _capture_notable_screenshot(frame, reason, detail, camera_id, event_id, timestamp_utc)
    if not rel_path:
        return
    try:
        get_cursor().execute(
            '''INSERT INTO notable_screenshots (timestamp_utc, reason, reason_detail, file_path, camera_id, event_id)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (timestamp_utc, reason, detail, rel_path, camera_id or '0', event_id)
        )
        get_conn().commit()
    except Exception:
        pass


def _update_pipeline_state(step, message, detail=None, confidence=None):
    """Update shared pipeline state for UI (how the AI is thinking)."""
    global _ai_pipeline_state
    ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    if not _ai_pipeline_state.get('steps'):
        _ai_pipeline_state['steps'] = []
    _ai_pipeline_state['current_step'] = step
    _ai_pipeline_state['message'] = message
    _ai_pipeline_state['timestamp'] = ts
    if confidence is not None:
        _ai_pipeline_state['confidence_estimate'] = confidence
    step_entry = {'name': step, 'status': 'done', 'detail': detail or message, 'timestamp': ts, 'confidence_estimate': confidence}
    existing = [s for s in _ai_pipeline_state['steps'] if s.get('name') == step]
    if existing:
        _ai_pipeline_state['steps'] = [s for s in _ai_pipeline_state['steps'] if s.get('name') != step]
    _ai_pipeline_state['steps'].append(step_entry)
    if len(_ai_pipeline_state['steps']) > 12:
        _ai_pipeline_state['steps'] = _ai_pipeline_state['steps'][-12:]


def analyze_frame():
    global is_recording, _event_history, _last_event_insert, _last_motion_time
    while True:
        try:
            if is_recording:
                success, frame = camera.read()
                if success:
                    _update_pipeline_state('object_detection', 'Running object detection…', None, None)
                    results = yolo_model.predict(frame, imgsz=_yolo_imgsz, conf=_yolo_conf, verbose=False) if yolo_model else None
                    if results and results[0].boxes:
                        _filter_yolo_results(results)
                    objects = [results[0].names[int(cls)] for cls in results[0].boxes.cls] if results and results[0].boxes else []
                    max_conf = float(results[0].boxes.conf.max()) if results and results[0].boxes and hasattr(results[0].boxes, 'conf') and results[0].boxes.conf.numel() else 0.0
                    obj_detail = ', '.join(objects[:3]) if objects else 'none'
                    _update_pipeline_state('object_detection', 'Objects: %s' % (obj_detail or 'none'), obj_detail, max_conf)

                    _update_pipeline_state('pose', 'Estimating pose…', None, None)
                    results_pose = None
                    pose = 'Unknown'
                    if MEDIAPIPE_AVAILABLE and mp_pose:
                        results_pose = mp_pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        pose = 'Unknown' if not results_pose.pose_landmarks else 'Standing'
                        if pose == 'Unknown' and results and results[0].boxes and hasattr(results[0], 'names'):
                            person_idxs = [i for i, c in enumerate(results[0].boxes.cls) if results[0].names.get(int(c), '').lower() == 'person']
                            if person_idxs:
                                # Use largest person bbox (by area) for crop fallback so we get pose more often
                                boxes = results[0].boxes
                                best_idx = max(person_idxs, key=lambda i: (boxes.xyxy[i][2] - boxes.xyxy[i][0]) * (boxes.xyxy[i][3] - boxes.xyxy[i][1]))
                                xyxy = boxes.xyxy[best_idx].cpu().numpy()
                                h, w = frame.shape[:2]
                                pad = 0.15
                                bw, bh = xyxy[2] - xyxy[0], xyxy[3] - xyxy[1]
                                x1 = max(0, int(xyxy[0] - pad * bw))
                                y1 = max(0, int(xyxy[1] - pad * bh))
                                x2 = min(w, int(xyxy[2] + pad * bw))
                                y2 = min(h, int(xyxy[3] + pad * bh))
                                if x2 > x1 and y2 > y1 and (y2 - y1) >= 32 and (x2 - x1) >= 32:
                                    crop = frame[y1:y2, x1:x2]
                                    res_crop = mp_pose.process(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
                                    if getattr(res_crop, 'pose_landmarks', None):
                                        results_pose = res_crop
                                        pose = 'Standing'
                        if pose == 'Standing' and _detect_person_down(frame, results, results_pose):
                            pose = 'Person down'
                    _update_pipeline_state('pose', 'Pose: %s' % pose, pose, None)

                    cfg_early = _recording_config
                    if cfg_early.get('ai_detail') == 'minimal':
                        emotion = 'Unknown'
                        license_plate = None
                        scene = 'Unknown'
                        _update_pipeline_state('emotion', 'Emotion: (minimal — disabled)', emotion, None)
                        _update_pipeline_state('scene', 'Scene: (minimal)', scene, None)
                    else:
                        _update_pipeline_state('emotion', 'Analyzing emotion…', None, None)
                        emotion = _get_dominant_emotion(frame, results)
                        _update_pipeline_state('emotion', 'Emotion: %s' % (emotion or 'Unknown'), emotion, None)
                        _update_pipeline_state('scene', 'Classifying scene…', None, None)
                        scene = 'Indoor' if np.mean(frame) < 100 else 'Outdoor'
                        license_plate = lpr_on_vehicle_roi(frame, results)
                        _update_pipeline_state('scene', 'Scene: %s' % scene, scene, None)

                    _update_pipeline_state('motion', 'Checking motion / loiter / line…', None, None)
                    motion = detect_motion(frame)
                    if motion:
                        _last_motion_time = time.time()
                    loiter, line_cross, zones_with_person = check_loiter_and_line_cross(frame, results)
                    raw_event = 'line_cross' if line_cross else ('loitering' if loiter else ('motion' if motion else None))
                    _event_history.append(raw_event)
                    recent = list(_event_history)
                    if len(recent) >= 2:
                        counts = Counter(recent)
                        majority = counts.most_common(1)[0]
                        if majority[1] >= 2 and majority[0] is not None:
                            raw_event = majority[0]
                        else:
                            raw_event = None
                    if raw_event == 'line_cross':
                        event = 'Line Crossing Detected'
                    elif raw_event == 'loitering':
                        event = 'Loitering Detected'
                    elif raw_event == 'motion':
                        event = 'Motion Detected'
                    else:
                        event = 'None'
                    if pose == 'Person down':
                        raw_event = 'fall'
                        event = 'Fall Detected'
                    _update_pipeline_state('motion', 'Event: %s' % event, event, None)

                    _ptz_auto_follow_from_bbox(frame, results)

                    crowd_count = sum(1 for cls in results[0].boxes.cls if results[0].names.get(int(cls), '').lower() == 'person') if results and results[0].boxes else 0

                    cfg = _recording_config
                    _update_pipeline_state('audio', 'Processing audio…', None, None)
                    if cfg.get('capture_audio', True):
                        audio_raw = get_audio_event()
                        if isinstance(audio_raw, dict):
                            audio_event = audio_raw.get('text', 'None')
                            audio_attrs = _extract_audio_attributes(
                                audio_raw.get('text'),
                                audio_raw.get('energy_db'),
                                audio_raw.get('duration_sec'),
                            )
                        else:
                            audio_event = audio_raw if isinstance(audio_raw, str) else 'None'
                            audio_attrs = _extract_audio_attributes(audio_event, None, None)
                    else:
                        audio_event = 'None'
                        audio_attrs = _extract_audio_attributes('None', None, None)
                    audio_msg = (audio_event[:50] + '…') if isinstance(audio_event, str) and len(audio_event) > 50 else (str(audio_event) if audio_event else 'none')
                    _update_pipeline_state('audio', 'Audio: %s' % audio_msg, audio_msg, None)

                    _update_pipeline_state('fuse', 'Fusing sensors…', None, None)
                    wifi_raw = get_wifi_device()
                    if isinstance(wifi_raw, dict):
                        macs = wifi_raw.get('macs') or []
                        device_mac = ','.join(macs) if macs else 'None'
                        device_oui_vendor = wifi_raw.get('oui_vendor')
                        device_probe_ssids = json.dumps(wifi_raw.get('probe_ssids') or []) if wifi_raw.get('probe_ssids') else None
                    else:
                        device_mac = wifi_raw if isinstance(wifi_raw, str) else 'None'
                        device_oui_vendor = None
                        device_probe_ssids = None
                    thermal_signature = analyze_thermal()
                    timestamp_utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                    if not cfg.get('capture_thermal', True):
                        thermal_signature = 'None'
                    if not cfg.get('capture_wifi', True):
                        device_mac = 'None'
                        device_oui_vendor = None
                        device_probe_ssids = None
                    data = {
                        'date': time.strftime('%Y-%m-%d'),
                        'time': time.strftime('%H:%M:%S'),
                        'individual': 'Unidentified',
                        'facial_features': f'pose={pose},emotion={emotion}',
                        'object': objects[0] if objects else 'None',
                        'pose': pose,
                        'emotion': emotion,
                        'scene': scene,
                        'license_plate': license_plate,
                        'event': event,
                        'crowd_count': crowd_count,
                        'audio_event': audio_event if cfg.get('capture_audio', True) else 'None',
                        'device_mac': device_mac,
                        'device_oui_vendor': device_oui_vendor,
                        'device_probe_ssids': device_probe_ssids,
                        'thermal_signature': thermal_signature,
                        'camera_id': '0',
                        'timestamp_utc': timestamp_utc,
                        'zone_presence': ','.join(map(str, sorted(zones_with_person))) if zones_with_person else '',
                        'model_version': _yolo_model_version(),
                        'system_id': _system_id(),
                    }
                    cnx, cny = _get_primary_centroid_normalized(frame, results)
                    cam_id = data.get('camera_id') or '0'
                    if cnx is not None and cny is not None:
                        data['centroid_nx'] = round(cnx, 4)
                        data['centroid_ny'] = round(cny, 4)
                        wx, wy = _apply_homography(cam_id, cnx, cny)
                        if wx is not None and wy is not None:
                            data['world_x'] = wx
                            data['world_y'] = wy
                    if cfg.get('capture_audio', True):
                        for k, v in audio_attrs.items():
                            if v is not None and (k not in data or data.get(k) is None):
                                data[k] = v
                    else:
                        for k in list(data.keys()):
                            if k.startswith('audio_'):
                                data[k] = data.get(k) if k == 'audio_event' else None
                    extended = _extract_extended_attributes(frame, results, pose, emotion, event, results_pose=results_pose) if cfg.get('ai_detail') == 'full' else {}
                    for k, v in extended.items():
                        if v is not None and (k not in data or data.get(k) is None):
                            data[k] = v
                    if os.environ.get('ENABLE_PREDICTIVE_THREAT', '').strip().lower() in ('1', 'true', 'yes'):
                        _apply_predictive_threat(data, event, timestamp_utc)
                    _apply_watchlist(frame, data, results)
                    _maybe_capture_notable(frame, data, event, data.get('camera_id') or '0', None, timestamp_utc)
                    if cfg.get('ai_detail') == 'minimal':
                        minimal_keys = ('date', 'time', 'event', 'object', 'camera_id', 'timestamp_utc')
                        data = {k: data.get(k) for k in minimal_keys if k in data}
                        for k in list(data.keys()):
                            if data[k] is None:
                                data[k] = 'None' if k != 'timestamp_utc' else time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                    # Normalize row to canonical columns so every insert has same shape (consistent export/analytics)
                    data = {k: data.get(k) for k in AI_DATA_EXPORT_COLUMNS}
                    data['integrity_hash'] = _ai_data_integrity_hash(data)
                    cols = list(AI_DATA_EXPORT_COLUMNS)
                    _ai_data_batch.append(data)
                    if len(_ai_data_batch) >= AI_DATA_BATCH_SIZE:
                        for row in _ai_data_batch:
                            get_cursor().execute(
                                f'''INSERT INTO ai_data ({",".join(cols)}) VALUES ({",".join("?" * len(cols))})''',
                                tuple(row.get(k) for k in cols),
                            )
                        get_conn().commit()
                        _ai_data_batch.clear()
                        _broadcast_event({'type': 'activity_update'})
                    if event != 'None':
                        ev_type = 'fall' if 'Fall' in event else ('line_cross' if 'Line' in event else ('loitering' if 'Loitering' in event else 'motion'))
                        if ev_type not in cfg.get('event_types', ['motion', 'loitering', 'line_cross', 'fall']):
                            pass
                        else:
                            dedupe_key = (ev_type, '0')
                            now_ts = time.time()
                            if dedupe_key in _last_event_insert and (now_ts - _last_event_insert[dedupe_key]) < _LAST_EVENT_DEDUPE_SEC:
                                pass
                            else:
                                _last_event_insert[dedupe_key] = now_ts
                                _ai_pipeline_state['last_event'] = event
                                ev_ts_utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                                ev_meta = json.dumps({
                                    'event': event, 'object': data['object'], 'crowd_count': crowd_count,
                                    'emotion': data.get('emotion'), 'pose': data.get('pose'), 'scene': data.get('scene'),
                                    'license_plate': data.get('license_plate') or None,
                                    'suspicious_behavior': data.get('suspicious_behavior'),
                                    'predicted_intent': data.get('predicted_intent'),
                                    'stress_level': data.get('stress_level'),
                                    'threat_score': data.get('threat_score'),
                                    'anomaly_score': data.get('anomaly_score'),
                                    'build': data.get('build'),
                                    'hair_color': data.get('hair_color'),
                                    'estimated_height_cm': data.get('estimated_height_cm'),
                                    'perceived_age_range': data.get('perceived_age_range'),
                                    'perceived_gender': data.get('perceived_gender'),
                                    'attention_region': data.get('attention_region'),
                                    'gait_notes': data.get('gait_notes'),
                                    'illumination_band': data.get('illumination_band'),
                                    'period_of_day_utc': data.get('period_of_day_utc'),
                                    'audio_transcription': data.get('audio_transcription'),
                                    'audio_sentiment': data.get('audio_sentiment'),
                                    'audio_emotion': data.get('audio_emotion'),
                                    'audio_stress_level': data.get('audio_stress_level'),
                                    'audio_threat_score': data.get('audio_threat_score'),
                                    'audio_anomaly_score': data.get('audio_anomaly_score'),
                                    'device_mac': data.get('device_mac'),
                                    'device_oui_vendor': data.get('device_oui_vendor'),
                                    'device_probe_ssids': data.get('device_probe_ssids'),
                                })
                                ev_severity = 'medium'
                                ev_hash = _event_integrity_hash(ev_ts_utc, ev_type, '0', 'default', ev_meta, ev_severity)
                                get_cursor().execute(
                                    '''INSERT INTO events (event_type, camera_id, site_id, timestamp, timestamp_utc, metadata, severity, integrity_hash)
                                       VALUES (?, ?, ?, datetime("now"), ?, ?, ?, ?)''',
                                    (ev_type, '0', 'default', ev_ts_utc, ev_meta, ev_severity, ev_hash)
                                )
                                get_conn().commit()
                                _broadcast_event({'type': 'new_event'})
                                _trigger_alert(ev_type, 'medium', json.dumps({'event': event, 'object': data['object']}))
                                _perimeter_action(ev_type, '0', ev_ts_utc)
                                _autonomous_action(ev_type, '0', ev_ts_utc, data.get('threat_score'), ev_meta)
                    # Crowd density alert: when count >= threshold, emit crowding event and alert (deduped)
                    try:
                        crowd_alert_threshold = int(os.environ.get('CROWD_DENSITY_ALERT_THRESHOLD', '0'))
                    except (TypeError, ValueError):
                        crowd_alert_threshold = 0
                    if crowd_alert_threshold > 0 and crowd_count >= crowd_alert_threshold:
                        dedupe_key = ('crowding', '0')
                        now_ts = time.time()
                        if dedupe_key not in _last_event_insert or (now_ts - _last_event_insert[dedupe_key]) >= _LAST_EVENT_DEDUPE_SEC:
                            _last_event_insert[dedupe_key] = now_ts
                            ev_ts_utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                            ev_meta = json.dumps({'event': 'Crowding Detected', 'crowd_count': crowd_count, 'camera_id': '0'})
                            ev_hash = _event_integrity_hash(ev_ts_utc, 'crowding', '0', 'default', ev_meta, 'medium')
                            get_cursor().execute(
                                '''INSERT INTO events (event_type, camera_id, site_id, timestamp, timestamp_utc, metadata, severity, integrity_hash)
                                   VALUES (?, ?, ?, datetime("now"), ?, ?, ?, ?)''',
                                ('crowding', '0', 'default', ev_ts_utc, ev_meta, 'medium', ev_hash)
                            )
                            get_conn().commit()
                            _broadcast_event({'type': 'new_event'})
                            _trigger_alert('crowding', 'medium', json.dumps({'event': 'Crowding Detected', 'crowd_count': crowd_count}))
            else:
                # Flush any buffered ai_data when recording stops (collection optimization research).
                if _ai_data_batch:
                    cols = list(AI_DATA_EXPORT_COLUMNS)
                    for row in _ai_data_batch:
                        get_cursor().execute(
                            f'''INSERT INTO ai_data ({",".join(cols)}) VALUES ({",".join("?" * len(cols))})''',
                            tuple(row.get(k) for k in cols),
                        )
                    get_conn().commit()
                    _ai_data_batch.clear()
                    _broadcast_event({'type': 'activity_update'})
            # Optional idle skip: when no motion for N seconds, sleep longer to save CPU (sustainable AI efficiency)
            try:
                idle_skip_sec = int(os.environ.get('ANALYZE_IDLE_SKIP_SECONDS', '0'))
                idle_mult = max(1.0, min(5.0, float(os.environ.get('ANALYZE_IDLE_INTERVAL_MULTIPLIER', '2'))))
            except (TypeError, ValueError):
                idle_skip_sec = 0
                idle_mult = 2.0
            if idle_skip_sec > 0 and _last_motion_time > 0 and (time.time() - _last_motion_time) >= idle_skip_sec:
                time.sleep(ANALYZE_INTERVAL_SECONDS * idle_mult)
            else:
                time.sleep(ANALYZE_INTERVAL_SECONDS)
        except Exception as e:
            print('[analyze_frame]', e, flush=True)


# Optional: serve React production build (set USE_REACT_APP=1 and run "cd frontend && npm run build")
_REACT_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'dist')


def _send_react_index():
    index_path = os.path.join(_REACT_DIST, 'index.html')
    if os.path.isfile(index_path):
        with open(index_path) as f:
            return f.read()
    return None


@app.route('/')
def index():
    if os.environ.get('USE_REACT_APP', '').lower() in ('1', 'true', 'yes') and os.path.isdir(_REACT_DIST):
        html = _send_react_index()
        if html:
            from flask import make_response
            r = make_response(html)
            r.headers['Content-Type'] = 'text/html'
            return r
    return render_template('index.html', logged_in=bool(session.get('user_id')))


@app.route('/settings')
def settings_page():
    """Flask settings page: user, devices, password, MFA, config (admin), audit (admin)."""
    return render_template('settings.html')


# SPA routes (React client-side paths): show helpful message instead of JSON 404 when React not enabled
_SPA_ROUTES = {'login', 'logout', 'activity', 'dashboard', 'export', 'settings', 'events', 'timeline', 'log', 'behaviors', 'map', 'analytics'}


@app.route('/<path:path>')
def serve_react(path):
    """Serve React SPA and static assets when USE_REACT_APP=1; otherwise serve app shell for SPA routes."""
    use_react = os.environ.get('USE_REACT_APP', '').lower() in ('1', 'true', 'yes') and os.path.isdir(_REACT_DIST)
    path_base = path.split('?')[0].strip('/').lower() or ''
    if not use_react:
        if path in ('login', 'logout'):
            return render_template('index.html', logged_in=bool(session.get('user_id')))
        if path_base in _SPA_ROUTES:
            from flask import make_response
            body = (
                '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Vigil — Activity</title></head>'
                '<body style="font-family:sans-serif;padding:2rem;background:#0f0f0f;color:#94a3b8;">'
                '<h1 style="color:#22d3ee;">Activity / Playback</h1>'
                '<p>To use this page (and &quot;Play at moment&quot; from the SOC dashboard), build the React app and run with <code>USE_REACT_APP=1</code>.</p>'
                '<p>From project root:</p><pre style="background:#1e293b;padding:1rem;border-radius:6px;">cd frontend &amp;&amp; npm run build</pre>'
                '<p>Then restart the server with <code>USE_REACT_APP=1</code> (e.g. <code>USE_REACT_APP=1 python app.py</code>).</p>'
                '<p><a href="/" style="color:#22d3ee;">Go to home</a></p></body></html>'
            )
            return make_response((body, 404, {'Content-Type': 'text/html'}))
        return jsonify({'error': 'Not found'}), 404
    file_path = os.path.join(_REACT_DIST, path)
    if os.path.isfile(file_path):
        from flask import send_from_directory
        return send_from_directory(_REACT_DIST, path)
    html = _send_react_index()
    if html:
        from flask import make_response
        return make_response(html)
    return jsonify({'error': 'Not found'}), 404


@app.route('/video_feed')
@app.route('/video_feed/<camera_id>')
def video_feed(camera_id='0'):
    if camera_id not in _cameras:
        return jsonify({'error': 'Camera not found'}), 404
    return Response(gen_frames(camera_id), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/thermal_feed')
def thermal_feed():
    return Response(gen_thermal_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/sites')
def list_sites():
    get_cursor().execute('SELECT id, name, map_url, timezone FROM sites')
    rows = get_cursor().fetchall()
    return jsonify([dict(zip(['id', 'name', 'map_url', 'timezone'], row)) for row in rows])


@app.route('/camera_positions')
def list_camera_positions():
    site_id = request.args.get('site_id', 'default')
    get_cursor().execute('SELECT camera_id, site_id, x, y, label FROM camera_positions WHERE site_id = ?', (site_id,))
    rows = get_cursor().fetchall()
    return jsonify([dict(zip(['camera_id', 'site_id', 'x', 'y', 'label'], row)) for row in rows])


def _get_device_name_for_index(index):
    """Get human-readable camera name from OS: Linux sysfs/udev, macOS AVFoundation (ffmpeg), Windows optional. Returns None if unavailable."""
    idx = index if isinstance(index, int) else (int(index) if str(index).isdigit() else None)
    if idx is None:
        return None
    # Linux: /sys/class/video4linux/videoN/name
    sysfs = f'/sys/class/video4linux/video{idx}/name'
    if os.path.isfile(sysfs):
        try:
            with open(sysfs) as f:
                name = f.read().strip()
            if name:
                return name
        except Exception:
            pass
    # Linux: udevadm
    try:
        import subprocess
        r = subprocess.run(
            ['udevadm', 'info', '--query=property', f'--name=/dev/video{idx}'],
            capture_output=True, text=True, timeout=2
        )
        if r.returncode == 0 and r.stdout:
            for line in r.stdout.splitlines():
                if line.startswith('ID_MODEL='):
                    return line.split('=', 1)[1].strip().replace('_', ' ')
                if line.startswith('ID_V4L_PRODUCT='):
                    return line.split('=', 1)[1].strip()
    except Exception:
        pass
    # macOS: ffmpeg -f avfoundation -list_devices (video section: [0] Name, [1] Name)
    if platform.system() == 'Darwin':
        try:
            import subprocess
            r = subprocess.run(
                ['ffmpeg', '-f', 'avfoundation', '-list_devices', 'true', '-i', ''],
                capture_output=True, text=True, timeout=5
            )
            if r.stderr:
                in_video = False
                for line in r.stderr.splitlines():
                    if 'AVFoundation video devices' in line:
                        in_video = True
                        continue
                    if in_video and 'AVFoundation audio' in line:
                        break
                    if in_video and ']' in line:
                        # "... [0] FaceTime HD Camera"
                        m = re.search(r'\[(\d+)\]\s*(.+)', line)
                        if m:
                            dev_idx, name = int(m.group(1)), m.group(2).strip()
                            if dev_idx == idx:
                                return name or None
        except Exception:
            pass
        if idx == 0:
            return 'Built-in Camera'
        if idx == 1:
            return 'External Camera'
    return None


def _get_camera_display_name(cam_id):
    """Return display name for camera: DB label, then real hardware detection (sysfs/udev), then RTSP host; only fallback to 'Camera N' when no name available."""
    # 1) DB label (camera_positions) if set and not the default
    try:
        get_cursor().execute('SELECT label FROM camera_positions WHERE camera_id = ? LIMIT 1', (cam_id,))
        row = get_cursor().fetchone()
        if row and row[0] and str(row[0]).strip():
            label = str(row[0]).strip()
            if label != f'Camera {cam_id}':
                return label
    except Exception:
        pass
    # 2) For index-based source: try OS device name
    if cam_id.isdigit() and int(cam_id) < len(_camera_sources):
        src = _camera_sources[int(cam_id)].strip()
        try:
            idx = int(src)
            name = _get_device_name_for_index(idx)
            if name:
                return name
        except ValueError:
            pass
        # 3) RTSP or URL: short descriptive label
        if src.startswith('rtsp://') or src.startswith('http://') or src.startswith('https://'):
            try:
                from urllib.parse import urlparse
                p = urlparse(src)
                host = (p.hostname or p.path or 'stream')[:30]
                return f'RTSP ({host})' if 'rtsp' in src.lower() else f'Stream ({host})'
            except Exception:
                return f'Camera {cam_id}'
    return f'Camera {cam_id}'


@app.route('/streams')
def list_streams():
    """Return available streams for dashboard. type mjpeg for in-app feeds; thermal only if hardware present."""
    streams = []
    for cam_id in sorted(_cameras.keys()):
        streams.append({
            'id': cam_id,
            'name': _get_camera_display_name(cam_id),
            'type': 'mjpeg',
            'url': f'/video_feed/{cam_id}' if cam_id != '0' else '/video_feed',
            'camera_id': cam_id,
        })
    if _thermal_capture is not None:
        streams.append({
            'id': 'thermal',
            'name': 'Thermal',
            'type': 'mjpeg',
            'url': '/thermal_feed',
            'camera_id': 'thermal',
        })
    return jsonify(streams)


def _get_camera_status_list():
    """Return list of camera status dicts for system status: id, name, status (ok/no_signal/offline), resolution, source, last_frame_utc, last_offline_utc, flapping."""
    now = time.time()
    stale_seconds = 30  # no frame in 30s = no_signal
    flapping_window_seconds = 600  # 10 min
    flapping_min_changes = 3
    out_list = []
    for cam_id in sorted(_cameras.keys()):
        cap = _cameras.get(cam_id)
        name = _get_camera_display_name(cam_id)
        if cap is None:
            status = 'offline'
            prev = _camera_prev_status.get(cam_id)
            if prev != status:
                _camera_prev_status[cam_id] = status
                _camera_last_offline_at[cam_id] = now
                _camera_status_change_times.setdefault(cam_id, []).append(now)
            lst = _camera_status_change_times.get(cam_id) or []
            lst = [t for t in lst if (now - t) <= flapping_window_seconds]
            _camera_status_change_times[cam_id] = lst[-20:]
            flapping = len(lst) >= flapping_min_changes
            last_offline_utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(_camera_last_offline_at[cam_id])) if _camera_last_offline_at.get(cam_id) else None
            out_list.append({'id': cam_id, 'name': name, 'status': status, 'resolution': None, 'source': None, 'last_frame_utc': None, 'last_offline_utc': last_offline_utc, 'flapping': flapping})
            continue
        opened = cap.isOpened()
        last_ts = _camera_last_frame_time.get(cam_id) or 0
        if not opened:
            status = 'offline'
        elif (now - last_ts) > stale_seconds:
            status = 'no_signal'
        else:
            status = 'ok'
        # Track transitions for last-offline and flapping
        prev = _camera_prev_status.get(cam_id)
        if prev != status:
            _camera_prev_status[cam_id] = status
            if status in ('no_signal', 'offline'):
                _camera_last_offline_at[cam_id] = now
            _camera_status_change_times.setdefault(cam_id, []).append(now)
        lst = _camera_status_change_times.get(cam_id) or []
        lst = [t for t in lst if (now - t) <= flapping_window_seconds]
        _camera_status_change_times[cam_id] = lst[-20:]
        flapping = len(lst) >= flapping_min_changes
        last_offline_utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(_camera_last_offline_at[cam_id])) if _camera_last_offline_at.get(cam_id) else None
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if opened else 0
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if opened else 0
        resolution = f'{w}x{h}' if (w and h) else None
        src = _camera_sources[int(cam_id)] if cam_id.isdigit() and int(cam_id) < len(_camera_sources) else cam_id
        last_frame_utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(last_ts)) if last_ts else None
        out_list.append({'id': cam_id, 'name': name, 'status': status, 'resolution': resolution, 'source': str(src), 'last_frame_utc': last_frame_utc, 'last_offline_utc': last_offline_utc, 'flapping': flapping})
    if _thermal_capture is not None:
        out_list.append({'id': 'thermal', 'name': 'Thermal', 'status': 'ok', 'resolution': '80x60', 'source': 'flir', 'last_frame_utc': None, 'last_offline_utc': None, 'flapping': False})
    return out_list


@app.route('/health')
def health():
    """Liveness: is the process up. Includes recording and uptime."""
    return jsonify({
        'status': 'ok',
        'recording': is_recording,
        'uptime_seconds': int(time.time() - _app_start_time),
    })


def _get_ai_status():
    """Build AI superpowers overview for system_status: YOLO, emotion, pose, LPR, stream tuning."""
    emotion_backend = (os.environ.get('EMOTION_BACKEND') or 'auto').strip().lower()
    if emotion_backend == 'auto':
        if EMOTIEFFLIB_AVAILABLE:
            emotion_backend = 'emotiefflib'
        elif DEEPFACE_AVAILABLE:
            emotion_backend = 'deepface'
        else:
            emotion_backend = 'none'
    yolo_imgsz = os.environ.get('YOLO_IMGSZ', '640')
    try:
        yolo_imgsz = int(yolo_imgsz)
    except (TypeError, ValueError):
        yolo_imgsz = 640
    stream_quality = os.environ.get('STREAM_JPEG_QUALITY', '82')
    stream_max_w = os.environ.get('STREAM_MAX_WIDTH', '0')
    try:
        stream_quality = int(stream_quality)
    except (TypeError, ValueError):
        stream_quality = 82
    try:
        stream_max_w = int(stream_max_w)
    except (TypeError, ValueError):
        stream_max_w = 0
    return {
        'yolo': {
            'loaded': yolo_model is not None,
            'model': os.environ.get('YOLO_MODEL', os.environ.get('YOLO_WEIGHTS', 'yolov8n.pt')),
            'device': os.environ.get('YOLO_DEVICE') or 'default',
            'imgsz': yolo_imgsz,
            'conf': _yolo_conf,
        },
        'emotion_backend': emotion_backend,
        'mediapipe_pose': MEDIAPIPE_AVAILABLE,
        'gait_notes_enabled': _is_gait_notes_enabled(),
        'lpr': True,  # pytesseract-based LPR always attempted when available
        'lpr_preprocess': _ENABLE_LPR_PREPROCESS,
        'stream_quality': stream_quality,
        'stream_max_width': stream_max_w,
    }


@app.route('/api/v1/config/public')
def api_v1_config_public():
    """Public config for frontend: map tile URL and default center/zoom (no auth). Use for Leaflet/OSM."""
    try:
        default_lat = float(os.environ.get('MAP_DEFAULT_LAT', '51.505'))
    except (TypeError, ValueError):
        default_lat = 51.505
    try:
        default_lon = float(os.environ.get('MAP_DEFAULT_LON', '-0.09'))
    except (TypeError, ValueError):
        default_lon = -0.09
    try:
        default_zoom = int(os.environ.get('MAP_DEFAULT_ZOOM', '13'))
    except (TypeError, ValueError):
        default_zoom = 13
    tile_url = (os.environ.get('MAP_TILE_URL') or 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').strip()
    return jsonify({
        'map': {
            'tile_url': tile_url,
            'default_lat': default_lat,
            'default_lon': default_lon,
            'default_zoom': default_zoom,
            'attribution': '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        },
    })


@app.route('/api/v1/system_status')
def api_v1_system_status():
    """System Status & Network Health: DB, recording, uptime, per-camera status, AI superpowers for dashboard."""
    db_ok = False
    try:
        get_cursor().execute('SELECT 1')
        get_cursor().fetchone()
        db_ok = True
    except Exception:
        pass
    cameras = _get_camera_status_list()
    status = 'ok' if db_ok and all(c.get('status') == 'ok' for c in cameras if c.get('id') != 'thermal') else 'degraded'
    if not db_ok:
        status = 'degraded'
    storage_bytes, recording_count, storage_free_bytes, storage_total_bytes = _recordings_storage()
    try:
        retention_days = int(os.environ.get('RETENTION_DAYS', '0'))
    except (TypeError, ValueError):
        retention_days = 0
    cfg = _recording_config
    ai_detail = cfg.get('ai_detail') or 'full'
    feature_flags = {
        'audio_capture': bool(cfg.get('capture_audio') and AUDIO_AVAILABLE),
        'lpr': ai_detail != 'minimal',
        'emotion': ai_detail != 'minimal',
        'wifi_sniff': bool(cfg.get('capture_wifi')),
        'reid': os.environ.get('ENABLE_REID', '').strip().lower() in ('1', 'true', 'yes'),
        'recording_fixity': os.environ.get('ENABLE_RECORDING_FIXITY', '').strip().lower() in ('1', 'true', 'yes'),
    }
    payload = {
        'status': status,
        'db_ok': db_ok,
        'recording': is_recording,
        'uptime_seconds': int(time.time() - _app_start_time),
        'cameras': cameras,
        'ai': _get_ai_status(),
        'storage_used_bytes': storage_bytes,
        'recording_count': recording_count,
        'retention_days': retention_days,
        'audio_enabled': _audio_capture_enabled,
        'audio_available': AUDIO_AVAILABLE,
        'enable_audio_env': os.environ.get('ENABLE_AUDIO', '1').strip(),
        'feature_flags': feature_flags,
        'privacy_preset': _analytics_config.get('privacy_preset', 'full'),
        'home_away_mode': _analytics_config.get('home_away_mode', 'away'),
    }
    if storage_free_bytes is not None:
        payload['storage_free_bytes'] = storage_free_bytes
    if storage_total_bytes is not None:
        payload['storage_total_bytes'] = storage_total_bytes
    return jsonify(payload)


@app.route('/api/v1/what_we_collect')
def api_v1_what_we_collect():
    """Transparency: summary of what is recorded/analyzed (civilian ethics). No auth required for in-dashboard display."""
    try:
        retention_days = int(os.environ.get('RETENTION_DAYS', '0'))
    except (TypeError, ValueError):
        retention_days = 0
    cfg = _recording_config
    ai_detail = cfg.get('ai_detail') or 'full'
    return jsonify({
        'video': True,
        'audio': bool(cfg.get('capture_audio') and AUDIO_AVAILABLE),
        'motion': True,
        'loitering': True,
        'line_crossing': True,
        'fall_detection': True,
        'lpr': ai_detail != 'minimal',
        'emotion_or_face': ai_detail != 'minimal',
        'wifi_presence': bool(cfg.get('capture_wifi')),
        'thermal': bool(cfg.get('capture_thermal')),
        'retention_days': retention_days,
        'privacy_preset': _analytics_config.get('privacy_preset', 'full'),
    })


@app.route('/api/audio_toggle', methods=['POST'])
def api_audio_toggle():
    """Toggle audio capture on/off at runtime (e.g. from fullscreen UI). Only has effect when AUDIO_AVAILABLE."""
    global _audio_capture_enabled
    if AUDIO_AVAILABLE:
        _audio_capture_enabled = not _audio_capture_enabled
    _broadcast_event({'type': 'audio_toggle', 'audio_enabled': _audio_capture_enabled})
    return jsonify({'audio_enabled': _audio_capture_enabled})


def _do_auto_login():
    """When AUTO_LOGIN=1, set session as admin. Returns (success, role or None)."""
    if session.get('user_id'):
        return True, session.get('role', 'admin')
    raw = (os.environ.get('AUTO_LOGIN') or '').strip().lower()
    # In dev (default secret), default to enabled so React dev server can use auto sign-in
    if not raw and app.secret_key == 'dev-secret-change-in-production':
        enabled = True
    else:
        enabled = raw in ('1', 'true', 'yes')
    if not enabled:
        return False, None
    _ensure_default_user()
    get_cursor().execute('SELECT id, role FROM users WHERE username = ?', ('admin',))
    row = get_cursor().fetchone()
    if not row:
        return False, None
    uid, role = row[0], row[1]
    session['user_id'] = str(uid)
    session['username'] = 'admin'
    session['role'] = role
    session['last_activity'] = time.time()
    _audit('admin', 'auto_login', 'auth')
    return True, role


@app.route('/auto_login')
def auto_login_redirect():
    """One-click sign-in as administrator when AUTO_LOGIN=1. Redirects to / so user can view all recordings and files."""
    success, role = _do_auto_login()
    if success:
        return redirect('/', code=302)
    return redirect('/login?auto=0', code=302)


@app.route('/api/v1/auto_login')
def api_v1_auto_login():
    """When AUTO_LOGIN=1, log in as admin (using ADMIN_PASSWORD from env) without a form. For local/dev convenience."""
    success, role = _do_auto_login()
    if success:
        return jsonify({'success': True, 'role': role})
    return jsonify({'success': False, 'enabled': False}), 404


@app.route('/api/v1/cameras/detect')
def api_v1_cameras_detect():
    """Autodetect camera devices: probe V4L2 indices 0-9, get device names (Linux sysfs/udev), list /dev/video*."""
    detected = []
    # Probe indices 0-9 (OpenCV); on macOS use AVFoundation for built-in camera
    for idx in range(10):
        cap = _open_video_capture(idx)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            name = _get_device_name_for_index(idx)
            detected.append({
                'index': idx,
                'path': f'index:{idx}',
                'opened': True,
                'resolution': f'{w}x{h}',
                'name': name or f'Camera {idx}',
            })
        else:
            cap.release()
    # On Linux, list /dev/video* not already in detected (e.g. metadata nodes or unopened)
    if os.path.exists('/dev'):
        try:
            devs = sorted([d for d in os.listdir('/dev') if d.startswith('video') and len(d) > 5 and d[5:].isdigit()])
            for d in devs:
                path = f'/dev/{d}'
                idx = int(d[5:])
                if any(isinstance(x.get('index'), int) and x.get('index') == idx for x in detected):
                    continue
                name = _get_device_name_for_index(idx)
                detected.append({
                    'index': path,
                    'path': path,
                    'opened': False,
                    'resolution': None,
                    'name': name or d,
                })
        except Exception:
            pass
    return jsonify({'detected': detected})


@app.route('/api/v1/audio/detect')
def api_v1_audio_detect():
    """Autodetect microphone/input devices (PyAudio). Integrates with ENABLE_AUDIO for laptop/device auto-setup."""
    devices = _detect_microphones()
    return jsonify({'detected': devices, 'audio_enabled': AUDIO_AVAILABLE})


@app.route('/api/ai_pipeline_state')
def api_ai_pipeline_state():
    """Return current AI pipeline state for UI: how the AI is thinking and formulating data collection (interpretability)."""
    return jsonify(_ai_pipeline_state)


def _sse_generator():
    """Yield Server-Sent Events for live feed updates (new_event, activity_update)."""
    q = queue.Queue()
    _sse_listeners.append(q)
    try:
        while True:
            try:
                msg = q.get(timeout=25)
                yield 'data: %s\n\n' % json.dumps(msg)
            except queue.Empty:
                yield 'data: %s\n\n' % json.dumps({'type': 'ping', 'ts': time.time()})
    finally:
        try:
            _sse_listeners.remove(q)
        except ValueError:
            pass


@app.route('/api/stream')
def api_stream():
    """Server-Sent Events stream for real-time feed updates. Connect with EventSource('/api/stream')."""
    from flask import Response, stream_with_context
    return Response(
        stream_with_context(_sse_generator()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'}
    )


@app.route('/api/v1/notable_screenshots')
def api_v1_notable_screenshots():
    """List notable behavior screenshots (reason, timestamp, file_path). Query: limit, camera_id, reason, since (ISO date or datetime)."""
    from flask import request
    limit = min(int(request.args.get('limit', 50)), 200)
    camera_id = request.args.get('camera_id')
    reason = request.args.get('reason')
    since = request.args.get('since')
    sql = 'SELECT id, timestamp_utc, reason, reason_detail, file_path, camera_id, event_id, created_at FROM notable_screenshots WHERE 1=1'
    params = []
    if camera_id:
        sql += ' AND camera_id = ?'
        params.append(camera_id)
    if reason:
        sql += ' AND reason = ?'
        params.append(reason)
    if since:
        sql += ' AND timestamp_utc >= ?'
        params.append(since)
    sql += ' ORDER BY timestamp_utc DESC LIMIT ?'
    params.append(limit)
    try:
        cur = get_cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cols = ['id', 'timestamp_utc', 'reason', 'reason_detail', 'file_path', 'camera_id', 'event_id', 'created_at']
        items = [dict(zip(cols, row)) for row in rows]
        return jsonify({'notable_screenshots': items})
    except Exception as e:
        return jsonify({'notable_screenshots': [], 'error': str(e)}), 500


@app.route('/api/v1/notable_screenshots/<int:screenshot_id>/image')
def api_v1_notable_screenshot_image(screenshot_id):
    """Serve the image file for a notable screenshot by id."""
    from flask import send_from_directory
    try:
        cur = get_cursor()
        cur.execute('SELECT file_path FROM notable_screenshots WHERE id = ?', (screenshot_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        file_path = row[0]
        filename = os.path.basename(file_path)
        if not filename or filename.startswith('.') or '/' in filename or '\\' in filename:
            return jsonify({'error': 'Invalid path'}), 400
        if not os.path.isdir(NOTABLE_SCREENSHOTS_DIR):
            return jsonify({'error': 'Screenshots directory not found'}), 404
        full_path = os.path.join(NOTABLE_SCREENSHOTS_DIR, filename)
        if not os.path.isfile(full_path):
            return jsonify({'error': 'File not found'}), 404
        return send_from_directory(NOTABLE_SCREENSHOTS_DIR, filename, mimetype='image/jpeg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/devices')
def api_v1_devices():
    """Unified device list: cameras + microphones for dashboard/setup (competitor-style auto-discovery)."""
    cam_resp = api_v1_cameras_detect()
    cameras = (cam_resp.get_json() or {}).get('detected', [])
    mics = _detect_microphones()
    return jsonify({
        'cameras': cameras,
        'microphones': mics,
        'audio_enabled': AUDIO_AVAILABLE,
        'camera_sources_auto': _raw_camera_sources.lower() in ('', 'auto'),
    })


def _time_sync_status():
    """Return time_sync_status for readiness: 'synced' if NTP check ok, 'unknown' otherwise (civilian evidence best practice). ntplib is optional."""
    try:
        import ntplib  # type: ignore[import-untyped]
        c = ntplib.NTPClient()
        r = c.request('pool.ntp.org', version=3, timeout=2)
        if r is not None and abs(r.offset or 0) < 5.0:
            return 'synced'
    except ImportError:
        pass
    except Exception:
        pass
    return 'unknown'


@app.route('/health/ready')
def health_ready():
    """Readiness: can serve traffic (DB + optional camera check). Includes time_sync_status for evidence (NISTIR 8161)."""
    try:
        get_cursor().execute('SELECT 1')
        get_cursor().fetchone()
    except Exception as e:
        return jsonify({'status': 'not_ready', 'reason': 'database', 'detail': str(e)}), 503
    return jsonify({'status': 'ready', 'time_sync_status': _time_sync_status()})


@app.route('/recording')
def recording_status():
    return jsonify({'recording': is_recording})


@app.route('/toggle_recording', methods=['POST'])
def toggle_recording():
    global is_recording, out
    is_recording = not is_recording
    if not is_recording:
        with _recording_lock:
            if out:
                out.release()
                out = None
    _audit(session.get('username'), 'toggle_recording', 'recording', 'on' if is_recording else 'off')
    _broadcast_event({'type': 'recording_toggle', 'recording': is_recording})
    return jsonify({'recording': is_recording})


@app.route('/recording_config', methods=['GET', 'POST'])
def recording_config():
    """GET: return current recording gather options (event_types, ai_detail, etc.). POST: set options; operator/admin. Data is collected only while recording is on."""
    global _recording_config
    if request.method == 'POST':
        if not session.get('user_id'):
            return jsonify({'error': 'Login required to change recording config'}), 401
        data = request.get_json() or {}
        if isinstance(data.get('event_types'), list):
            _recording_config['event_types'] = [str(x) for x in data['event_types'] if str(x) in ('motion', 'loitering', 'line_cross', 'fall')]
        if 'capture_audio' in data:
            _recording_config['capture_audio'] = bool(data['capture_audio'])
        if 'capture_thermal' in data:
            _recording_config['capture_thermal'] = bool(data['capture_thermal'])
        if 'capture_wifi' in data:
            _recording_config['capture_wifi'] = bool(data['capture_wifi'])
        if data.get('ai_detail') in ('minimal', 'full'):
            _recording_config['ai_detail'] = data['ai_detail']
        try:
            _audit(session.get('username'), 'recording_config', 'config', str(_recording_config))
        except Exception:
            pass
        return jsonify(_recording_config)
    return jsonify(_recording_config)


_STORAGE_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'storage.json')
_recordings_base_path = None


def _recordings_dir():
    """Return configured recordings directory (env RECORDINGS_DIR, or config file, or app dir). Enterprise: support external/USB drive."""
    global _recordings_base_path
    if _recordings_base_path is None:
        base = os.environ.get('RECORDINGS_DIR', '').strip()
        if not base and os.path.isfile(_STORAGE_CONFIG_FILE):
            try:
                with open(_STORAGE_CONFIG_FILE) as f:
                    data = json.load(f)
                    base = (data.get('recordings_dir') or '').strip()
            except Exception:
                pass
        if not base:
            base = os.path.dirname(os.path.abspath(__file__))
        _recordings_base_path = os.path.abspath(base)
    return _recordings_base_path


def _set_recordings_dir(path):
    """Set recordings directory (must exist and be writable). Persist to config file. Returns (success, message)."""
    global _recordings_base_path
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(path):
        return False, 'Not a directory'
    try:
        tf = os.path.join(path, '.vigil_write_test')
        with open(tf, 'w') as f:
            f.write('')
        os.unlink(tf)
    except Exception as e:
        return False, str(e)
    _recordings_base_path = path
    try:
        os.makedirs(os.path.dirname(_STORAGE_CONFIG_FILE), exist_ok=True)
        with open(_STORAGE_CONFIG_FILE, 'w') as f:
            json.dump({'recordings_dir': path}, f, indent=2)
    except Exception:
        pass
    return True, 'OK'


def _reset_recordings_dir_to_default():
    """Clear configured path so _recordings_dir() falls back to app dir. Returns (success, message)."""
    global _recordings_base_path
    _recordings_base_path = None
    try:
        if os.path.isfile(_STORAGE_CONFIG_FILE):
            os.remove(_STORAGE_CONFIG_FILE)
    except Exception:
        pass
    return True, 'OK'


def _list_available_drives():
    """List candidate storage locations (app dir, /Volumes on macOS, /media on Linux, drive letters on Windows). Enterprise: external drive detection."""
    drives = []
    app_dir = os.path.dirname(os.path.abspath(__file__))
    drives.append({'path': app_dir, 'label': 'App directory (default)'})
    if os.path.isdir('/Volumes'):
        try:
            for d in os.listdir('/Volumes'):
                if d in ('.', '..'):
                    continue
                p = os.path.join('/Volumes', d)
                if os.path.isdir(p):
                    drives.append({'path': p, 'label': 'Mac: %s' % d})
        except Exception:
            pass
    if os.path.isdir('/media'):
        try:
            for u in os.listdir('/media'):
                p = os.path.join('/media', u)
                if os.path.isdir(p):
                    for d in os.listdir(p):
                        sub = os.path.join(p, d)
                        if os.path.isdir(sub):
                            drives.append({'path': sub, 'label': 'Linux: %s' % d})
        except Exception:
            pass
    run_media = '/run/media'
    if os.path.isdir(run_media):
        try:
            for u in os.listdir(run_media):
                p = os.path.join(run_media, u)
                if os.path.isdir(p):
                    for d in os.listdir(p):
                        sub = os.path.join(p, d)
                        if os.path.isdir(sub):
                            drives.append({'path': sub, 'label': 'USB: %s' % d})
        except Exception:
            pass
    # Windows: list mounted drive letters (e.g. D:\, E:\ for external drives)
    if os.name == 'nt':
        try:
            import string
            for letter in string.ascii_uppercase:
                drive = letter + ':\\'
                if os.path.isdir(drive):
                    drives.append({'path': drive, 'label': 'Drive %s' % drive})
        except Exception:
            pass
    return drives


@app.route('/api/storage')
@require_role('viewer', 'operator', 'admin')
def api_storage():
    """Get current storage path, available drives (external/USB), and usage. Enterprise: choose local or external drive."""
    rec_dir = _recordings_dir()
    storage_bytes, recording_count, _, _ = _recordings_storage()
    can_write = False
    try:
        tf = os.path.join(rec_dir, '.vigil_write_test')
        with open(tf, 'w') as f:
            f.write('')
        os.unlink(tf)
        can_write = True
    except Exception:
        pass
    return jsonify({
        'path': rec_dir,
        'recordings_path': rec_dir,
        'available_drives': _list_available_drives(),
        'can_write': can_write,
        'storage_used_bytes': storage_bytes,
        'used_bytes': storage_bytes,
        'recording_count': recording_count,
    })


@app.route('/api/storage', methods=['POST'])
@require_role('admin')
def api_storage_set():
    """Set recordings directory (e.g. external drive). Empty path = reset to app default."""
    data = request.get_json() or {}
    path = (data.get('path') or '').strip()
    if path:
        success, message = _set_recordings_dir(path)
    else:
        success, message = _reset_recordings_dir_to_default()
    if not success:
        return jsonify({'success': False, 'error': message}), 400
    rec_dir = _recordings_dir()
    _audit(session.get('username'), 'storage_set', 'recordings_dir', rec_dir or '(default)')
    storage_bytes, recording_count, _, _ = _recordings_storage()
    can_write = False
    try:
        tf = os.path.join(rec_dir, '.vigil_write_test')
        with open(tf, 'w') as f:
            f.write('')
        os.unlink(tf)
        can_write = True
    except Exception:
        pass
    return jsonify({
        'success': True,
        'recordings_path': rec_dir,
        'path': rec_dir,
        'used_bytes': storage_bytes,
        'storage_used_bytes': storage_bytes,
        'recording_count': recording_count,
        'can_write': can_write,
        'available_drives': _list_available_drives(),
        'message': 'Storage location updated. New recordings will save here.',
    })


def _recordings_storage():
    """Return storage_used_bytes, recording_count, and optional disk free/total for the recordings partition (for dashboard / low-disk warning)."""
    rec_dir = _recordings_dir()
    total = 0
    count = 0
    try:
        for f in os.listdir(rec_dir):
            if not _safe_recording_basename(f):
                continue
            path = os.path.join(rec_dir, f)
            if os.path.isfile(path):
                total += os.path.getsize(path)
                count += 1
    except Exception:
        pass
    free_bytes = total_bytes_partition = None
    try:
        usage = shutil.disk_usage(rec_dir)
        free_bytes = usage.free
        total_bytes_partition = usage.total
    except Exception:
        pass
    return total, count, free_bytes, total_bytes_partition


def _safe_recording_basename(name):
    """Allow only recording_<digits>.avi to prevent path traversal."""
    return name if re.match(r'^recording_\d+\.avi$', name) else None


@app.route('/recordings')
@require_role('viewer', 'operator', 'admin')
def list_recordings():
    """List available recording files (NISTIR 8161 / evidence export)."""
    rec_dir = _recordings_dir()
    result = []
    try:
        for f in os.listdir(rec_dir):
            if not _safe_recording_basename(f):
                continue
            path = os.path.join(rec_dir, f)
            if not os.path.isfile(path):
                continue
            stat = os.stat(path)
            result.append({
                'name': f,
                'size_bytes': stat.st_size,
                'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(stat.st_mtime)),
            })
    except Exception:
        pass
    result.sort(key=lambda x: x['created_utc'], reverse=True)
    return jsonify({'recordings': result})


def _compute_recording_sha256(path: str) -> str | None:
    """Compute SHA-256 of a recording file. Returns hex digest or None on error (OSAC/SWGDE fixity)."""
    try:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _export_recording_file(path: str, as_mp4: bool):
    """If as_mp4 True and ffmpeg available, convert AVI to MP4 and return (temp_path, download_name, mimetype, sha256). Else return (path, basename, mimetype, sha256). Caller must unlink temp_path if different from path."""
    import subprocess
    import tempfile
    basename = os.path.basename(path)
    if not as_mp4:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return path, basename, 'video/x-msvideo', h.hexdigest(), None
    out_fd, out_path = tempfile.mkstemp(suffix='.mp4')
    os.close(out_fd)
    try:
        subprocess.run(
            ['ffmpeg', '-y', '-i', path, '-c', 'copy', out_path],
            capture_output=True, timeout=300, check=True
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        try:
            os.unlink(out_path)
        except Exception:
            pass
        return None, None, None, None, 'ffmpeg not available or conversion failed'
    h = hashlib.sha256()
    with open(out_path, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    mp4_name = basename.replace('.avi', '.mp4') if basename.endswith('.avi') else basename + '.mp4'
    return out_path, mp4_name, 'video/mp4', h.hexdigest(), out_path


@app.route('/recordings/<path:filename>/export')
@require_role('operator', 'admin')
def export_recording(filename):
    """Export a recording with NISTIR 8161-style metadata and SHA-256 integrity (chain of custody). Optional ?format=mp4 when ffmpeg available."""
    if os.environ.get('EXPORT_REQUIRES_APPROVAL', '').strip().lower() in ('1', 'true', 'yes') and session.get('role') != 'admin':
        return jsonify({'error': 'Export requires admin approval', 'message': 'Only an administrator can export recordings when EXPORT_REQUIRES_APPROVAL is set.'}), 403
    basename = os.path.basename(filename)
    if not _safe_recording_basename(basename):
        return jsonify({'error': 'Invalid recording name'}), 400
    rec_dir = _recordings_dir()
    path = os.path.join(rec_dir, basename)
    if not os.path.isfile(path):
        return jsonify({'error': 'Not found'}), 404
    as_mp4 = request.args.get('format', '').lower() == 'mp4'
    result = _export_recording_file(path, as_mp4)
    if len(result) == 5 and result[0] is None:
        _, _, _, _, err = result
        if as_mp4:
            return jsonify({'error': err or 'MP4 conversion unavailable'}), 503
        return jsonify({'error': 'Export failed'}), 500
    file_path, download_name, mimetype, export_hash, temp_path = result
    operator = session.get('username') or 'unknown'
    export_utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    try:
        system_id = os.environ.get('SYSTEM_ID') or platform.node() or 'surveillance'
    except Exception:
        system_id = 'surveillance'
    from flask import send_file
    try:
        retention_days = int(os.environ.get('RETENTION_DAYS', '0'))
    except (TypeError, ValueError):
        retention_days = 0
    try:
        resp = send_file(file_path, as_attachment=True, download_name=download_name, mimetype=mimetype)
        resp.headers['X-Export-UTC'] = export_utc
        resp.headers['X-Operator'] = operator
        resp.headers['X-System-ID'] = system_id
        resp.headers['X-Camera-ID'] = '0'
        resp.headers['X-Export-SHA256'] = export_hash
        resp.headers['X-Retention-Policy-Days'] = str(retention_days)
        _audit(operator, 'export_recording', 'recordings', download_name)
        return resp
    finally:
        if temp_path and temp_path != path and os.path.isfile(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass


@app.route('/recordings/<path:filename>/play')
@require_role('viewer', 'operator', 'admin')
def recording_play(filename):
    """Serve recording for inline playback (video element). Use ?format=mp4 for browser-friendly playback when ffmpeg is available. Supports Range requests for seeking."""
    basename = os.path.basename(filename)
    if not _safe_recording_basename(basename):
        return jsonify({'error': 'Invalid recording name'}), 400
    rec_dir = _recordings_dir()
    path = os.path.join(rec_dir, basename)
    if not os.path.isfile(path):
        return jsonify({'error': 'Not found'}), 404
    from flask import send_file
    as_mp4 = request.args.get('format', '').lower() == 'mp4'
    if as_mp4:
        result = _export_recording_file(path, as_mp4=True)
        if result[0] is not None and result[1] is not None:
            file_path, _, mimetype, _, temp_path = result
            try:
                return send_file(
                    file_path,
                    mimetype=mimetype or 'video/mp4',
                    as_attachment=False,
                    download_name=None,
                    conditional=True,
                    etag=True,
                )
            finally:
                if temp_path and temp_path != path and os.path.isfile(temp_path):
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass
        # Fall back to AVI if MP4 conversion failed
    return send_file(
        path,
        mimetype='video/x-msvideo',
        as_attachment=False,
        download_name=None,
        conditional=True,
        etag=True,
    )


@app.route('/recordings/<path:filename>/manifest')
@require_role('viewer', 'operator', 'admin')
def recording_manifest(filename):
    """Return NISTIR 8161-style manifest (metadata + SHA-256) for a recording without downloading the file. Includes fixity stored hash/checked_at when available (OSAC/SWGDE)."""
    basename = os.path.basename(filename)
    if not _safe_recording_basename(basename):
        return jsonify({'error': 'Invalid recording name'}), 400
    path = os.path.join(_recordings_dir(), basename)
    if not os.path.isfile(path):
        return jsonify({'error': 'Not found'}), 404
    current_sha256 = _compute_recording_sha256(path)
    if not current_sha256:
        return jsonify({'error': 'Could not compute hash'}), 500
    out = {
        'filename': basename,
        'size_bytes': os.stat(path).st_size,
        'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(os.path.getmtime(path))),
        'sha256': current_sha256,
        'system_id': os.environ.get('SYSTEM_ID') or platform.node() or 'surveillance',
        'camera_id': '0',
    }
    try:
        get_cursor().execute('SELECT sha256, checked_at FROM recording_fixity WHERE path = ?', (basename,))
        row = get_cursor().fetchone()
        if row:
            out['fixity_stored_sha256'] = row[0]
            out['fixity_checked_at'] = row[1]
            out['fixity_match'] = row[0] == current_sha256
    except Exception:
        pass
    return jsonify(out)


@app.route('/toggle_motion', methods=['POST'])
def toggle_motion():
    return jsonify({'motion': request.json.get('motion', False)})


def _ptz_move_onvif(direction):
    if _onvif_ptz is None or _onvif_profile_token is None:
        return False
    try:
        if direction == 'stop':
            _onvif_ptz.Stop({'ProfileToken': _onvif_profile_token})
            return True
        vel = 0.3
        if direction == 'left':
            request = _onvif_ptz.create_type('ContinuousMove')
            request.ProfileToken = _onvif_profile_token
            request.Velocity = _onvif_ptz.GetStatus({'ProfileToken': _onvif_profile_token}).Position
            request.Velocity.PanTilt = {'x': -vel, 'y': 0}
            _onvif_ptz.ContinuousMove(request)
        elif direction == 'right':
            request = _onvif_ptz.create_type('ContinuousMove')
            request.ProfileToken = _onvif_profile_token
            request.Velocity = _onvif_ptz.GetStatus({'ProfileToken': _onvif_profile_token}).Position
            request.Velocity.PanTilt = {'x': vel, 'y': 0}
            _onvif_ptz.ContinuousMove(request)
        else:
            _onvif_ptz.Stop({'ProfileToken': _onvif_profile_token})
        return True
    except Exception:
        return False


_ptz_auto_follow_last_time = 0.0
AUTO_PTZ_FOLLOW_COOLDOWN = 3.0  # seconds between auto-follow moves


def _ptz_auto_follow_from_bbox(frame, results):
    """Auto PTZ: move camera to keep largest detected person near center. ONVIF only; rate-limited."""
    global _ptz_auto_follow_last_time
    if _onvif_ptz is None or _onvif_profile_token is None or not results or not results[0].boxes:
        return
    if os.environ.get('AUTO_PTZ_FOLLOW', '').strip().lower() not in ('1', 'true', 'yes'):
        return
    now = time.time()
    if now - _ptz_auto_follow_last_time < AUTO_PTZ_FOLLOW_COOLDOWN:
        return
    h, w = frame.shape[:2]
    names = results[0].names
    boxes = results[0].boxes
    best = None
    best_area = 0
    for i, cls in enumerate(boxes.cls):
        if names.get(int(cls), '').lower() != 'person':
            continue
        xyxy = boxes.xyxy[i].cpu().numpy()
        area = (xyxy[2] - xyxy[0]) * (xyxy[3] - xyxy[1])
        if area > best_area:
            best_area = area
            best = xyxy
    if best is None:
        return
    cx = (best[0] + best[2]) / 2
    cy = (best[1] + best[3]) / 2
    center_x, center_y = w / 2.0, h / 2.0
    dx = cx - center_x
    dy = cy - center_y
    if abs(dx) < 30 and abs(dy) < 30:
        return
    gain = 0.002
    pan_vel = max(-0.3, min(0.3, dx * gain))
    tilt_vel = max(-0.3, min(0.3, dy * gain))
    try:
        request = _onvif_ptz.create_type('ContinuousMove')
        request.ProfileToken = _onvif_profile_token
        request.Velocity = _onvif_ptz.GetStatus({'ProfileToken': _onvif_profile_token}).Position
        request.Velocity.PanTilt = {'x': float(pan_vel), 'y': float(tilt_vel)}
        _onvif_ptz.ContinuousMove(request)
        _ptz_auto_follow_last_time = now
        def _stop_after():
            time.sleep(0.35)
            try:
                _onvif_ptz.Stop({'ProfileToken': _onvif_profile_token})
            except Exception:
                pass
        threading.Thread(target=_stop_after, daemon=True).start()
    except Exception:
        pass


@app.route('/move_camera', methods=['POST'])
def move_camera():
    direction = request.get_json(silent=True) and request.json.get('direction', 'stop') or 'stop'
    if _onvif_ptz is not None and _onvif_profile_token is not None:
        if _ptz_move_onvif(direction):
            _audit(session.get('username'), 'move_camera', 'ptz', direction)
            return jsonify({'status': 'success', 'method': 'onvif'})
    if GPIO_AVAILABLE:
        import RPi.GPIO as GPIO  # type: ignore[reportMissingModuleSource]
        speed = 50
        if direction == 'left':
            GPIO.output(23, True)
            GPIO.output(24, False)
            motor_pwm.ChangeDutyCycle(speed)
        elif direction == 'right':
            GPIO.output(23, False)
            GPIO.output(24, True)
            motor_pwm.ChangeDutyCycle(speed)
        else:
            motor_pwm.ChangeDutyCycle(0)
        _audit(session.get('username'), 'move_camera', 'ptz', direction)
        return jsonify({'status': 'success', 'method': 'gpio'})
    return jsonify({'status': 'unavailable', 'message': 'No PTZ (ONVIF or GPIO) available'}), 503


def _audit_saved_search_run_if_requested():
    """If request includes saved_search_id and user is logged in, verify ownership and log saved_search_run to audit (NIST AU-9)."""
    raw = request.args.get('saved_search_id')
    if not raw or not session.get('user_id'):
        return
    try:
        sid = int(raw)
    except (TypeError, ValueError):
        return
    uid = session.get('user_id')
    try:
        get_cursor().execute('SELECT 1 FROM saved_searches WHERE id = ? AND user_id = ?', (sid, uid))
        if get_cursor().fetchone():
            _audit(session.get('username'), 'saved_search_run', 'saved_searches', str(sid))
    except Exception:
        pass


def _parse_filters():
    """Parse and validate common query params for get_data and list_events. Canonical API validation: limit (cap 1000), offset (≥0), date_from/date_to (YYYY-MM-DD). See docs/APP_REVIEW_AND_RATING.md."""
    try:
        limit = int(request.args.get('limit', 100))
    except (TypeError, ValueError):
        limit = 100
    limit = max(1, min(limit, 1000))
    try:
        offset = int(request.args.get('offset', 0))
    except (TypeError, ValueError):
        offset = 0
    offset = max(0, offset)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if date_from and len(date_from) == 10 and date_from[:4].isdigit() and date_from[5:7].isdigit() and date_from[8:10].isdigit():
        pass
    else:
        date_from = None
    if date_to and len(date_to) == 10 and date_to[:4].isdigit() and date_to[5:7].isdigit() and date_to[8:10].isdigit():
        pass
    else:
        date_to = None
    return limit, offset, date_from, date_to


@app.route('/get_data')
def get_data():
    _audit_saved_search_run_if_requested()
    limit, offset, date_from, date_to = _parse_filters()
    camera_id = request.args.get('camera_id')
    event_type = request.args.get('event_type')
    sql = 'SELECT * FROM ai_data WHERE 1=1'
    params = []
    if date_from:
        sql += ' AND date >= ?'
        params.append(date_from)
    if date_to:
        sql += ' AND date <= ?'
        params.append(date_to)
    if event_type:
        sql += ' AND event = ?'
        params.append(event_type)
    allowed_sites = _get_user_allowed_site_ids()
    if allowed_sites is not None:
        get_cursor().execute('SELECT camera_id FROM camera_positions WHERE site_id IN (%s)' % ','.join('?' * len(allowed_sites)), allowed_sites)
        allowed_cameras = [r[0] for r in get_cursor().fetchall()]
        if allowed_cameras:
            sql += ' AND camera_id IN (%s)' % ','.join('?' * len(allowed_cameras))
            params.extend(allowed_cameras)
        else:
            sql += ' AND 1=0'
    if camera_id:
        sql += ' AND camera_id = ?'
        params.append(camera_id)
    # Prefer timestamp_utc for ordering when present (correct across date boundaries)
    try:
        get_cursor().execute("SELECT 1 FROM ai_data WHERE timestamp_utc IS NOT NULL AND timestamp_utc != '' LIMIT 1")
        if get_cursor().fetchone():
            sql += ' ORDER BY timestamp_utc DESC LIMIT ? OFFSET ?'
        else:
            sql += ' ORDER BY date DESC, time DESC LIMIT ? OFFSET ?'
    except Exception:
        sql += ' ORDER BY date DESC, time DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])
    get_cursor().execute(sql, params)
    rows = get_cursor().fetchall()
    cols = [d[0] for d in get_cursor().description]
    data = [dict(zip(cols, row)) for row in rows]
    etag = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    if request.headers.get('If-None-Match', '').strip('"') == etag:
        r = make_response('', 304)
        r.headers['ETag'] = '"' + etag + '"'
        return r
    r = jsonify(data)
    r.headers['ETag'] = '"' + etag + '"'
    return r


@app.route('/events')
def list_events():
    if (os.environ.get('USE_REACT_APP', '').lower() in ('1', 'true', 'yes') and
            request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'text/html'):
        html = _send_react_index()
        if html:
            return make_response(html)
    _audit_saved_search_run_if_requested()
    limit, offset, date_from, date_to = _parse_filters()
    camera_id = request.args.get('camera_id')
    event_type = request.args.get('event_type')
    severity = request.args.get('severity')
    acknowledged = request.args.get('acknowledged')  # 'true' | 'false' | omit for all
    site_id = request.args.get('site_id')
    sql = 'SELECT id, event_type, camera_id, site_id, timestamp, timestamp_utc, metadata, severity, acknowledged_by, acknowledged_at, integrity_hash FROM events WHERE 1=1'
    params = []
    allowed_sites = _get_user_allowed_site_ids()
    if allowed_sites is not None:
        sql += ' AND site_id IN (%s)' % ','.join('?' * len(allowed_sites))
        params.extend(allowed_sites)
    if date_from:
        sql += ' AND date(timestamp) >= ?'
        params.append(date_from)
    if date_to:
        sql += ' AND date(timestamp) <= ?'
        params.append(date_to)
    if site_id:
        sql += ' AND site_id = ?'
        params.append(site_id)
    if camera_id:
        sql += ' AND camera_id = ?'
        params.append(camera_id)
    if event_type:
        sql += ' AND event_type = ?'
        params.append(event_type)
    if severity:
        sql += ' AND severity = ?'
        params.append(severity)
    if acknowledged == 'true':
        sql += ' AND acknowledged_at IS NOT NULL'
    elif acknowledged == 'false':
        sql += ' AND acknowledged_at IS NULL'
    sql += ' ORDER BY timestamp_utc DESC, timestamp DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])
    get_cursor().execute(sql, params)
    rows = get_cursor().fetchall()
    cols = ['id', 'event_type', 'camera_id', 'site_id', 'timestamp', 'timestamp_utc', 'metadata', 'severity', 'acknowledged_by', 'acknowledged_at', 'integrity_hash']
    data = [dict(zip(cols, row)) for row in rows]
    etag = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    if request.headers.get('If-None-Match', '').strip('"') == etag:
        r = make_response('', 304)
        r.headers['ETag'] = '"' + etag + '"'
        return r
    r = jsonify(data)
    r.headers['ETag'] = '"' + etag + '"'
    return r


@app.route('/events', methods=['POST'])
def create_event():
    data = request.get_json() or {}
    event_type = data.get('event_type') or 'motion'
    camera_id = data.get('camera_id') or '0'
    site_id = data.get('site_id') or 'default'
    metadata = data.get('metadata')
    severity = data.get('severity') or 'medium'
    meta_str = json.dumps(metadata) if metadata is not None else None
    ev_ts_utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    ev_hash = _event_integrity_hash(ev_ts_utc, event_type, camera_id, site_id, meta_str, severity)
    get_cursor().execute(
        '''INSERT INTO events (event_type, camera_id, site_id, timestamp, timestamp_utc, metadata, severity, integrity_hash)
           VALUES (?, ?, ?, datetime("now"), ?, ?, ?, ?)''',
        (event_type, camera_id, site_id, ev_ts_utc, meta_str, severity, ev_hash)
    )
    get_conn().commit()
    _broadcast_event({'type': 'new_event'})
    _trigger_alert(event_type, severity, meta_str)
    return jsonify({'success': True, 'id': get_cursor().lastrowid})


@app.route('/events/<int:event_id>/acknowledge', methods=['POST'])
@require_role('viewer', 'operator', 'admin')
def acknowledge_event(event_id):
    allowed_sites = _get_user_allowed_site_ids()
    if allowed_sites is not None:
        get_cursor().execute('SELECT site_id FROM events WHERE id = ?', (event_id,))
        row = get_cursor().fetchone()
        if not row or row[0] not in allowed_sites:
            return jsonify({'success': False, 'message': 'Event not found'}), 404
    user = session.get('username') or request.get_json(silent=True) and request.json.get('user') or 'unknown'
    get_cursor().execute(
        'UPDATE events SET acknowledged_by = ?, acknowledged_at = datetime("now") WHERE id = ?',
        (user, event_id)
    )
    get_conn().commit()
    if get_cursor().rowcount == 0:
        return jsonify({'success': False, 'message': 'Event not found'}), 404
    _audit(session.get('username'), 'acknowledge_event', 'events', str(event_id))
    return jsonify({'success': True})


# ---------- API v1 (enterprise / scale) ----------
@app.route('/api/v1/analytics/aggregates')
def api_v1_analytics_aggregates():
    """Time-series aggregates by camera and event type for dashboards/heatmaps. Bucket by hour."""
    date_from = request.args.get('date_from') or time.strftime('%Y-%m-%d', time.gmtime(time.time() - 7 * 86400))
    date_to = request.args.get('date_to') or time.strftime('%Y-%m-%d')
    try:
        bucket_hours = max(1, min(24, int(request.args.get('bucket_hours', '1'))))
    except (TypeError, ValueError):
        bucket_hours = 1
    camera_id = request.args.get('camera_id')
    site_id = request.args.get('site_id')
    sql = """SELECT date, strftime('%H', time) AS hour, event, camera_id, COUNT(*) AS cnt, SUM(crowd_count) AS total_crowd
             FROM ai_data WHERE date >= ? AND date <= ?"""
    params = [date_from, date_to]
    if camera_id:
        sql += ' AND camera_id = ?'
        params.append(camera_id)
    sql += " GROUP BY date, hour, event, camera_id ORDER BY date, hour"
    try:
        get_cursor().execute(sql, params)
        rows = get_cursor().fetchall()
    except sqlite3.OperationalError:
        try:
            get_cursor().execute("""SELECT date, strftime('%H', time) AS hour, event, COUNT(*) AS cnt, SUM(crowd_count) AS total_crowd
                              FROM ai_data WHERE date >= ? AND date <= ? GROUP BY date, hour, event ORDER BY date, hour""",
                           (date_from, date_to))
            rows = [(r[0], r[1], r[2], '0', r[3], r[4]) for r in get_cursor().fetchall()]
        except Exception:
            return jsonify({'aggregates': [], 'bucket_hours': bucket_hours}), 200
    cols = ['date', 'hour', 'event', 'camera_id', 'count', 'total_crowd']
    aggregates = [dict(zip(cols, row)) for row in rows]
    allowed_sites = _get_user_allowed_site_ids()
    if allowed_sites is not None:
        get_cursor().execute('SELECT camera_id FROM camera_positions WHERE site_id IN (%s)' % ','.join('?' * len(allowed_sites)), allowed_sites)
        allowed_cameras = {r[0] for r in get_cursor().fetchall()}
        aggregates = [a for a in aggregates if a.get('camera_id') in allowed_cameras]
    elif site_id:
        get_cursor().execute('SELECT camera_id FROM camera_positions WHERE site_id = ?', (site_id,))
        allowed_cameras = {r[0] for r in get_cursor().fetchall()}
        aggregates = [a for a in aggregates if a.get('camera_id') in allowed_cameras]
    return jsonify({'aggregates': aggregates, 'bucket_hours': bucket_hours})


def _search_impl(q: str, limit: int, date_from=None, date_to=None, camera_id=None, event_type=None):
    """Shared search logic for GET and POST /api/v1/search. RBAC applied inside."""
    like = f'%{q}%'
    allowed_sites = _get_user_allowed_site_ids()
    events_sql = """SELECT id, event_type, camera_id, site_id, timestamp, metadata, severity
                    FROM events WHERE event_type LIKE ? OR metadata LIKE ?"""
    params_ev = [like, like]
    if date_from:
        events_sql += ' AND date(timestamp) >= ?'
        params_ev.append(date_from)
    if date_to:
        events_sql += ' AND date(timestamp) <= ?'
        params_ev.append(date_to)
    if event_type:
        events_sql += ' AND event_type = ?'
        params_ev.append(event_type)
    if camera_id:
        events_sql += ' AND camera_id = ?'
        params_ev.append(camera_id)
    if allowed_sites is not None:
        events_sql += ' AND site_id IN (%s)' % ','.join('?' * len(allowed_sites))
        params_ev.extend(allowed_sites)
    events_sql += ' ORDER BY timestamp DESC LIMIT ?'
    params_ev.append(limit)
    get_cursor().execute(events_sql, params_ev)
    ev_cols = ['id', 'event_type', 'camera_id', 'site_id', 'timestamp', 'metadata', 'severity']
    events = [dict(zip(ev_cols, row)) for row in get_cursor().fetchall()]
    allowed_cameras = None
    if allowed_sites is not None:
        get_cursor().execute('SELECT camera_id FROM camera_positions WHERE site_id IN (%s)' % ','.join('?' * len(allowed_sites)), allowed_sites)
        allowed_cameras = {r[0] for r in get_cursor().fetchall()}
    try:
        ad_sql = """SELECT * FROM ai_data WHERE object LIKE ? OR event LIKE ? OR scene LIKE ? OR license_plate LIKE ?
                    OR COALESCE(suspicious_behavior,'') LIKE ? OR COALESCE(predicted_intent,'') LIKE ?
                    OR COALESCE(stress_level,'') LIKE ? OR COALESCE(hair_color,'') LIKE ? OR COALESCE(build,'') LIKE ?
                    OR COALESCE(perceived_gender,'') LIKE ? OR COALESCE(perceived_age_range,'') LIKE ?
                    OR COALESCE(clothing_description,'') LIKE ? OR COALESCE(gait_notes,'') LIKE ?
                    OR COALESCE(intoxication_indicator,'') LIKE ? OR COALESCE(micro_expression,'') LIKE ?
                    OR COALESCE(attention_region,'') LIKE ? OR COALESCE(illumination_band,'') LIKE ? OR COALESCE(period_of_day_utc,'') LIKE ?
                    OR CAST(centroid_nx AS TEXT) LIKE ? OR CAST(centroid_ny AS TEXT) LIKE ?
                    OR CAST(world_x AS TEXT) LIKE ? OR CAST(world_y AS TEXT) LIKE ?
                    OR COALESCE(audio_event,'') LIKE ? OR COALESCE(audio_transcription,'') LIKE ?
                    OR COALESCE(audio_sentiment,'') LIKE ? OR COALESCE(audio_emotion,'') LIKE ?
                    OR COALESCE(audio_stress_level,'') LIKE ? OR COALESCE(audio_keywords,'') LIKE ?
                    OR COALESCE(device_mac,'') LIKE ? OR COALESCE(device_oui_vendor,'') LIKE ?
                    OR COALESCE(device_probe_ssids,'') LIKE ?"""
        ad_params = [like] * 28
        if date_from:
            ad_sql += ' AND date >= ?'
            ad_params.append(date_from)
        if date_to:
            ad_sql += ' AND date <= ?'
            ad_params.append(date_to)
        if camera_id:
            ad_sql += ' AND camera_id = ?'
            ad_params.append(camera_id)
        if event_type:
            ad_sql += ' AND event = ?'
            ad_params.append(event_type)
        if allowed_cameras is not None:
            if not allowed_cameras:
                ad_sql += ' AND 1=0'
            else:
                ad_sql += ' AND camera_id IN (%s)' % ','.join('?' * len(allowed_cameras))
                ad_params.extend(allowed_cameras)
        ad_sql += ' ORDER BY date DESC, time DESC LIMIT ?'
        ad_params.append(limit)
        get_cursor().execute(ad_sql, ad_params)
        ad_cols = [d[0] for d in get_cursor().description]
        ai_data = [dict(zip(ad_cols, row)) for row in get_cursor().fetchall()]
    except sqlite3.OperationalError:
        ad_sql = """SELECT date, time, object, event, scene, license_plate, crowd_count, camera_id
                    FROM ai_data WHERE object LIKE ? OR event LIKE ? OR scene LIKE ? OR license_plate LIKE ?"""
        ad_params = [like, like, like, like]
        if date_from:
            ad_sql += ' AND date >= ?'
            ad_params.append(date_from)
        if date_to:
            ad_sql += ' AND date <= ?'
            ad_params.append(date_to)
        if camera_id:
            ad_sql += ' AND camera_id = ?'
            ad_params.append(camera_id)
        if allowed_cameras is not None and allowed_cameras:
            ad_sql += ' AND camera_id IN (%s)' % ','.join('?' * len(allowed_cameras))
            ad_params.extend(allowed_cameras)
        ad_sql += ' ORDER BY date DESC, time DESC LIMIT ?'
        ad_params.append(limit)
        get_cursor().execute(ad_sql, ad_params)
        ad_cols = [d[0] for d in get_cursor().description]
        ai_data = [dict(zip(ad_cols, row)) for row in get_cursor().fetchall()]
        if allowed_cameras is not None:
            ai_data = [a for a in ai_data if a.get('camera_id', '0') in allowed_cameras]
    return {'events': events, 'ai_data': ai_data}


@app.route('/api/v1/search', methods=['GET', 'POST'])
def api_v1_search():
    """Natural-language / keyword search over events and ai_data. GET: q, date_from, date_to, camera_id, event_type, limit."""
    if request.method == 'GET':
        q = (request.args.get('q') or request.args.get('query') or '').strip()
        limit = min(int(request.args.get('limit', 50)), 200)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        camera_id = request.args.get('camera_id') or None
        event_type = request.args.get('event_type') or None
    else:
        data = request.get_json() or {}
        q = (data.get('q') or data.get('query') or '').strip()
        limit = min(int(data.get('limit', 50)), 200)
        date_from = data.get('date_from') or request.args.get('date_from')
        date_to = data.get('date_to') or request.args.get('date_to')
        camera_id = data.get('camera_id') or request.args.get('camera_id')
        event_type = data.get('event_type') or request.args.get('event_type')
    if not q:
        return jsonify({'events': [], 'ai_data': [], 'message': 'Provide q or query'})
    nl_url = os.environ.get('NL_SEARCH_WEBHOOK_URL', '').strip()
    if nl_url:
        try:
            from urllib.request import Request, urlopen
            payload = json.dumps({'q': q, 'date_from': date_from, 'date_to': date_to, 'limit': limit}).encode()
            req = Request(nl_url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
            r = urlopen(req, timeout=15)
            body = r.read().decode()
            data = json.loads(body) if body else {}
            event_ids = data.get('event_ids') or []
            ai_data_rowids = data.get('ai_data_rowids') or data.get('ai_data_ids') or []
            if isinstance(event_ids, list) and event_ids:
                event_ids = event_ids[:limit]
                placeholders = ','.join('?' * len(event_ids))
                get_cursor().execute(
                    f'SELECT id, event_type, camera_id, site_id, timestamp, metadata, severity FROM events WHERE id IN ({placeholders}) ORDER BY timestamp DESC',
                    event_ids,
                )
                ev_cols = ['id', 'event_type', 'camera_id', 'site_id', 'timestamp', 'metadata', 'severity']
                events = [dict(zip(ev_cols, row)) for row in get_cursor().fetchall()]
            else:
                events = []
            if isinstance(ai_data_rowids, list) and ai_data_rowids:
                ai_data_rowids = ai_data_rowids[:limit]
                placeholders = ','.join('?' * len(ai_data_rowids))
                get_cursor().execute(
                    f'SELECT * FROM ai_data WHERE rowid IN ({placeholders}) ORDER BY date DESC, time DESC',
                    ai_data_rowids,
                )
                ad_cols = [d[0] for d in get_cursor().description]
                ai_data = [dict(zip(ad_cols, row)) for row in get_cursor().fetchall()]
            else:
                ai_data = []
            if events or ai_data:
                result = {'events': events, 'ai_data': ai_data}
            else:
                result = _search_impl(q, limit, date_from=date_from, date_to=date_to, camera_id=camera_id, event_type=event_type)
        except Exception:
            result = _search_impl(q, limit, date_from=date_from, date_to=date_to, camera_id=camera_id, event_type=event_type)
    else:
        result = _search_impl(q, limit, date_from=date_from, date_to=date_to, camera_id=camera_id, event_type=event_type)
    try:
        _audit(
            session.get('username'),
            'search',
            'api/v1/search',
            json.dumps({'q': q[:200], 'limit': limit, 'date_from': date_from, 'date_to': date_to, 'event_type': event_type, 'result_events': len(result['events']), 'result_ai_data': len(result['ai_data'])})
        )
    except Exception:
        pass
    return jsonify(result)


@app.route('/api/v1/users/<int:user_id>/sites', methods=['GET'])
@require_role('admin')
def api_v1_user_sites_get(user_id):
    """Get allowed site_ids for a user (resource-level RBAC). Empty = no restrictions (all sites)."""
    get_cursor().execute('SELECT site_id FROM user_site_roles WHERE user_id = ?', (user_id,))
    site_ids = [r[0] for r in get_cursor().fetchall()]
    return jsonify({'user_id': user_id, 'site_ids': site_ids})


@app.route('/api/v1/users/<int:user_id>/sites', methods=['PUT'])
@require_role('admin')
def api_v1_user_sites_put(user_id):
    """Set allowed site_ids for a user. Empty list = no restrictions (all sites)."""
    data = request.get_json() or {}
    site_ids = data.get('site_ids')
    if site_ids is None:
        return jsonify({'error': 'site_ids required'}), 400
    get_cursor().execute('DELETE FROM user_site_roles WHERE user_id = ?', (user_id,))
    for sid in site_ids:
        if sid:
            try:
                get_cursor().execute('INSERT OR IGNORE INTO user_site_roles (user_id, site_id) VALUES (?, ?)', (user_id, sid))
            except Exception:
                pass
    get_conn().commit()
    _audit(session.get('username'), 'config_change', 'user_site_roles', f'user_id={user_id}')
    get_cursor().execute('SELECT site_id FROM user_site_roles WHERE user_id = ?', (user_id,))
    return jsonify({'user_id': user_id, 'site_ids': [r[0] for r in get_cursor().fetchall()]})


@app.route('/api/v1/reset_data', methods=['POST'])
@require_role('admin')
def api_v1_reset_data():
    """Delete all events and ai_data so dashboard counts reset to zero. Recordings, users, and audit_log are not touched. Admin only."""
    try:
        cur = get_cursor()
        cur.execute('DELETE FROM events')
        cur.execute('DELETE FROM ai_data')
        get_conn().commit()
        _audit(session.get('username'), 'reset_data', 'events,ai_data', 'deleted all rows')
        return jsonify({'success': True})
    except Exception as e:
        try:
            get_conn().rollback()
        except Exception:
            pass
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/v1/users')
@require_role('admin')
def api_v1_users_list():
    """List users (id, username, role) for admin RBAC assignment."""
    get_cursor().execute('SELECT id, username, role FROM users ORDER BY id')
    return jsonify({'users': [dict(zip(['id', 'username', 'role'], r)) for r in get_cursor().fetchall()]})


@app.route('/api/v1/legal_hold', methods=['GET'])
@require_role('operator', 'admin')
def api_v1_legal_hold_list():
    """List all legal holds (for evidence preservation)."""
    get_cursor().execute('SELECT id, resource_type, resource_id, held_at, held_by, reason FROM legal_hold ORDER BY held_at DESC')
    rows = get_cursor().fetchall()
    return jsonify({'holds': [dict(zip(['id', 'resource_type', 'resource_id', 'held_at', 'held_by', 'reason'], r)) for r in rows]})


@app.route('/api/v1/legal_hold', methods=['POST'])
@require_role('operator', 'admin')
def api_v1_legal_hold_add():
    """Place a legal hold on a recording or event. resource_type: 'recording'|'event', resource_id: filename or event id."""
    data = request.get_json() or {}
    resource_type = (data.get('resource_type') or '').strip().lower()
    resource_id = (data.get('resource_id') or '').strip()
    reason = (data.get('reason') or '').strip() or None
    if resource_type not in ('recording', 'event') or not resource_id:
        return jsonify({'error': 'resource_type must be recording|event and resource_id required'}), 400
    if resource_type == 'event':
        resource_id = str(int(resource_id))
    held_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    held_by = session.get('username') or 'operator'
    try:
        get_cursor().execute(
            'INSERT INTO legal_hold (resource_type, resource_id, held_at, held_by, reason) VALUES (?, ?, ?, ?, ?)',
            (resource_type, resource_id, held_at, held_by, reason)
        )
        get_conn().commit()
        hold_id = get_cursor().lastrowid
        _audit(session.get('username'), 'legal_hold', resource_type, f'resource_id={resource_id} reason={reason or ""}')
        _log_structured('legal_hold_add', user=session.get('username'), resource_type=resource_type, resource_id=resource_id)
        return jsonify({'id': hold_id, 'resource_type': resource_type, 'resource_id': resource_id, 'held_at': held_at, 'held_by': held_by})
    except sqlite3.IntegrityError:
        get_cursor().execute('SELECT id FROM legal_hold WHERE resource_type = ? AND resource_id = ?', (resource_type, resource_id))
        row = get_cursor().fetchone()
        return jsonify({'id': row[0], 'resource_type': resource_type, 'resource_id': resource_id, 'message': 'Already held'}), 200


@app.route('/api/v1/legal_hold/<int:hold_id>', methods=['DELETE'])
@require_role('admin')
def api_v1_legal_hold_remove(hold_id):
    """Remove a legal hold (admin only)."""
    get_cursor().execute('DELETE FROM legal_hold WHERE id = ?', (hold_id,))
    get_conn().commit()
    if get_cursor().rowcount:
        _audit(session.get('username'), 'legal_hold_remove', 'legal_hold', f'id={hold_id}')
        _log_structured('legal_hold_remove', user=session.get('username'), hold_id=hold_id)
        return jsonify({'success': True})
    return jsonify({'error': 'Not found'}), 404


@app.route('/api/v1/saved_searches', methods=['GET'])
@require_role('viewer', 'operator', 'admin')
def api_v1_saved_searches_list():
    """List saved searches for current user (NIST AU-9: saved searches + audit). When running a search, pass saved_search_id on GET /get_data or GET /events to log saved_search_run to the audit log."""
    uid = session.get('user_id')
    if not uid:
        return jsonify({'error': 'Login required'}), 401
    get_cursor().execute('SELECT id, name, params_json, created_at FROM saved_searches WHERE user_id = ? ORDER BY created_at DESC', (uid,))
    rows = get_cursor().fetchall()
    return jsonify({'saved_searches': [dict(zip(['id', 'name', 'params_json', 'created_at'], r)) for r in rows]})


@app.route('/api/v1/saved_searches', methods=['POST'])
@require_role('viewer', 'operator', 'admin')
def api_v1_saved_searches_add():
    """Create a saved search. params_json: JSON object (e.g. date_from, date_to, event_type)."""
    uid = session.get('user_id')
    if not uid:
        return jsonify({'error': 'Login required'}), 401
    data = request.get_json() or {}
    name = (data.get('name') or '').strip() or 'Unnamed'
    params = data.get('params') or data.get('params_json') or {}
    params_json = json.dumps(params) if isinstance(params, dict) else str(params)
    created = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    get_cursor().execute('INSERT INTO saved_searches (user_id, name, params_json, created_at) VALUES (?, ?, ?, ?)', (uid, name[:200], params_json, created))
    get_conn().commit()
    sid = get_cursor().lastrowid
    _audit(session.get('username'), 'saved_search_create', 'saved_searches', f'id={sid} name={name[:50]}')
    return jsonify({'id': sid, 'name': name, 'params': params, 'created_at': created})


@app.route('/api/v1/saved_searches/<int:sid>', methods=['DELETE'])
@require_role('viewer', 'operator', 'admin')
def api_v1_saved_searches_delete(sid):
    """Delete a saved search (own only)."""
    uid = session.get('user_id')
    get_cursor().execute('DELETE FROM saved_searches WHERE id = ? AND user_id = ?', (sid, uid))
    get_conn().commit()
    if get_cursor().rowcount:
        _audit(session.get('username'), 'saved_search_delete', 'saved_searches', str(sid))
        return jsonify({'success': True})
    return jsonify({'error': 'Not found or not owner'}), 404


@app.route('/api/v1/export/incident_bundle')
@require_role('operator', 'admin')
def api_v1_incident_bundle():
    """Incident export bundle: manifest for a time range (recordings + AI data export params). Chain of custody; for insurance/LE."""
    if os.environ.get('EXPORT_REQUIRES_APPROVAL', '').strip().lower() in ('1', 'true', 'yes') and session.get('role') != 'admin':
        return jsonify({'error': 'Export requires admin approval'}), 403
    date_from = request.args.get('from', request.args.get('date_from', '')).strip()
    date_to = request.args.get('to', request.args.get('date_to', '')).strip()
    camera_id = request.args.get('camera_id', '').strip() or None
    if not date_from or not date_to:
        return jsonify({'error': 'Query params from and to (YYYY-MM-DD) required'}), 400
    try:
        retention_days = int(os.environ.get('RETENTION_DAYS', '0'))
    except (TypeError, ValueError):
        retention_days = 0
    export_utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    operator = session.get('username') or 'unknown'
    system_id = _system_id()
    rec_dir = _recordings_dir()
    recordings_in_range = []
    try:
        for f in os.listdir(rec_dir):
            if not (f.startswith('recording_') and f.endswith('.avi')):
                continue
            path = os.path.join(rec_dir, f)
            try:
                mtime = os.path.getmtime(path)
                dt = time.gmtime(mtime)
                file_date = time.strftime('%Y-%m-%d', dt)
                if date_from <= file_date <= date_to:
                    size = os.path.getsize(path)
                    item = {'name': f, 'size_bytes': size, 'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', dt)}
                    sha = _compute_recording_sha256(path)
                    if sha:
                        item['sha256_verified_at_export'] = sha
                        item['export_utc'] = export_utc
                    recordings_in_range.append(item)
            except Exception:
                pass
    except Exception:
        pass
    recordings_in_range.sort(key=lambda x: x.get('created_utc', ''))
    preservation_checklist = {
        'description': 'NIST IR 8387 / SWGDE: verify each item hash at export; retain this manifest for chain of custody.',
        'export_utc': export_utc,
        'operator': operator,
        'items': [
            {'type': 'recording', 'name': r['name'], 'sha256': r.get('sha256_verified_at_export'), 'verified_at_export_utc': export_utc}
            for r in recordings_in_range if r.get('sha256_verified_at_export')
        ] + [{'type': 'ai_data', 'export_url': f'/export_data?date_from={date_from}&date_to={date_to}', 'verified_at_export_utc': export_utc}],
    }
    manifest = {
        'export_utc': export_utc,
        'operator': operator,
        'system_id': system_id,
        'date_from': date_from,
        'date_to': date_to,
        'retention_days': retention_days,
        'camera_id_filter': camera_id,
        'recordings': recordings_in_range,
        'preservation_checklist': preservation_checklist,
        'ai_data_export_url': f'/export_data?date_from={date_from}&date_to={date_to}',
        'purpose': 'incident_bundle',
    }
    _audit(operator, 'incident_bundle', 'export', json.dumps({'from': date_from, 'to': date_to, 'recordings_count': len(recordings_in_range)}))
    return jsonify({'manifest': manifest})


@app.route('/api/v1/analytics/heatmap')
@require_role('viewer', 'operator', 'admin')
def api_v1_analytics_heatmap():
    """Heatmap data: event counts by date, hour bucket, and event type. Query: date_from, date_to, site_id, bucket_hours (default 1)."""
    date_from = request.args.get('date_from') or time.strftime('%Y-%m-%d', time.gmtime(time.time() - 7 * 86400))
    date_to = request.args.get('date_to') or time.strftime('%Y-%m-%d')
    bucket_hours = max(1, min(int(request.args.get('bucket_hours', 1)), 24))
    allowed_sites = _get_user_allowed_site_ids()
    sql = """
        SELECT date(timestamp) AS d, strftime('%H', timestamp) AS h, event_type, camera_id, COUNT(*) AS cnt
        FROM events
        WHERE date(timestamp) >= ? AND date(timestamp) <= ?
    """
    params = [date_from, date_to]
    if allowed_sites is not None:
        sql += ' AND site_id IN (%s)' % ','.join('?' * len(allowed_sites))
        params.extend(allowed_sites)
    sql += " GROUP BY d, h, event_type, camera_id ORDER BY d, h"
    get_cursor().execute(sql, params)
    rows = get_cursor().fetchall()
    buckets = []
    for r in rows:
        buckets.append({'date': r[0], 'hour': r[1], 'event_type': r[2], 'camera_id': r[3], 'count': r[4]})
    return jsonify({'heatmap': buckets, 'date_from': date_from, 'date_to': date_to, 'bucket_hours': bucket_hours})


@app.route('/api/v1/analytics/spatial_heatmap')
@require_role('viewer', 'operator', 'admin')
def api_v1_analytics_spatial_heatmap():
    """Spatial heatmap: aggregate detections by binned (centroid_nx, centroid_ny) for camera-view occupancy. Query: date_from, date_to, camera_id (optional), grid_size (default 16)."""
    date_from = request.args.get('date_from') or time.strftime('%Y-%m-%d', time.gmtime(time.time() - 7 * 86400))
    date_to = request.args.get('date_to') or time.strftime('%Y-%m-%d')
    camera_id = request.args.get('camera_id')
    try:
        grid_size = max(8, min(32, int(request.args.get('grid_size', '16'))))
    except (TypeError, ValueError):
        grid_size = 16
    allowed_sites = _get_user_allowed_site_ids()
    try:
        interval_sec = ANALYZE_INTERVAL_SECONDS
    except NameError:
        interval_sec = 10
    sql = """
        SELECT centroid_nx, centroid_ny FROM ai_data
        WHERE date >= ? AND date <= ? AND centroid_nx IS NOT NULL AND centroid_ny IS NOT NULL
    """
    params = [date_from, date_to]
    if camera_id:
        sql += ' AND camera_id = ?'
        params.append(camera_id)
    if allowed_sites is not None:
        get_cursor().execute('SELECT camera_id FROM camera_positions WHERE site_id IN (%s)' % ','.join('?' * len(allowed_sites)), allowed_sites)
        allowed_cameras = {r[0] for r in get_cursor().fetchall()}
        if not allowed_cameras:
            return jsonify({
                'grid_rows': grid_size, 'grid_cols': grid_size, 'cells': [], 'date_from': date_from, 'date_to': date_to,
                'camera_id': camera_id, 'interval_seconds': interval_sec,
            })
        placeholders = ','.join('?' * len(allowed_cameras))
        sql += ' AND camera_id IN (%s)' % placeholders
        params.extend(allowed_cameras)
    get_cursor().execute(sql, params)
    rows = get_cursor().fetchall()
    grid = {}
    for (nx, ny) in rows:
        if nx is None or ny is None:
            continue
        nx = max(0.0, min(1.0, float(nx)))
        ny = max(0.0, min(1.0, float(ny)))
        i = min(int(nx * grid_size), grid_size - 1)
        j = min(int(ny * grid_size), grid_size - 1)
        grid[(i, j)] = grid.get((i, j), 0) + 1
    cells = [{'i': i, 'j': j, 'count': c, 'person_seconds': c * interval_sec} for (i, j), c in grid.items()]
    return jsonify({
        'grid_rows': grid_size,
        'grid_cols': grid_size,
        'cells': cells,
        'date_from': date_from,
        'date_to': date_to,
        'camera_id': camera_id,
        'interval_seconds': interval_sec,
    })


@app.route('/api/v1/analytics/world_heatmap')
@require_role('viewer', 'operator', 'admin')
def api_v1_analytics_world_heatmap():
    """World/floor-plane heatmap: aggregate by binned (world_x, world_y) when homography is configured. Query: date_from, date_to, camera_id (optional), grid_size (default 16)."""
    date_from = request.args.get('date_from') or time.strftime('%Y-%m-%d', time.gmtime(time.time() - 7 * 86400))
    date_to = request.args.get('date_to') or time.strftime('%Y-%m-%d')
    camera_id = request.args.get('camera_id')
    try:
        grid_size = max(8, min(32, int(request.args.get('grid_size', '16'))))
    except (TypeError, ValueError):
        grid_size = 16
    allowed_sites = _get_user_allowed_site_ids()
    try:
        interval_sec = ANALYZE_INTERVAL_SECONDS
    except NameError:
        interval_sec = 10
    sql = """
        SELECT world_x, world_y FROM ai_data
        WHERE date >= ? AND date <= ? AND world_x IS NOT NULL AND world_y IS NOT NULL
    """
    params = [date_from, date_to]
    if camera_id:
        sql += ' AND camera_id = ?'
        params.append(camera_id)
    if allowed_sites is not None:
        get_cursor().execute('SELECT camera_id FROM camera_positions WHERE site_id IN (%s)' % ','.join('?' * len(allowed_sites)), allowed_sites)
        allowed_cameras = {r[0] for r in get_cursor().fetchall()}
        if not allowed_cameras:
            return jsonify({
                'grid_rows': grid_size, 'grid_cols': grid_size, 'cells': [], 'date_from': date_from, 'date_to': date_to,
                'camera_id': camera_id, 'interval_seconds': interval_sec,
            })
        placeholders = ','.join('?' * len(allowed_cameras))
        sql += ' AND camera_id IN (%s)' % placeholders
        params.extend(allowed_cameras)
    get_cursor().execute(sql, params)
    rows = get_cursor().fetchall()
    grid = {}
    for (wx, wy) in rows:
        if wx is None or wy is None:
            continue
        wx = max(0.0, min(1.0, float(wx)))
        wy = max(0.0, min(1.0, float(wy)))
        i = min(int(wx * grid_size), grid_size - 1)
        j = min(int(wy * grid_size), grid_size - 1)
        grid[(i, j)] = grid.get((i, j), 0) + 1
    cells = [{'i': i, 'j': j, 'count': c, 'person_seconds': c * interval_sec} for (i, j), c in grid.items()]
    return jsonify({
        'grid_rows': grid_size,
        'grid_cols': grid_size,
        'cells': cells,
        'date_from': date_from,
        'date_to': date_to,
        'camera_id': camera_id,
        'interval_seconds': interval_sec,
    })


@app.route('/api/v1/analytics/zone_dwell')
@require_role('viewer', 'operator', 'admin')
def api_v1_analytics_zone_dwell():
    """Zone dwell heatmap: person-seconds per zone per hour bucket from ai_data.zone_presence. Query: date_from, date_to, camera_id, zone_index (optional)."""
    date_from = request.args.get('date_from') or time.strftime('%Y-%m-%d', time.gmtime(time.time() - 7 * 86400))
    date_to = request.args.get('date_to') or time.strftime('%Y-%m-%d')
    camera_id = request.args.get('camera_id')
    zone_index_param = request.args.get('zone_index')
    try:
        interval_sec = ANALYZE_INTERVAL_SECONDS
    except NameError:
        interval_sec = 10
    allowed_sites = _get_user_allowed_site_ids()
    zone_indices = []
    if zone_index_param is not None:
        try:
            zone_indices = [int(zone_index_param)]
        except ValueError:
            pass
    if not zone_indices:
        num_zones = len(_analytics_config.get('loiter_zones', []))
        zone_indices = list(range(num_zones))
    buckets = []
    try:
        for zi in zone_indices:
            sql = """
                SELECT date, strftime('%H', time) AS hour, camera_id, COUNT(*) AS frame_count
                FROM ai_data
                WHERE date >= ? AND date <= ?
                AND (',' || COALESCE(zone_presence,'') || ',') LIKE ?
            """
            params = [date_from, date_to, '%,' + str(zi) + ',%']
            if camera_id:
                sql += ' AND camera_id = ?'
                params.append(camera_id)
            sql += ' GROUP BY date, hour, camera_id ORDER BY date, hour'
            get_cursor().execute(sql, params)
            for row in get_cursor().fetchall():
                buckets.append({
                    'date': row[0],
                    'hour_bucket': row[1],
                    'camera_id': row[2],
                    'zone_index': zi,
                    'frame_count': row[3],
                    'person_seconds': row[3] * interval_sec,
                })
    except sqlite3.OperationalError:
        pass
    if allowed_sites is not None:
        get_cursor().execute('SELECT camera_id FROM camera_positions WHERE site_id IN (%s)' % ','.join('?' * len(allowed_sites)), allowed_sites)
        allowed_cameras = {r[0] for r in get_cursor().fetchall()}
        buckets = [b for b in buckets if b.get('camera_id') in allowed_cameras]
    return jsonify({'zone_dwell': buckets, 'date_from': date_from, 'date_to': date_to, 'interval_seconds': interval_sec})


@app.route('/api/v1/analytics/vehicle_activity')
@require_role('viewer', 'operator', 'admin')
def api_v1_analytics_vehicle_activity():
    """LPR / vehicle activity: sightings by license_plate from ai_data. Query: date_from, date_to, camera_id, plate (optional filter). Returns list of sightings and per-plate summary."""
    date_from = request.args.get('date_from') or time.strftime('%Y-%m-%d', time.gmtime(time.time() - 7 * 86400))
    date_to = request.args.get('date_to') or time.strftime('%Y-%m-%d')
    camera_id = request.args.get('camera_id')
    plate_filter = (request.args.get('plate') or '').strip()
    allowed_sites = _get_user_allowed_site_ids()
    sql = """
        SELECT date, time, timestamp_utc, camera_id, license_plate
        FROM ai_data
        WHERE date >= ? AND date <= ?
        AND license_plate IS NOT NULL AND TRIM(license_plate) != '' AND license_plate NOT IN ('', 'None')
    """
    params = [date_from, date_to]
    if camera_id:
        sql += ' AND camera_id = ?'
        params.append(camera_id)
    if plate_filter:
        sql += ' AND license_plate LIKE ?'
        params.append('%' + plate_filter + '%')
    sql += ' ORDER BY date, time'
    try:
        get_cursor().execute(sql, params)
        rows = get_cursor().fetchall()
    except sqlite3.OperationalError:
        rows = []
    sightings = [{'date': r[0], 'time': r[1], 'timestamp_utc': r[2], 'camera_id': r[3], 'license_plate': r[4]} for r in rows]
    if allowed_sites is not None:
        get_cursor().execute('SELECT camera_id FROM camera_positions WHERE site_id IN (%s)' % ','.join('?' * len(allowed_sites)), allowed_sites)
        allowed_cameras = {r[0] for r in get_cursor().fetchall()}
        sightings = [s for s in sightings if s.get('camera_id') in allowed_cameras]
    # Per-plate summary: plate -> { count, cameras: set, first_seen, last_seen }
    by_plate = {}
    for s in sightings:
        plate = (s.get('license_plate') or '').strip()
        if not plate:
            continue
        if plate not in by_plate:
            by_plate[plate] = {'count': 0, 'camera_ids': [], 'first_seen': s.get('timestamp_utc') or (s.get('date') + 'T' + s.get('time', '')), 'last_seen': None}
        by_plate[plate]['count'] += 1
        if s.get('camera_id') and s['camera_id'] not in by_plate[plate]['camera_ids']:
            by_plate[plate]['camera_ids'].append(s['camera_id'])
        by_plate[plate]['last_seen'] = s.get('timestamp_utc') or (s.get('date') + 'T' + s.get('time', ''))
    return jsonify({'sightings': sightings, 'by_plate': by_plate, 'date_from': date_from, 'date_to': date_to})


@app.route('/api/v1/watchlist', methods=['GET'])
@require_role('viewer', 'operator', 'admin')
def api_v1_watchlist_list():
    """List watchlist entries (id, name, created_at). No embedding returned."""
    try:
        get_cursor().execute('SELECT id, name, created_at FROM watchlist_faces ORDER BY name')
        rows = get_cursor().fetchall()
    except sqlite3.OperationalError:
        return jsonify({'watchlist': []})
    return jsonify({'watchlist': [{'id': r[0], 'name': r[1], 'created_at': r[2]} for r in rows]})


@app.route('/api/v1/watchlist', methods=['POST'])
@require_role('admin')
def api_v1_watchlist_add():
    """Add a face to the watchlist. JSON: {"name": "Alice", "image_base64": "..."} or multipart file with "image" and "name". Requires DeepFace; edge-only."""
    name = None
    img_b64 = None
    if request.is_json:
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        img_b64 = data.get('image_base64')
    else:
        name = (request.form.get('name') or '').strip()
        f = request.files.get('image')
        if f:
            img_b64 = f.read()
            try:
                img_b64 = img_b64.decode('utf-8') if isinstance(img_b64, bytes) else img_b64
            except Exception:
                import base64
                img_b64 = base64.b64encode(img_b64).decode('ascii') if isinstance(img_b64, bytes) else None
    if not name:
        return jsonify({'error': 'name required'}), 400
    if not img_b64:
        return jsonify({'error': 'image_base64 or image file required'}), 400
    try:
        import base64
        raw = base64.b64decode(img_b64, validate=True)
        nparr = np.frombuffer(raw, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None or img.size == 0:
            return jsonify({'error': 'invalid image'}), 400
    except Exception as e:
        return jsonify({'error': 'invalid image or base64: %s' % str(e)}), 400
    emb = _get_face_embedding(img)
    if emb is None:
        return jsonify({'error': 'no face detected in image; add a clear face photo'}), 400
    blob = emb.tobytes()
    created_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    try:
        get_cursor().execute('INSERT INTO watchlist_faces (name, embedding, created_at) VALUES (?, ?, ?)', (name, blob, created_at))
        get_conn().commit()
        row_id = get_cursor().lastrowid
    except sqlite3.OperationalError as e:
        return jsonify({'error': 'database error: %s' % str(e)}), 500
    return jsonify({'id': row_id, 'name': name, 'created_at': created_at}), 201


@app.route('/api/v1/watchlist/<int:wid>', methods=['DELETE'])
@require_role('admin')
def api_v1_watchlist_delete(wid):
    """Remove a face from the watchlist."""
    try:
        get_cursor().execute('DELETE FROM watchlist_faces WHERE id = ?', (wid,))
        get_conn().commit()
        if get_cursor().rowcount == 0:
            return jsonify({'error': 'not found'}), 404
    except sqlite3.OperationalError as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'success': True})


@app.route('/api/v1/ai_data/verify')
@require_role('operator', 'admin')
def api_v1_ai_data_verify():
    """Verify integrity_hash for ai_data rows (chain of custody). Returns verified/mismatched/total for rows that have hash."""
    get_cursor().execute('SELECT * FROM ai_data WHERE integrity_hash IS NOT NULL AND integrity_hash != ""')
    rows = get_cursor().fetchall()
    col_names = [d[0] for d in get_cursor().description]
    verified, mismatched = 0, 0
    for row in rows:
        data = dict(zip(col_names, row))
        expected = _ai_data_integrity_hash(data)
        if data.get('integrity_hash') == expected:
            verified += 1
        else:
            mismatched += 1
    return jsonify({'verified': verified, 'mismatched': mismatched, 'total': len(rows)})


def _csv_cell(val):
    """Escape a single CSV cell (comma, newline, quote)."""
    s = '' if val is None else str(val)
    if ',' in s or '\n' in s or '"' in s:
        return '"' + s.replace('"', '""') + '"'
    return s


def _parse_surveillance_log_fallback(log_text):
    """Load and run surveillance log parser (script path); returns DataFrame or None on failure."""
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts', 'surveillance_log_parser.py')
        if os.path.isfile(path):
            import importlib.util
            spec = importlib.util.spec_from_file_location('surveillance_log_parser', path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.parse_surveillance_log(log_text)
    except Exception:
        pass
    try:
        from proactive.parser import parse_surveillance_log
        return parse_surveillance_log(log_text)
    except Exception:
        pass
    return None


@app.route('/api/v1/parse_log', methods=['POST'])
@require_role('viewer', 'operator', 'admin')
def api_v1_parse_log():
    """Parse raw surveillance log text (YOLOv8/Frigate-style tab/comma-separated). Accepts JSON body { \"log_text\": \"...\" } or form file 'file'. Returns parsed rows, columns, and summary."""
    log_text = None
    if request.is_json and request.json:
        log_text = request.json.get('log_text') or request.json.get('logText')
    if not log_text and request.files:
        f = request.files.get('file')
        if f:
            try:
                log_text = f.read().decode('utf-8', errors='replace')
            except Exception:
                return jsonify({'error': 'Failed to read file'}), 400
    if not log_text or not str(log_text).strip():
        return jsonify({'error': 'Provide log_text in JSON body or upload a file'}), 400
    df = _parse_surveillance_log_fallback(str(log_text))
    if df is None:
        return jsonify({'error': 'Parser not available or parse failed'}), 503
    try:
        import pandas as pd
        summary = {}
        if not df.empty and 'local_timestamp' in df.columns:
            ts = pd.to_datetime(df['local_timestamp'], errors='coerce').dropna()
            if len(ts) >= 2:
                summary['hours_covered'] = (ts.max() - ts.min()).total_seconds() / 3600
        summary['rows'] = len(df)
        summary['columns'] = list(df.columns)
        # Serialize for JSON (datetime -> iso, NaN -> null)
        rows = df.replace({np.nan: None}).to_dict('records')
        for r in rows:
            for k, v in list(r.items()):
                if hasattr(v, 'isoformat'):
                    r[k] = v.isoformat()
        return jsonify({'rows': rows, 'columns': list(df.columns), 'summary': summary})
    except Exception as e:
        return jsonify({'error': 'Serialization failed', 'detail': str(e)}), 500


@app.route('/api/v1/surveillance_analysis_report')
@require_role('viewer', 'operator', 'admin')
def api_v1_surveillance_analysis_report():
    """Serve the surveillance log analysis report (markdown) if present. Generated by scripts/surveillance_log_parser.py."""
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'surveillance_analysis_report.md')
    if not os.path.isfile(report_path):
        return jsonify({'error': 'Report not found', 'message': 'Run scripts/surveillance_log_parser.py to generate it'}), 404
    try:
        with open(report_path, encoding='utf-8') as f:
            body = f.read()
        from flask import Response
        return Response(body, mimetype='text/markdown; charset=utf-8', headers={'Content-Disposition': 'inline; filename=surveillance_analysis_report.md'})
    except Exception as e:
        return jsonify({'error': 'Failed to read report', 'detail': str(e)}), 500


@app.route('/export_data')
@require_role('operator', 'admin')
def export_data():
    if os.environ.get('EXPORT_REQUIRES_APPROVAL', '').strip().lower() in ('1', 'true', 'yes') and session.get('role') != 'admin':
        return jsonify({'error': 'Export requires admin approval', 'message': 'Only an administrator can export data when EXPORT_REQUIRES_APPROVAL is set.'}), 403
    operator = session.get('username') or 'unknown'
    _audit(operator, 'export_data', 'ai_data')
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    try:
        retention_days = int(os.environ.get('RETENTION_DAYS', '0'))
    except (TypeError, ValueError):
        retention_days = 0
    allowed_sites = _get_user_allowed_site_ids()
    if allowed_sites is not None:
        get_cursor().execute('SELECT camera_id FROM camera_positions WHERE site_id IN (%s)' % ','.join('?' * len(allowed_sites)), allowed_sites)
        allowed_cameras = [r[0] for r in get_cursor().fetchall()]
        if allowed_cameras:
            if date_from or date_to:
                q = 'SELECT * FROM ai_data WHERE camera_id IN (%s)' % ','.join('?' * len(allowed_cameras))
                params = list(allowed_cameras)
                if date_from:
                    q += ' AND date >= ?'
                    params.append(date_from)
                if date_to:
                    q += ' AND date <= ?'
                    params.append(date_to)
                get_cursor().execute(q, params)
            else:
                get_cursor().execute('SELECT * FROM ai_data WHERE camera_id IN (%s)' % ','.join('?' * len(allowed_cameras)), allowed_cameras)
        else:
            get_cursor().execute('SELECT * FROM ai_data WHERE 1=0')
        rows = get_cursor().fetchall()
    else:
        if date_from or date_to:
            q = 'SELECT * FROM ai_data WHERE 1=1'
            params = []
            if date_from:
                q += ' AND date >= ?'
                params.append(date_from)
            if date_to:
                q += ' AND date <= ?'
                params.append(date_to)
            get_cursor().execute(q, params)
        else:
            get_cursor().execute('SELECT * FROM ai_data')
        rows = get_cursor().fetchall()
    col_names = [d[0] for d in get_cursor().description]
    # Use canonical export column order so CSV matches standard schema header
    export_cols = [c for c in AI_DATA_EXPORT_COLUMNS if c in col_names]
    if not export_cols:
        export_cols = col_names
    export_utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    system_id = _system_id()
    meta = f'# Export UTC: {export_utc}\n# Operator: {operator}\n# System: {system_id}\n# Chain of custody: per-row integrity_hash column; file SHA-256 in footer and X-Export-SHA256 header. Verify: GET /api/v1/ai_data/verify\n'
    headers = ','.join(export_cols) + '\n'
    row_dicts = [dict(zip(col_names, row)) for row in rows]
    body = '\n'.join([','.join([_csv_cell(r.get(c)) for c in export_cols]) for r in row_dicts])
    csv_no_hash = meta + headers + body
    export_hash = hashlib.sha256(csv_no_hash.encode('utf-8')).hexdigest()
    csv = csv_no_hash + f'\n# SHA-256: {export_hash}\n'
    resp = Response(csv, mimetype='text/csv', headers={'Content-Disposition': f'attachment;filename=ai_data_{time.strftime("%Y%m%d")}.csv'})
    resp.headers['X-Export-SHA256'] = export_hash
    resp.headers['X-Export-UTC'] = export_utc
    resp.headers['X-Operator'] = operator
    resp.headers['X-System-ID'] = system_id
    resp.headers['X-Retention-Policy-Days'] = str(retention_days)
    if date_from or date_to:
        resp.headers['X-Export-Purpose'] = 'incident_bundle_range'
    return resp


def _ensure_default_user():
    get_cursor().execute('SELECT COUNT(*) FROM users')
    if get_cursor().fetchone()[0] > 0:
        return
    pw = os.environ.get('ADMIN_PASSWORD', 'admin')
    if BCRYPT_AVAILABLE:
        ok, msg = _validate_password(pw)
        if not ok and pw != 'admin':
            try:
                import logging
                logging.warning('Default admin password does not meet policy: %s', msg)
            except Exception:
                pass
        get_cursor().execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                       ('admin', bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(), 'admin'))
    else:
        # No bcrypt: create admin with sentinel hash; login uses password check vs ADMIN_PASSWORD.
        get_cursor().execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                       ('admin', 'no-bcrypt', 'admin'))
    if PASSWORD_EXPIRY_DAYS > 0:
        try:
            get_cursor().execute('UPDATE users SET password_expires_at = ? WHERE username = ?',
                           (time.time() + PASSWORD_EXPIRY_DAYS * 86400, 'admin'))
        except sqlite3.OperationalError:
            pass
    get_conn().commit()


def _sync_admin_password():
    """On startup, set the admin user's password to ADMIN_PASSWORD so login admin / ADMIN_PASSWORD works (e.g. admin/admin)."""
    pw = os.environ.get('ADMIN_PASSWORD', 'admin')
    get_cursor().execute('SELECT id, password_hash FROM users WHERE username = ?', ('admin',))
    row = get_cursor().fetchone()
    if not row:
        return
    if BCRYPT_AVAILABLE:
        new_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
        get_cursor().execute('UPDATE users SET password_hash = ? WHERE username = ?', (new_hash, 'admin'))
        get_conn().commit()
    # else: no-bcrypt admin continues to use env check at login


# Ensure default admin exists and password is ADMIN_PASSWORD (e.g. admin/admin) on startup
try:
    get_conn()
    _ensure_default_user()
    _sync_admin_password()
except Exception:
    pass


@app.route('/audit_log')
def get_audit_log():
    """List audit log. ?mine=1 or user_id=me: any authenticated user sees only their entries (My access history). Else admin sees all."""
    if not session.get('user_id'):
        return jsonify({'error': 'Login required'}), 401
    limit = min(int(request.args.get('limit', 100)), 500)
    mine = request.args.get('mine') == '1' or request.args.get('user_id', '').strip().lower() == 'me'
    uid = session.get('user_id')
    if mine and uid:
        get_cursor().execute('SELECT id, user_id, action, resource, timestamp, details FROM audit_log WHERE user_id = ? ORDER BY id DESC LIMIT ?', (uid, limit))
    else:
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin role required to view full audit log'}), 403
        get_cursor().execute('SELECT id, user_id, action, resource, timestamp, details FROM audit_log ORDER BY id DESC LIMIT ?', (limit,))
    rows = get_cursor().fetchall()
    return jsonify([dict(zip(['id', 'user_id', 'action', 'resource', 'timestamp', 'details'], row)) for row in rows])


@app.route('/audit_log/export')
@require_role('admin')
def export_audit_log():
    """Export audit log as CSV with SHA-256 integrity (AU-9 verifiable export)."""
    operator = session.get('username') or 'unknown'
    export_utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    try:
        system_id = os.environ.get('SYSTEM_ID') or platform.node() or 'surveillance'
    except Exception:
        system_id = 'surveillance'
    limit = min(int(request.args.get('limit', 10000)), 50000)
    try:
        get_cursor().execute('SELECT id, user_id, action, resource, timestamp, details, integrity_hash FROM audit_log ORDER BY id ASC LIMIT ?', (limit,))
        rows = get_cursor().fetchall()
        headers = 'id,user_id,action,resource,timestamp,details,integrity_hash\n'
    except sqlite3.OperationalError:
        get_cursor().execute('SELECT id, user_id, action, resource, timestamp, details FROM audit_log ORDER BY id ASC LIMIT ?', (limit,))
        rows = get_cursor().fetchall()
        headers = 'id,user_id,action,resource,timestamp,details\n'
    def _csv_cell(c):
        s = '' if c is None else str(c)
        if ',' in s or '\n' in s or '"' in s:
            return '"' + s.replace('"', '""') + '"'
        return s
    meta = f'# Audit log export UTC: {export_utc}\n# Operator: {operator}\n# System: {system_id}\n'
    body = '\n'.join([','.join([_csv_cell(c) for c in row]) for row in rows])
    csv_no_hash = meta + headers + body
    export_hash = hashlib.sha256(csv_no_hash.encode('utf-8')).hexdigest()
    csv = csv_no_hash + f'\n# SHA-256: {export_hash}\n'
    resp = Response(csv, mimetype='text/csv', headers={'Content-Disposition': f'attachment;filename=audit_log_{time.strftime("%Y%m%d")}.csv'})
    resp.headers['X-Export-SHA256'] = export_hash
    _audit(operator, 'export_audit_log', 'audit_log')
    return resp


@app.route('/audit_log/verify')
@require_role('admin')
def verify_audit_log():
    """Verify integrity_hash for audit log rows (AU-9). Returns counts of verified and mismatched."""
    try:
        get_cursor().execute('SELECT id, user_id, action, resource, timestamp, details, integrity_hash FROM audit_log')
    except sqlite3.OperationalError:
        return jsonify({'verified': 0, 'mismatched': 0, 'total': 0, 'message': 'integrity_hash column not present'})
    rows = get_cursor().fetchall()
    verified, mismatched = 0, 0
    for row in rows:
        row_id, u, a, r, ts, d, stored = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
        if not stored:
            continue
        payload = f'{row_id}|{u or "anonymous"}|{a}|{r or ""}|{ts or ""}|{d or ""}'
        expected = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        if expected == stored:
            verified += 1
        else:
            mismatched += 1
    return jsonify({'verified': verified, 'mismatched': mismatched, 'total': len(rows)})


@app.route('/config')
def get_config():
    """Return current analytics config (loiter zones, crossing lines). Read-only for viewers."""
    return jsonify(_analytics_config)


@app.route('/config', methods=['PATCH'])
@require_role('admin')
def update_config():
    """Update analytics config (AU-2 config-change audit). Includes privacy/civilian keys."""
    global _analytics_config
    data = request.get_json() or {}
    allowed = {'loiter_zones', 'loiter_seconds', 'crossing_lines', 'privacy_preset', 'home_away_mode', 'recording_signage_reminder', 'privacy_policy_url'}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({'success': False, 'error': 'No allowed keys'}), 400
    if 'loiter_seconds' in updates:
        try:
            updates['loiter_seconds'] = int(updates['loiter_seconds'])
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'loiter_seconds must be integer'}), 400
    if 'privacy_preset' in updates and updates['privacy_preset'] not in ('minimal', 'full'):
        updates['privacy_preset'] = _analytics_config.get('privacy_preset', 'full')
    if 'home_away_mode' in updates and updates['home_away_mode'] not in ('home', 'away'):
        updates['home_away_mode'] = _analytics_config.get('home_away_mode', 'away')
    for k in ('recording_signage_reminder', 'privacy_policy_url'):
        if k in updates and updates[k] is not None and not isinstance(updates[k], str):
            updates[k] = str(updates[k])
    try:
        current = {}
        if os.path.isfile(_config_path):
            with open(_config_path) as f:
                current = json.load(f)
        current.update(updates)
        with open(_config_path, 'w') as f:
            json.dump(current, f, indent=2)
        _analytics_config.update(current)
        _audit(session.get('username'), 'config_change', 'config', json.dumps(list(updates.keys())))
        return jsonify({'success': True, 'config': _analytics_config})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not username:
        return jsonify({'success': False})
    _ensure_default_user()
    # Always sync admin password from ADMIN_PASSWORD so login works after env change or if startup sync was skipped
    if username == 'admin':
        _sync_admin_password()
    if _is_locked(username):
        get_cursor().execute('SELECT locked_until FROM login_attempts WHERE username = ?', (username,))
        row = get_cursor().fetchone()
        until = row[0] if row and row[0] else None
        return jsonify({
            'success': False,
            'locked': True,
            'locked_until_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(until)) if until else None,
        }), 423
    try:
        get_cursor().execute('SELECT id, password_hash, role, password_expires_at, expires_at FROM users WHERE username = ?', (username,))
    except sqlite3.OperationalError:
        try:
            get_cursor().execute('SELECT id, password_hash, role, password_expires_at FROM users WHERE username = ?', (username,))
            row = get_cursor().fetchone()
            if row:
                row = row + (None,)  # expires_at
        except sqlite3.OperationalError:
            get_cursor().execute('SELECT id, password_hash, role FROM users WHERE username = ?', (username,))
            row = get_cursor().fetchone()
            if row:
                row = row + (None, None)
            else:
                row = None
    else:
        row = get_cursor().fetchone()
    if not row:
        _record_failed_login(username)
        ctx = _client_context()
        _audit(username, 'login_failed', 'auth', ctx and f'unknown user {ctx}' or 'unknown user')
        _log_structured('login', username=username, outcome='failure', reason='unknown_user')
        return jsonify({'success': False})
    uid, pw_hash, role = row[0], row[1], row[2]
    password_expires_at = row[3] if len(row) > 3 else None
    # Sentinel for default user created without bcrypt; check against env password.
    if pw_hash == 'no-bcrypt':
        if password != (os.environ.get('ADMIN_PASSWORD') or 'admin'):
            _record_failed_login(username)
            ctx = _client_context()
            _audit(username, 'login_failed', 'auth', ctx and f'bad password {ctx}' or 'bad password')
            _log_structured('login', username=username, outcome='failure', reason='bad_password')
            return jsonify({'success': False})
    elif BCRYPT_AVAILABLE:
        try:
            if not bcrypt.checkpw(password.encode('utf-8'), pw_hash.encode('utf-8')):
                _record_failed_login(username)
                ctx = _client_context()
                _audit(username, 'login_failed', 'auth', ctx and f'bad password {ctx}' or 'bad password')
                _log_structured('login', username=username, outcome='failure', reason='bad_password')
                return jsonify({'success': False})
        except (ValueError, TypeError):
            _record_failed_login(username)
            _log_structured('login', username=username, outcome='failure', reason='bad_password')
            return jsonify({'success': False})
    else:
        if password != (os.environ.get('ADMIN_PASSWORD') or 'admin'):
            _record_failed_login(username)
            ctx = _client_context()
            _audit(username, 'login_failed', 'auth', ctx and f'bad password {ctx}' or 'bad password')
            _log_structured('login', username=username, outcome='failure', reason='bad_password')
            return jsonify({'success': False})
    if password_expires_at is not None and time.time() > password_expires_at:
        _audit(username, 'login_failed', 'auth', 'password expired')
        _log_structured('login', username=username, outcome='failure', reason='password_expired')
        return jsonify({'success': False, 'password_expired': True}), 403
    expires_at = row[4] if len(row) > 4 else None
    if expires_at is not None and time.time() > expires_at:
        _audit(username, 'login_failed', 'auth', 'account expired (guest/temporary access)')
        _log_structured('login', username=username, outcome='failure', reason='account_expired')
        return jsonify({'success': False, 'account_expired': True}), 403
    _clear_login_attempts(username)
    if ENABLE_MFA and PYOTP_AVAILABLE and _user_has_mfa_enabled(uid):
        _clean_expired_mfa_tokens()
        mfa_token = os.urandom(32).hex()
        expires = time.time() + MFA_TOKEN_TTL_SECONDS
        try:
            get_cursor().execute('INSERT INTO mfa_tokens (token, user_id, expires) VALUES (?, ?, ?)', (mfa_token, uid, expires))
            get_conn().commit()
        except Exception:
            return jsonify({'success': False}), 500
        return jsonify({'success': True, 'require_mfa': True, 'mfa_token': mfa_token})
    session['user_id'] = str(uid)
    session['username'] = username
    session['role'] = role
    session['last_activity'] = time.time()
    _audit(username, 'login', 'auth')
    _log_structured('login', username=username, outcome='success')
    payload = {'success': True, 'role': role}
    if password_expires_at is not None and password_expires_at > time.time():
        payload['password_expires_in_days'] = max(0, int((password_expires_at - time.time()) / 86400))
    return jsonify(payload)


@app.route('/login/verify_totp', methods=['POST'])
def verify_totp():
    """Complete login after password when MFA is enabled (NIST IR 8523 / CJIS)."""
    if not ENABLE_MFA or not PYOTP_AVAILABLE:
        return jsonify({'success': False, 'error': 'MFA not enabled'}), 400
    data = request.get_json() or {}
    mfa_token = (data.get('mfa_token') or '').strip()
    code = (data.get('code') or '').strip().replace(' ', '')
    if not mfa_token or not code or len(code) != 6:
        return jsonify({'success': False})
    _clean_expired_mfa_tokens()
    get_cursor().execute('SELECT user_id FROM mfa_tokens WHERE token = ? AND expires > ?', (mfa_token, time.time()))
    row = get_cursor().fetchone()
    if not row:
        return jsonify({'success': False, 'error': 'expired_or_invalid'})
    uid = row[0]
    get_cursor().execute('DELETE FROM mfa_tokens WHERE token = ?', (mfa_token,))
    get_conn().commit()
    get_cursor().execute('SELECT secret FROM user_mfa WHERE user_id = ? AND enabled = 1', (uid,))
    row = get_cursor().fetchone()
    if not row:
        return jsonify({'success': False})
    secret = row[0]
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        return jsonify({'success': False})
    try:
        get_cursor().execute('SELECT username, role, password_expires_at FROM users WHERE id = ?', (uid,))
    except sqlite3.OperationalError:
        get_cursor().execute('SELECT username, role FROM users WHERE id = ?', (uid,))
        row = get_cursor().fetchone()
        if row:
            row = row + (None,)
        else:
            row = None
    else:
        row = get_cursor().fetchone()
    if not row:
        return jsonify({'success': False})
    username, role = row[0], row[1]
    password_expires_at = row[2] if len(row) > 2 else None
    session['user_id'] = str(uid)
    session['username'] = username
    session['role'] = role
    session['last_activity'] = time.time()
    _audit(username, 'login', 'auth', 'mfa_verified')
    payload = {'success': True, 'role': role}
    if password_expires_at is not None and password_expires_at > time.time():
        payload['password_expires_in_days'] = max(0, int((password_expires_at - time.time()) / 86400))
    return jsonify(payload)


@app.route('/me')
def me():
    """Return current session (username, role, password_expires_in_days). Used by frontend for Settings."""
    if not session.get('user_id'):
        return jsonify({'authenticated': False}), 401
    uid = int(session['user_id'])
    try:
        get_cursor().execute('SELECT username, role, password_expires_at FROM users WHERE id = ?', (uid,))
    except sqlite3.OperationalError:
        get_cursor().execute('SELECT username, role FROM users WHERE id = ?', (uid,))
        row = get_cursor().fetchone()
        if row:
            row = row + (None,)
        else:
            row = None
    else:
        row = get_cursor().fetchone()
    if not row:
        return jsonify({'authenticated': False}), 401
    username, role = row[0], row[1]
    password_expires_at = row[2] if len(row) > 2 else None
    payload = {'authenticated': True, 'username': username, 'role': role}
    if password_expires_at is not None and password_expires_at > time.time():
        payload['password_expires_in_days'] = max(0, int((password_expires_at - time.time()) / 86400))
    allowed = _get_user_allowed_site_ids()
    if allowed is not None:
        payload['allowed_site_ids'] = allowed
    return jsonify(payload)


@app.route('/mfa/status')
def mfa_status():
    """Return whether current user has MFA enabled (for Settings)."""
    if not session.get('user_id'):
        return jsonify({'enabled': False}), 401
    uid = int(session['user_id'])
    get_cursor().execute('SELECT 1 FROM user_mfa WHERE user_id = ? AND enabled = 1', (uid,))
    return jsonify({'enabled': get_cursor().fetchone() is not None, 'available': ENABLE_MFA and PYOTP_AVAILABLE})


@app.route('/mfa/setup', methods=['POST'])
@require_role('operator', 'admin')
def mfa_setup():
    """Generate TOTP secret for current user; user must then confirm with code (POST /mfa/confirm)."""
    if not ENABLE_MFA or not PYOTP_AVAILABLE:
        return jsonify({'error': 'MFA not available'}), 400
    uid = int(session['user_id'])
    username = session.get('username', '')
    secret = pyotp.random_base32()
    get_cursor().execute('INSERT OR REPLACE INTO user_mfa (user_id, secret, enabled) VALUES (?, ?, 0)', (uid, secret))
    get_conn().commit()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=username, issuer_name=os.environ.get('MFA_ISSUER_NAME', 'VMS'))
    _audit(session.get('username'), 'mfa_setup', 'auth', 'secret_generated')
    return jsonify({'secret': secret, 'provisioning_uri': provisioning_uri})


@app.route('/mfa/confirm', methods=['POST'])
@require_role('operator', 'admin')
def mfa_confirm():
    """Verify TOTP code and enable MFA for current user."""
    if not ENABLE_MFA or not PYOTP_AVAILABLE:
        return jsonify({'success': False, 'error': 'MFA not available'}), 400
    code = (request.get_json(silent=True) or {}).get('code', '').strip().replace(' ', '')
    if len(code) != 6:
        return jsonify({'success': False})
    uid = int(session['user_id'])
    get_cursor().execute('SELECT secret FROM user_mfa WHERE user_id = ?', (uid,))
    row = get_cursor().fetchone()
    if not row:
        return jsonify({'success': False})
    if not pyotp.TOTP(row[0]).verify(code, valid_window=1):
        return jsonify({'success': False})
    get_cursor().execute('UPDATE user_mfa SET enabled = 1 WHERE user_id = ?', (uid,))
    get_conn().commit()
    _audit(session.get('username'), 'mfa_enabled', 'auth')
    return jsonify({'success': True})


@app.route('/change_password', methods=['POST'])
@require_role('viewer', 'operator', 'admin')
def change_password():
    """Change current user password. Enforces password history and expiry (NIST/CJIS)."""
    if not BCRYPT_AVAILABLE:
        return jsonify({'success': False, 'error': 'Password change not available'}), 400
    data = request.get_json() or {}
    current = (data.get('current_password') or data.get('current') or '').strip()
    new_pw = (data.get('new_password') or data.get('new') or '').strip()
    if not current or not new_pw:
        return jsonify({'success': False, 'error': 'current_password and new_password required'}), 400
    ok, msg = _validate_password(new_pw)
    if not ok:
        return jsonify({'success': False, 'error': msg}), 400
    uid = int(session['user_id'])
    get_cursor().execute('SELECT password_hash FROM users WHERE id = ?', (uid,))
    row = get_cursor().fetchone()
    if not row or not bcrypt.checkpw(current.encode(), row[0].encode()):
        _audit(session.get('username'), 'password_change_failed', 'auth', 'bad current password')
        return jsonify({'success': False, 'error': 'Current password is incorrect'}), 400
    if PASSWORD_HISTORY_COUNT > 0:
        get_cursor().execute(
            'SELECT password_hash FROM password_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
            (uid, PASSWORD_HISTORY_COUNT)
        )
        for (h,) in get_cursor().fetchall():
            if bcrypt.checkpw(new_pw.encode(), h.encode()):
                return jsonify({'success': False, 'error': f'Cannot reuse one of the last {PASSWORD_HISTORY_COUNT} passwords'}), 400
    new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
    try:
        get_cursor().execute('UPDATE users SET password_hash = ?, password_expires_at = ? WHERE id = ?', (
            new_hash,
            (time.time() + PASSWORD_EXPIRY_DAYS * 86400) if PASSWORD_EXPIRY_DAYS > 0 else None,
            uid
        ))
        get_cursor().execute('INSERT INTO password_history (user_id, password_hash, created_at) VALUES (?, ?, ?)',
                       (uid, row[0], time.time()))
        if PASSWORD_HISTORY_COUNT > 0:
            get_cursor().execute(
                'DELETE FROM password_history WHERE user_id = ? AND id IN (SELECT id FROM password_history WHERE user_id = ? ORDER BY created_at DESC LIMIT -1 OFFSET ?)',
                (uid, uid, PASSWORD_HISTORY_COUNT)
            )
        get_conn().commit()
    except sqlite3.OperationalError as e:
        if 'password_expires_at' in str(e):
            get_cursor().execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, uid))
            get_cursor().execute('INSERT INTO password_history (user_id, password_hash, created_at) VALUES (?, ?, ?)',
                           (uid, row[0], time.time()))
            get_conn().commit()
        else:
            return jsonify({'success': False, 'error': str(e)}), 500
    _audit(session.get('username'), 'password_change', 'auth')
    return jsonify({'success': True})


@app.route('/logout', methods=['POST'])
def logout():
    _audit(session.get('username'), 'logout', 'auth')
    session.clear()
    return jsonify({'success': True})


if sock is not None:
    @sock.route('/ws')
    def ws_route(ws):
        _ws_clients.append(ws)
        try:
            while True:
                ws.receive()
        except Exception:
            pass
        finally:
            if ws in _ws_clients:
                _ws_clients.remove(ws)


def retention_job():
    """Delete old ai_data, events, and recording files. Legal hold excludes held resources. Audit log has separate AUDIT_RETENTION_DAYS (AU-9)."""
    retention_days = int(os.environ.get('RETENTION_DAYS', '0'))
    audit_retention_days = int(os.environ.get('AUDIT_RETENTION_DAYS', '0'))
    while True:
        time.sleep(6 * 3600)
        try:
            _log_structured('retention_run', retention_days=retention_days, audit_retention_days=audit_retention_days)
            if retention_days > 0:
                cutoff = time.strftime('%Y-%m-%d', time.gmtime(time.time() - retention_days * 86400))
                get_cursor().execute('DELETE FROM ai_data WHERE date < ?', (cutoff,))
                get_cursor().execute(
                    "DELETE FROM events WHERE date(timestamp) < ? AND CAST(id AS TEXT) NOT IN (SELECT resource_id FROM legal_hold WHERE resource_type = 'event')",
                    (cutoff,)
                )
                get_conn().commit()
                rec_dir = _recordings_dir()
                try:
                    get_cursor().execute("SELECT resource_id FROM legal_hold WHERE resource_type = 'recording'")
                    held_recordings = {row[0] for row in get_cursor().fetchall()}
                except Exception:
                    held_recordings = set()
                try:
                    for f in os.listdir(rec_dir):
                        if f.startswith('recording_') and f.endswith('.avi') and f not in held_recordings:
                            try:
                                fp = os.path.join(rec_dir, f)
                                if os.path.getmtime(fp) < time.time() - retention_days * 86400:
                                    os.remove(fp)
                                    get_cursor().execute('DELETE FROM recording_fixity WHERE path = ?', (f,))
                            except Exception:
                                pass
                    get_conn().commit()
                except Exception:
                    pass
            if audit_retention_days > 0:
                cutoff_audit = time.strftime('%Y-%m-%d', time.gmtime(time.time() - audit_retention_days * 86400))
                get_cursor().execute('DELETE FROM audit_log WHERE date(timestamp) < ?', (cutoff_audit,))
                get_conn().commit()
        except Exception:
            pass


def fixity_job():
    """OSAC/SWGDE fixity: compute SHA-256 for each recording, compare to stored value; alert on mismatch. Run when ENABLE_RECORDING_FIXITY=1."""
    while True:
        time.sleep(6 * 3600)
        if os.environ.get('ENABLE_RECORDING_FIXITY', '').strip().lower() not in ('1', 'true', 'yes'):
            continue
        try:
            rec_dir = _recordings_dir()
            checked_at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            for f in os.listdir(rec_dir):
                if not (f.startswith('recording_') and f.endswith('.avi')):
                    continue
                path = os.path.join(rec_dir, f)
                if not os.path.isfile(path):
                    continue
                current = _compute_recording_sha256(path)
                if not current:
                    continue
                cur = get_cursor()
                cur.execute('SELECT sha256 FROM recording_fixity WHERE path = ?', (f,))
                row = cur.fetchone()
                if row:
                    stored = row[0]
                    if stored != current:
                        _log_structured('fixity_mismatch', path=f, stored_sha256=stored[:16] + '...', current_sha256=current[:16] + '...')
                cur.execute('INSERT OR REPLACE INTO recording_fixity (path, sha256, checked_at) VALUES (?, ?, ?)', (f, current, checked_at))
            get_conn().commit()
        except Exception:
            pass


if __name__ == '__main__':
    if os.environ.get('FLASK_SECRET_KEY') in (None, '', 'dev-secret-change-in-production'):
        import sys
        print('WARNING: Using default FLASK_SECRET_KEY. Set FLASK_SECRET_KEY in production.', file=sys.stderr)
    threading.Thread(target=analyze_frame, daemon=True).start()
    if os.environ.get('RETENTION_DAYS') or os.environ.get('AUDIT_RETENTION_DAYS'):
        threading.Thread(target=retention_job, daemon=True).start()
    if os.environ.get('ENABLE_RECORDING_FIXITY', '').strip().lower() in ('1', 'true', 'yes'):
        threading.Thread(target=fixity_job, daemon=True).start()
    if _redis_sub is not None:
        threading.Thread(target=_redis_subscriber, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    print(f'Vigil starting on http://0.0.0.0:{port} (cameras: {"auto" if _raw_camera_sources.lower() in ("", "auto") else "env"}, audio: {"enabled (ENABLE_AUDIO=1)" if AUDIO_AVAILABLE else "disabled (ENABLE_AUDIO=0)"})')
    app.run(host='0.0.0.0', port=port)
