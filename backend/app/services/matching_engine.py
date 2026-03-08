"""
services/matching_engine.py
────────────────────────────
Alias de compatibilidade para match_engine.py.

O módulo real é `app.services.match_engine`; este arquivo apenas
re-exporta tudo para que imports usando o nome `matching_engine`
continuem funcionando sem duplicar código.
"""

from app.services.match_engine import (  # noqa: F401
    MatchDetail,
    MatchReport,
    MatchStatus,
    run_matching,
)
