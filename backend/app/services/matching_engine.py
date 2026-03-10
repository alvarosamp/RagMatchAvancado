"""
services/matching_engine.py
────────────────────────────
Re-export do match_engine.py (versão com MLOps integrado).

Este arquivo existe para compatibilidade de imports:
  editais.py importa de 'matching_engine'
  A lógica real está em 'match_engine.py'
"""

from app.services.match_engine import (  # noqa: F401
    MatchDetail,
    MatchReport,
    MatchStatus,
    run_matching,
    match_all_products,
)
