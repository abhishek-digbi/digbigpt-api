import pytest

from tools.definitions.common import cgm_score_report
from tools import Tool


def test_cgm_score_report_is_tool():
    assert isinstance(cgm_score_report, Tool)


@pytest.mark.parametrize(
    "tir, expected",
    [
        (90, 5),
        (75, 4),
        (65, 3),
        (55, 2),
        (30, 1),
    ],
)
def test_cgm_score_report_scores(tir, expected):
    score, report = cgm_score_report.func(tir)
    assert score == expected
    assert f"Your CGM TIR: {tir:.0f}%" in report


def test_cgm_score_report_invalid():
    with pytest.raises(ValueError):
        cgm_score_report.func(None)

