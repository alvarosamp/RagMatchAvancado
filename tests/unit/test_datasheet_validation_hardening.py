from app.pipeline.docling_parser import _normalize_extracted_text
from app.services.crm_match_scoring import _has_hard_category_conflict, technical_compatibility_score
from app.services.datasheet_extractor import _extract_specs_heuristic


def test_normalize_extracted_text_collapses_spaced_ocr_words():
    raw = "S F P 1 G 3 1 5 5 1 0 K M\nT r a n s c e p t o r  S F P"

    normalized = _normalize_extracted_text(raw)

    assert "SFP1G315510KM" in normalized
    assert "Transceptor SFP" in normalized


def test_hard_category_conflict_blocks_switch_or_ap_against_transceiver():
    transceiver = "SFP transceiver transceptor fibra monomodo 10km"

    assert _has_hard_category_conflict("Access Point Wi-Fi 6 Ruckus R650 PoE+", transceiver)
    assert _has_hard_category_conflict("Switch 48 portas RJ45 PoE VLAN Layer 3", transceiver)


def test_datasheet_heuristic_extracts_sfp_core_specs():
    text = """
    SFP1G315510KM Transceptor SFP Bidirecional (BiDi) de 1,25 Gbps
    Tx1310nm/Rx1550nm, 10 km. Ate 10 km em fibra monomodo (SMF).
    Formato SFP hot-pluggable. Fonte de alimentacao unica de +3,3V.
    """

    extracted = _extract_specs_heuristic(text, "SFP1G315510KM REV00.pdf")

    assert extracted["model"] == "SFP1G315510KM"
    assert extracted["category"] == "transceiver"
    assert extracted["specs"]["Formato"] == "SFP"
    assert extracted["specs"]["Alcance"] == "10 km"
    assert extracted["specs"]["Tipo de meio"] == "Fibra monomodo"


def test_optical_technical_score_rewards_matching_specs_and_penalizes_conflicts():
    good = technical_compatibility_score(
        "Transceiver SFP+ 10G monomodo LC alcance minimo 10km",
        "SFPX10GDLR10KM transceiver SFP+ 10 Gbps fibra monomodo 10 km",
    )
    bad = technical_compatibility_score(
        "Transceiver SFP+ 10G monomodo LC alcance minimo 10km",
        "SFP1GDSR550M transceiver SFP 1,25 Gbps fibra multimodo 550 m",
    )

    assert good is not None
    assert good.score >= 0.82
    assert bad is not None
    assert bad.score < 0.64
    assert bad.conflicts
