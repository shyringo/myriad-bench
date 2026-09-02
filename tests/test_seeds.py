import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.validate import load_and_validate, validate_dir  # noqa: E402

SEEDS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "seeds")


class TestSeedsValid(unittest.TestCase):
    def test_all_seed_sessions_valid(self):
        errs = validate_dir(SEEDS)
        bad = {fn: e for fn, e in errs.items() if e}
        self.assertEqual(bad, {}, f"invalid seeds: {bad}")

    def test_seed_dependencies_are_consistent(self):
        for fn in os.listdir(SEEDS):
            if not fn.endswith(".json"):
                continue
            session, errs = load_and_validate(os.path.join(SEEDS, fn))
            self.assertFalse(errs, fn)
            units = {u["id"]: u for u in session["units"]}
            for u in session["units"]:
                arts = set(u.get("produce_artifacts", []))
                for dep in u.get("depends_on", []):
                    prod = units[dep["unit"]]
                    self.assertIn(dep["artifact"], set(prod.get("produce_artifacts", [])),
                                  f"{fn}: {dep['artifact']} not produced by {dep['unit']}")
                    self.assertIn("fs", u.get("tools", []),
                                  f"{fn}: consumer {u['id']} cannot read (obligation {dep['artifact']})")


if __name__ == "__main__":
    unittest.main()