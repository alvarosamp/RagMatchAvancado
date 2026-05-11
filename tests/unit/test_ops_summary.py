from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.ops_summary import summarize_crm, summarize_editais, summarize_jobs


def _dt(hours=0, days=0):
    return datetime.now(timezone.utc) + timedelta(hours=hours, days=days)


def test_summarize_jobs_tracks_active_stale_and_recent_failures():
    now = datetime(2026, 5, 11, 15, 0, tzinfo=timezone.utc)
    jobs = [
        SimpleNamespace(
            id="job-running",
            job_type="upload_edital",
            status="running",
            progress=0.45,
            payload={"filename": "ata.pdf"},
            result=None,
            created_at=now - timedelta(minutes=25),
            started_at=now - timedelta(minutes=21),
            finished_at=None,
            error_message=None,
        ),
        SimpleNamespace(
            id="job-pending",
            job_type="run_matching",
            status="pending",
            progress=0.0,
            payload={"edital_id": 7},
            result=None,
            created_at=now - timedelta(minutes=5),
            started_at=None,
            finished_at=None,
            error_message=None,
        ),
        SimpleNamespace(
            id="job-failed",
            job_type="upload_edital",
            status="failed",
            progress=0.2,
            payload={"filename": "falhou.pdf"},
            result=None,
            created_at=now - timedelta(hours=3),
            started_at=now - timedelta(hours=2, minutes=50),
            finished_at=now - timedelta(hours=2),
            error_message="Erro no parser",
        ),
        SimpleNamespace(
            id="job-done",
            job_type="run_matching",
            status="done",
            progress=1.0,
            payload={},
            result={"filename": "resultado.pdf"},
            created_at=now - timedelta(hours=4),
            started_at=now - timedelta(hours=4),
            finished_at=now - timedelta(hours=3, minutes=30),
            error_message=None,
        ),
    ]

    summary = summarize_jobs(jobs, now=now)

    assert summary["total"] == 4
    assert summary["active_count"] == 2
    assert summary["stale_count"] == 1
    assert summary["failed_last_24h"] == 1
    assert summary["avg_duration_seconds"] == 1800.0
    assert summary["status_counts"]["running"] == 1
    assert summary["status_counts"]["done"] == 1
    assert summary["active_jobs"][0]["id"] == "job-running"
    assert summary["recent_failures"][0]["id"] == "job-failed"


def test_summarize_editais_rolls_up_chunks_and_requirements():
    editais = [
        SimpleNamespace(parsed_at=_dt(days=-2), chunks=[1, 2], requirements=[1]),
        SimpleNamespace(parsed_at=_dt(days=-1), chunks=[1], requirements=[1, 2, 3]),
    ]

    summary = summarize_editais(editais)

    assert summary["total_editais"] == 2
    assert summary["total_chunks"] == 3
    assert summary["total_requirements"] == 4
    assert summary["last_parsed_at"] is not None


def test_summarize_crm_flags_attention_and_upcoming_auctions():
    now = datetime(2026, 5, 11, 15, 0, tzinfo=timezone.utc)
    notices = [
        SimpleNamespace(
            id="n1",
            number="PE-001",
            title="Pregao aberto",
            stage="auction",
            outcome="pending",
            auction_date=now + timedelta(days=2),
            post_auction_phase=None,
            post_auction_deadline=None,
            organ=SimpleNamespace(name="Prefeitura A"),
        ),
        SimpleNamespace(
            id="n2",
            number="PE-002",
            title="Pos-disputa atrasado",
            stage="result",
            outcome="pending",
            auction_date=now - timedelta(days=1),
            post_auction_phase="judgment",
            post_auction_deadline=date(2026, 5, 10),
            organ=SimpleNamespace(name="Prefeitura B"),
        ),
        SimpleNamespace(
            id="n3",
            number="PE-003",
            title="Ganho",
            stage="result",
            outcome="won",
            auction_date=now - timedelta(days=4),
            post_auction_phase="converted",
            post_auction_deadline=None,
            organ=SimpleNamespace(name="Prefeitura C"),
        ),
    ]

    summary = summarize_crm(notices, now=now)

    assert summary["total_notices"] == 3
    assert summary["active_pipeline"] == 2
    assert summary["won_count"] == 1
    assert summary["upcoming_auctions_count"] == 1
    assert summary["overdue_post_auction_count"] == 1
    assert summary["attention_required"] == 2
    assert summary["stage_counts"]["result"] == 2
    assert summary["upcoming_auctions"][0]["number"] == "PE-001"
