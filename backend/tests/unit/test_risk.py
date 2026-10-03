import pytest

from app.domain.errors import ValidationError
from app.domain.risk import level_for, risk_level, risk_score


def test_score_is_severity_times_likelihood():
    assert risk_score(5, 3) == 15
    assert risk_score(1, 1) == 1


@pytest.mark.parametrize(
    "score,level",
    [(1, "low"), (7, "low"), (8, "medium"), (14, "medium"), (15, "high"), (25, "high")],
)
def test_level_boundaries(score, level):
    assert risk_level(score) == level


def test_level_for_matches_seed_example():
    assert level_for(5, 3) == "high"  # RISK-002 in the seed data
    assert level_for(4, 3) == "medium"  # RISK-003


@pytest.mark.parametrize("bad", [0, 6, -1, 2.5, "3", None, True])
def test_scale_rejects_bad_values(bad):
    with pytest.raises(ValidationError):
        risk_score(bad, 3)
    with pytest.raises(ValidationError):
        risk_score(3, bad)
