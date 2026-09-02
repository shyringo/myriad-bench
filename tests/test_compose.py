import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.compose import compose_session, compose_isolated, generate_mixture  # noqa: E402
from harness.tasks import generate_unit  # noqa: E402
from harness.validate import validate_session  # noqa: E402

import random  # noqa: E402


class TestCompose(unittest.TestCase):
    def test_deterministic_generation(self):
        a = compose_session({"mixture_id": "m", "session_id": "m-1", "name": "x", "tier": "S",
                             "seed": 7, "mixture": {"K": 5, "H": 0.6, "D": 0.5, "DEP": 0.5, "IR": 0.4, "NV": 0.3}},
                            random.Random(7))
        b = compose_session({"mixture_id": "m", "session_id": "m-1", "name": "x", "tier": "S",
                             "seed": 7, "mixture": {"K": 5, "H": 0.6, "D": 0.5, "DEP": 0.5, "IR": 0.4, "NV": 0.3}},
                            random.Random(7))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_generated_session_valid(self):
        s = compose_session({"mixture_id": "m", "session_id": "m-2", "name": "x", "tier": "S",
                             "seed": 3, "mixture": {"K": 8, "H": 0.8, "D": 0.6, "DEP": 0.6, "IR": 0.5, "NV": 0.5}},
                            random.Random(3))
        self.assertFalse(validate_session(s), validate_session(s))
        self.assertEqual(len(s["units"]), 8)

    def test_declared_tools_have_envs(self):
        """Every tool a unit declares must resolve to an env container."""
        s = compose_session({"mixture_id": "m", "session_id": "m-5", "name": "x", "tier": "S",
                             "seed": 11, "mixture": {"K": 8, "H": 0.8, "D": 0.6, "DEP": 0.6, "IR": 0.5, "NV": 0.5}},
                            random.Random(11))
        for u in s["units"]:
            for tool in u.get("tools", []):
                if tool == "none":
                    continue
                self.assertIn(tool, s["world"], (u["id"], tool, list(s["world"])))

    def test_dependencies_reference_produced_artifacts(self):
        s = compose_session({"mixture_id": "m", "session_id": "m-3", "name": "x", "tier": "S",
                             "seed": 11, "mixture": {"K": 8, "H": 0.6, "D": 0.4, "DEP": 1.0, "IR": 0.3, "NV": 0.0}},
                            random.Random(11))
        units = {u["id"]: u for u in s["units"]}
        for u in s["units"]:
            for dep in u.get("depends_on", []):
                self.assertIn(dep["unit"], units)
                self.assertIn(dep["artifact"], units[dep["unit"]].get("produce_artifacts", []))

    def test_isolated_sessions_are_single_task(self):
        s = compose_session({"mixture_id": "m", "session_id": "m-4", "name": "x", "tier": "S",
                             "seed": 5, "mixture": {"K": 4, "H": 0.5, "D": 0.5, "DEP": 0.5, "IR": 0.5, "NV": 0.0}},
                            random.Random(5))
        for u in s["units"]:
            iso = compose_isolated(u, s, random.Random(5))
            self.assertEqual(iso["kind"], "isolated")
            self.assertEqual(iso["isolated_unit"], u["id"])
            self.assertEqual(len(iso["units"]), 1)
            self.assertFalse(validate_session(iso), validate_session(iso))

    def test_generate_mixture_writes_files(self):
        with tempfile.TemporaryDirectory() as td:
            path, isolated = generate_mixture(td, "cli-mix", seed=9, tier="S", K=3, NV=0.0)
            self.assertTrue(os.path.exists(path))
            self.assertEqual(len(isolated), 3)
            for p in isolated:
                self.assertTrue(os.path.exists(p))


if __name__ == "__main__":
    unittest.main()