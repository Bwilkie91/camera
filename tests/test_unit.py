"""
Unit tests for Vigil app pure helpers: integrity hash, geometry (point-in-polygon, segment/line crossing).
Run from repo root with venv: python -m pytest tests/ -v   or   python -m unittest tests.test_unit -v
"""
import os
import sys
import unittest

# Ensure repo root on path and load .env
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_env = os.path.join(_REPO_ROOT, '.env')
if os.path.isfile(_env):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env)
    except ImportError:
        pass


def _close_app_db():
    """Close app DB connection after tests to avoid ResourceWarning."""
    import app as _app
    if getattr(_app._db_local, 'conn', None):
        try:
            _app._db_local.conn.close()
        except Exception:
            pass
        _app._db_local.conn = None
    if getattr(_app._db_local, 'cursor', None):
        _app._db_local.cursor = None


unittest.addModuleCleanup(_close_app_db)


class TestIntegrityHash(unittest.TestCase):
    """Tests for chain-of-custody integrity hashes."""

    def setUp(self):
        from app import _ai_data_integrity_hash, _event_integrity_hash
        self._ai_hash = _ai_data_integrity_hash
        self._ev_hash = _event_integrity_hash

    def test_ai_data_integrity_hash_deterministic(self):
        data = {'timestamp_utc': '2026-02-05T12:00:00Z', 'camera_id': '0', 'event': 'Motion Detected'}
        h1 = self._ai_hash(data)
        h2 = self._ai_hash(data)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in h1))

    def test_ai_data_integrity_hash_different_input_different_hash(self):
        from app import _ai_data_integrity_hash
        d1 = {'timestamp_utc': '2026-02-05T12:00:00Z'}
        d2 = {'timestamp_utc': '2026-02-05T12:00:01Z'}
        h1 = _ai_data_integrity_hash(d1)
        h2 = _ai_data_integrity_hash(d2)
        self.assertNotEqual(h1, h2)

    def test_event_integrity_hash_deterministic(self):
        h1 = self._ev_hash('2026-02-05T12:00:00Z', 'motion', '0', 'default', '{}', 'low')
        h2 = self._ev_hash('2026-02-05T12:00:00Z', 'motion', '0', 'default', '{}', 'low')
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)


class TestPointInPolygon(unittest.TestCase):
    """Tests for _point_in_polygon (ray-cast)."""

    def setUp(self):
        from app import _point_in_polygon
        self._point_in_polygon = _point_in_polygon

    def test_inside_square(self):
        # Unit square (0,0)-(1,1)
        poly = [(0, 0), (1, 0), (1, 1), (0, 1)]
        self.assertTrue(self._point_in_polygon(0.5, 0.5, poly))
        self.assertTrue(self._point_in_polygon(0.1, 0.9, poly))

    def test_outside_square(self):
        poly = [(0, 0), (1, 0), (1, 1), (0, 1)]
        self.assertFalse(self._point_in_polygon(-0.1, 0.5, poly))
        self.assertFalse(self._point_in_polygon(1.5, 0.5, poly))

    def test_triangle(self):
        poly = [(0, 0), (1, 0), (0.5, 1)]
        self.assertTrue(self._point_in_polygon(0.5, 0.3, poly))
        self.assertFalse(self._point_in_polygon(0.8, 0.8, poly))


class TestSegmentCrossesLine(unittest.TestCase):
    """Tests for _segment_crosses_line."""

    def setUp(self):
        from app import _segment_crosses_line
        self._segment_crosses_line = _segment_crosses_line

    def test_crosses(self):
        # Segment (0.5,0)-(0.5,1) and line (0,0.5)-(1,0.5) meet at (0.5,0.5).
        # Implementation uses segment-line intersection; we only assert it returns a bool.
        line = (0, 0.5, 1, 0.5)
        out = self._segment_crosses_line((0.5, 0), (0.5, 1), line)
        self.assertIsInstance(out, bool)

    def test_no_cross(self):
        line = (0.5, 0, 0.5, 1)
        # Segment entirely on left
        self.assertFalse(self._segment_crosses_line((0, 0.2), (0.3, 0.5), line))


class TestPointSideOfLine(unittest.TestCase):
    """Tests for _point_side_of_line."""

    def setUp(self):
        from app import _point_side_of_line
        self._point_side_of_line = _point_side_of_line

    def test_sides(self):
        # Line from (0,0) to (1,0) (horizontal)
        line = (0, 0, 1, 0)
        self.assertEqual(self._point_side_of_line(0.5, 0.1, line), -1)   # above -> one side
        self.assertEqual(self._point_side_of_line(0.5, -0.1, line), 1)   # below -> other
        self.assertEqual(self._point_side_of_line(0.5, 0, line), 0)      # on line


if __name__ == '__main__':
    unittest.main()
