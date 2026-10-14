"""A generic, auditable consumer-credit decision engine on synthetic data."""

from .applicant import Applicant
from .decision import Decision, decide, replay

__all__ = ["Applicant", "Decision", "decide", "replay"]
