import pickle
import numpy as np
import pytest

try:
    from xgboost.core import XGBoostError
except ModuleNotFoundError:
    pytest.skip("xgboost not installed", allow_module_level=True)


import tools.definitions.bioage as bioage_tools
from tools.definitions.bioage import full_bioage_report
from tools import Tool


class DummyScaler:
    def transform(self, X):
        return X


class DummyModel:
    def predict(self, X):
        return np.array([40.0])


def test_full_bioage_report_is_tool():
    assert isinstance(full_bioage_report, Tool)


def test_full_bioage_report(tmp_path, monkeypatch):
    inputs = {
        "LBXGH": 5.8,
        "BMXWAIST": 90,
        "LBDHDD": 35,
        "BMXWT": 80,
        "LBXGLU": 110,
        "BMXBMI": 28,
        "LBDTRSI": 2.5,
        "LBDLDL": 120,
        "BMXHT": 175,
        "RIAGENDR": 1,
        "LBXHSCRP": 1.5,
    }
    bundle = {
        "model": DummyModel(),
        "scaler": DummyScaler(),
        "feature_names": list(inputs.keys()),
    }
    model_path = tmp_path / "model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(bundle, f)

    monkeypatch.setattr(bioage_tools, "MODELS_DIR", str(tmp_path))
    result = full_bioage_report.func(inputs, 50)

    assert result["status"] == "all_inputs"
    assert result["predicted_age"] == 40.0
    assert result["top_4"][:2] == ["LBXGH", "LBXGLU"]


def test_full_bioage_report_real_models():
    pytest.importorskip("xgboost")
    pytest.importorskip("sklearn")

    inputs = {
        "LBXGH": 5.8,
        "BMXWAIST": 90,
        "LBDHDD": 35,
        "BMXWT": 80,
        "LBXGLU": 110,
        "BMXBMI": 28,
        "LBDTRSI": 2.5,
        "LBDLDL": 120,
        "BMXHT": 175,
        "RIAGENDR": 1,
        "LBXHSCRP": 1.5,
    }
    try:
        result = full_bioage_report.func(inputs, 50)
    except XGBoostError:
        pytest.skip("XGBoost runtime not available")
    assert "predicted_age" in result
