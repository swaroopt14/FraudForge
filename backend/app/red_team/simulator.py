"""Simulator adapter: deterministic generation lives in app.redteam."""

from app.redteam.controller import RedTeamController
from app.redteam.mutations import apply_mutation

__all__ = ["RedTeamController", "apply_mutation"]
