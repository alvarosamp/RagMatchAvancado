__all__ = [
    "get_current_user",
    "get_current_tenant",
    "create_access_token",
    "verify_password",
    "hash_password",
]


def __getattr__(name):
    if name == "get_current_user":
        from .dependencies import get_current_user

        return get_current_user
    if name == "get_current_tenant":
        from .dependencies import get_current_tenant

        return get_current_tenant
    if name in {"create_access_token", "verify_password", "hash_password"}:
        from .security import create_access_token, hash_password, verify_password

        return {
            "create_access_token": create_access_token,
            "verify_password": verify_password,
            "hash_password": hash_password,
        }[name]
    raise AttributeError(name)
