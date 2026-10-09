from app.market_intelligence.models import ModelRun
from app.market_intelligence.monitoring import quality_snapshot
from app.market_intelligence.repository import scoped


def test_quality_records_missing_source_and_does_not_retrain(db):
    result = quality_snapshot(db, 1)
    assert result["status"] == "alert"
    assert "crm_stale_or_not_loaded" in result["alerts"]
    row = scoped(db, ModelRun, 1).one()
    assert row.report["drift"]["status"] == "insufficient_data"
    assert not row.report["automatic_retraining"]
