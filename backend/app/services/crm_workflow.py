from __future__ import annotations


POST_AUCTION_PHASES = ("judgment", "qualification", "appeals", "adjudication", "homologation")


def validate_post_auction_transition(previous: str | None, target: str) -> None:
    if target not in POST_AUCTION_PHASES:
        raise ValueError("Etapa pos-disputa invalida.")
    if previous is None:
        if target != POST_AUCTION_PHASES[0]:
            raise ValueError("O fluxo pos-disputa deve iniciar em Julgamento.")
        return
    if previous not in POST_AUCTION_PHASES:
        raise ValueError("A etapa pos-disputa atual e invalida.")
    old_index = POST_AUCTION_PHASES.index(previous)
    new_index = POST_AUCTION_PHASES.index(target)
    if new_index > old_index + 1:
        raise ValueError("O avanco deve ser sequencial; retornos a etapas anteriores sao permitidos.")


def ensure_not_last_active_admin(
    *, previous_role: str, new_role: str, target_is_active: bool, active_admin_count: int
) -> None:
    if previous_role == "admin" and new_role != "admin" and target_is_active and active_admin_count <= 1:
        raise ValueError("Nao e permitido remover a funcao do ultimo administrador ativo.")
