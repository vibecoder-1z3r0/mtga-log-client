import pathlib

import pytest

RANK_LOG_TEMPLATE = (
    "[UnityCrossThreadLogger]1/1/2024 12:00:00 AM: Rank_GetCombinedRankInfo\n"
    '{{"playerId": "{player_id}", "limitedSeasonOrdinal": 1}}\n'
)


def write_rank_log(path: pathlib.Path, player_id: str = "test-user") -> pathlib.Path:
    """Write a minimal Player.log that triggers a single rank-info submission."""
    path.write_text(RANK_LOG_TEMPLATE.format(player_id=player_id))
    return path


@pytest.fixture
def rank_log_file(tmp_path: pathlib.Path) -> pathlib.Path:
    return write_rank_log(tmp_path / "Player.log")
