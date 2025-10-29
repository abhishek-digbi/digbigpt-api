import json
import logging

from tools.services.api_data_processors import process_gut_report


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_process_gut_report_handles_null_overall_score():
    # Load sample payload derived from the provided JSON.
    # The actual service passes the `result` object into the processor.
    with open("tests/fixtures/gut_report_sample.json", "r") as f:
        payload = json.load(f)

    data = payload["result"]

    # Should not raise even if overallScore is null
    result = process_gut_report(data)
    logger.info("process_gut_report output: %s", result)

    print(result)

    assert isinstance(result, dict)
    assert "traits" in result
    assert isinstance(result["traits"], list)

    # With riskDescription present, traits should be extracted
    assert len(result["traits"]) >= 1
    names = {t["name"] for t in result["traits"]}
    assert "Acetate" in names
