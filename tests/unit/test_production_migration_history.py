"""Keep database revisions already deployed to production resolvable."""

from pathlib import Path
import sys

from alembic.script import ScriptDirectory


VERSIONS = Path(__file__).resolve().parents[2] / "backend" / "alembic"
sys.path.insert(0, str(VERSIONS.parent))


def test_production_lpu_revision_is_reachable_from_head():
    scripts = ScriptDirectory(str(VERSIONS))
    assert scripts.get_current_head() == "20261014_01"
    assert scripts.get_revision("20261014_01").down_revision == "20261013_01"
    assert scripts.get_revision("20261013_01").down_revision == "20261012_02"
    assert list(scripts.iterate_revisions("head", "20261014_01")) == []
    assert [revision.revision for revision in scripts.iterate_revisions(
        "head", "20261012_02"
    )] == ["20261014_01", "20261013_01"]
