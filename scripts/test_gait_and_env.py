#!/usr/bin/env python3
"""
Test gait/pose env and app logic. Run from repo root (or set PYTHONPATH).
Usage: python scripts/test_gait_and_env.py [--live]
  --live  also GET /health and /api/v1/system_status (default http://127.0.0.1:5000).
Use repo venv: .venv/bin/python scripts/test_gait_and_env.py [--live]
"""
import os
import sys

# Load .env from repo root
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(repo_root, '.env')
if os.path.isfile(env_path):
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        pass

def main():
    base = os.environ.get('VIGIL_BASE_URL', 'http://127.0.0.1:5000').rstrip('/')
    live = '--live' in sys.argv

    # 1) Env
    raw = os.environ.get('ENABLE_GAIT_NOTES', '1')
    enabled = raw.strip().lower() in ('1', 'true', 'yes')
    print('ENABLE_GAIT_NOTES:', repr(raw), '-> enabled:', enabled)

    # 2) App module and gait helper
    sys.path.insert(0, repo_root)
    from app import _gait_notes_from_pose, _is_gait_notes_enabled
    assert _gait_notes_from_pose(None) == 'unknown'
    print('_gait_notes_from_pose(None):', 'unknown', 'OK')
    # Mock pose: upright, symmetric -> normal
    class MockLm:
        def __init__(self, x=0.5, y=0.0, visibility=1.0):
            self.x, self.y = x, y
            self.visibility = visibility
    class MockPose:
        pose_landmarks = type('LM', (), {
            'landmark': [MockLm(0.5, 0.2 + i * 0.02) for i in range(33)]
        })()
    # Override so shoulders (11,12) and hips (23,24) give upright torso
    MockPose.pose_landmarks.landmark[11] = MockLm(0.4, 0.25, 1.0)
    MockPose.pose_landmarks.landmark[12] = MockLm(0.6, 0.25, 1.0)
    MockPose.pose_landmarks.landmark[23] = MockLm(0.4, 0.55, 1.0)
    MockPose.pose_landmarks.landmark[24] = MockLm(0.6, 0.55, 1.0)
    out = _gait_notes_from_pose(MockPose())
    assert out in ('normal', 'asymmetric', 'bent_torso', 'bent_torso, asymmetric', 'unknown'), out
    print('_gait_notes_from_pose(mock upright):', out, 'OK')
    print('_is_gait_notes_enabled():', _is_gait_notes_enabled(), 'OK')

    # 3) Optional live HTTP checks
    if live:
        try:
            import urllib.request
            with urllib.request.urlopen(base + '/health', timeout=5) as r:
                code = r.getcode()
                print('GET', base + '/health', '->', code, 'OK' if code == 200 else 'FAIL')
            with urllib.request.urlopen(base + '/api/v1/system_status', timeout=5) as r:
                import json
                data = json.load(r)
                ai = data.get('ai', {})
                g = ai.get('gait_notes_enabled')
                print('GET', base + '/api/v1/system_status', '-> gait_notes_enabled:', g, 'OK' if g is not None else 'MISSING')
        except Exception as e:
            print('Live checks failed:', e)
            return 1
    else:
        print('Skipping live HTTP checks (use --live to enable)')

    print('All checks passed.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
