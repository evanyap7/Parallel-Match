import unittest

from parallel_match import realism


class RealismTest(unittest.TestCase):
    """Per-match averages over a fixed set of seeds stay inside the target
    ranges. Slow-ish (about 20s)."""

    def test_report_inside_target_ranges(self):
        rep = realism.run(n_matches=120, base_seed=5000)
        failed = [f"{m['name']}={m['value']} not in [{m['lo']}, {m['hi']}]"
                  for m in rep["metrics"] if not m["ok"]]
        self.assertEqual(failed, [])


if __name__ == "__main__":
    unittest.main()
