"""Product kinds are technical identities; manufacturer/sheet names are not kinds."""
import re
from app.services.technical_matching.normalizer import canonical_category

KINDS = {'switch', 'access_point', 'transceiver', 'cabo', 'fonte'}


def product_category(category, description='', model=''):
    text = f'{description or ""} {model or ""}'
    # The primary noun precedes accessory/compatibility mentions: a power supply
    # for a switch is a supply; a switch with a power cable remains a switch.
    candidates = []
    for kind, pattern in [
        ('fonte', r'\bpower supply(?: module)?\b|\bfonte\b|\bpower module\b'),
        ('cabo', r'\b(?:DAC|AOC|cabo|cable|patch cord|cordão)\b'),
        ('access_point', r'\baccess[ -]point\b|\bponto de acesso\b'),
        ('switch', r'\bswitch(?:es)?\b'),
        ('transceiver', r'\btransceiver\b|\btransceptor\b'),
    ]:
        match = re.search(pattern, text, re.I)
        if match:
            candidates.append((match.start(), kind))
    if candidates:
        return min(candidates)[1]
    known = canonical_category(category)
    if known in KINDS:
        return known
    if re.search(r'\b(?:SFP\+?|QSFP\d*|XFP|CFP\d*)\b', text, re.I):
        return 'transceiver'
    return None
