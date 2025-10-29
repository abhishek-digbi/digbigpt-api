import pytest

from tools.definitions.common import vo2_score_report
from tools import Tool


def test_vo2_score_report_is_tool():
    assert isinstance(vo2_score_report, Tool)


@pytest.mark.parametrize(
    "vo2, gender, age, expected",
    [
        (42.0, 1, 25, 0),  # Male, under 40, below first cutoff
        (44.0, 1, 25, 6),  # Male, under 40, mid-range
        (46.0, 1, 25, 10),  # Male, under 40, above all cutoffs
        (40.0, 2, 30, 0),  # Female, under 40, below first cutoff
        (37.0, 2, 50, 1),  # Female, age 40-59, just above first cutoff
    ],
)
def test_vo2_score_report_scores(vo2, gender, age, expected):
    score, report = vo2_score_report.func(vo2, gender, age)
    assert score == expected
    assert f"Your VO2 Lung score is — {score}" in report
