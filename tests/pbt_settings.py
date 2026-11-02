"""Hypothesis profiles shared by the property tests.

Default is 300 examples; HYPOTHESIS_PROFILE=deep runs 20,000.
"""

import os

from hypothesis import settings

settings.register_profile("default", max_examples=300, deadline=None)
settings.register_profile("deep", max_examples=20_000, deadline=None)
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))
