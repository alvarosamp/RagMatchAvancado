from pathlib import Path

import pytest
from alembic.script import ScriptDirectory


@pytest.fixture
def history():
    return ScriptDirectory(str(Path(__file__).resolve().parents[2] / "backend/alembic"))


@pytest.mark.parametrize("revision", ["20260926_01", "20261009_01", "20261009_02", "20261010_03", "20261012_01"])
def test_released_database_revisions_can_reach_unified_head(history, revision):
    assert history.get_current_head() == "20261012_02"
    upgrades = history._upgrade_revs("head", revision)
    assert upgrades[-1].revision.revision == "20261012_02"
    pending = {step.revision.revision for step in upgrades}
    assert revision not in pending
    if revision == "20261010_03":
        assert pending == {"20261012_01", "20261012_02"}
    if revision == "20261012_01":
        assert pending == {"20261009_01", "20261009_02", "20261010_03", "20261012_02"}
