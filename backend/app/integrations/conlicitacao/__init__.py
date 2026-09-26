"""ConLicitacao provider implementation."""

from app.integrations.conlicitacao.client import (
    ConlicitacaoClient,
    ConlicitacaoSettings,
)

__all__ = ["ConlicitacaoClient", "ConlicitacaoSettings"]
