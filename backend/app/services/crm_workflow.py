from __future__ import annotations


POST_AUCTION_PHASES = ("judgment", "qualification", "appeals", "adjudication", "homologation")


def validate_post_auction_transition(previous: str | None, target: str) -> None:
    if target not in POST_AUCTION_PHASES:
        raise ValueError("Etapa pos-disputa invalida.")
    if previous is not None and previous not in POST_AUCTION_PHASES:
        raise ValueError("A etapa pos-disputa atual e invalida.")


def next_post_auction_phase(current: str | None) -> str:
    if current is None:
        return POST_AUCTION_PHASES[0]
    if current not in POST_AUCTION_PHASES:
        raise ValueError("A etapa pos-disputa atual e invalida.")
    index = POST_AUCTION_PHASES.index(current)
    return POST_AUCTION_PHASES[min(index + 1, len(POST_AUCTION_PHASES) - 1)]


def ensure_not_last_active_admin(
    *, previous_role: str, new_role: str, target_is_active: bool, active_admin_count: int
) -> None:
    if previous_role == "admin" and new_role != "admin" and target_is_active and active_admin_count <= 1:
        raise ValueError("Nao e permitido remover a funcao do ultimo administrador ativo.")
