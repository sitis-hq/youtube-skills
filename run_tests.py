#!/usr/bin/env python3
"""Run every skill's tests. Skill directories have hyphens, so they are not packages and plain
`unittest discover` cannot walk into them; each tests/ directory is discovered on its own."""

import sys
import unittest
from pathlib import Path

root = Path(__file__).resolve().parent
suite = unittest.TestSuite()
for tests in sorted(root.glob("skills/*/tests")) + sorted(root.glob("lib/*/tests")):
    suite.addTests(unittest.defaultTestLoader.discover(str(tests), pattern="test_*.py", top_level_dir=str(tests)))
result = unittest.TextTestRunner(verbosity=2 if "-v" in sys.argv else 1).run(suite)
if result.testsRun == 0:
    print("no tests found", file=sys.stderr)
    sys.exit(1)
sys.exit(0 if result.wasSuccessful() else 1)
