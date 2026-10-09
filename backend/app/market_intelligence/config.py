"""A reversible operational switch; collected history is never removed."""

import os


def enabled():
    return os.getenv("MARKET_INTELLIGENCE_ENABLED", "true").lower() in {
        "true",
        "1",
        "yes",
        "on",
    }


def bling_enabled():
    return os.getenv("MARKET_BLING_ANALYTICS_ENABLED", "false").lower() in {
        "true",
        "1",
        "yes",
        "on",
    }
