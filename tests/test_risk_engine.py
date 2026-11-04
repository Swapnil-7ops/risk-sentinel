import pytest

from app.services.risk_engine import assess_risk, calculate_score, is_appetite_breach, score_level


@pytest.mark.parametrize(("likelihood", "impact", "score"), [(1, 1, 1), (1, 4, 4), (1, 5, 5), (2, 5, 10), (3, 5, 15), (4, 4, 16), (5, 4, 20), (5, 5, 25)])
def test_score_boundaries(likelihood, impact, score):
    assert calculate_score(likelihood, impact) == score


@pytest.mark.parametrize(("score", "level"), [(1, "Low"), (4, "Low"), (5, "Medium"), (9, "Medium"), (10, "High"), (16, "High"), (17, "Critical"), (25, "Critical")])
def test_level_boundaries(score, level):
    assert score_level(score) == level


def test_assess_risk_and_appetite():
    assert assess_risk(2, 5) == {"score": 10, "level": "High"}
    assert is_appetite_breach(11, 10)
    assert not is_appetite_breach(10, 10)


def test_invalid_values():
    with pytest.raises(ValueError):
        calculate_score(0, 3)
    with pytest.raises(ValueError):
        score_level(26)
