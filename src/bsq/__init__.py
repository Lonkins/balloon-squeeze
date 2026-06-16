"""Balloon Squeeze — a research instrument for measuring deception displacement.

Inside a multi-agent social-deduction game, a hidden impostor has an incentive to
make false claims. The engine holds ground truth for those claims on *both* sides of
a checkability boundary, and a verifier is announced in some experimental arms. By
replaying the byte-identical seeded world with the verifier toggled on vs off, we
estimate whether dishonesty is reduced (honesty) or merely redistributed onto the
unchecked claims (displacement — the "balloon squeeze").
"""

__version__ = "0.0.1"
