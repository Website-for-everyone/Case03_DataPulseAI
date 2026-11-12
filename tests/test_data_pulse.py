import pytest
from fastapi.testclient import TestClient
import pandas as pd
import numpy as np
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR in sys.path:
    sys.path.remove(BASE_DIR)
sys.path.insert(0, BASE_DIR)
for mod in list(sys.modules.keys()):
    if mod == "web" or mod.startswith("web.") or mod == "bot" or mod.startswith("bot."):
        del sys.modules[mod]

from web.app import (
    app,
    calculate_dataset_profile,
    calculate_correlation_matrix,
    is_code_safe,
    DATASETS
)
from bot.bot import generate_pdf_report, create_datapulse_bot

client = TestClient(app)

def test_ast_safety_guard():
    # Safe pandas code
    assert is_code_safe("df['Fare'].median()") == True
    assert is_code_safe("df.nlargest(5, 'Age')") == True
    assert is_code_safe("df.groupby('Pclass')['Fare'].mean()") == True

    # Malicious code patterns
    assert is_code_safe("import os; os.system('ls')") == False
    assert is_code_safe("__import__('os').system('ls')") == False
    assert is_code_safe("eval('1 + 1')") == False
    assert is_code_safe("open('/etc/passwd').read()") == False

def test_statistical_profiling():
    df = DATASETS["titanic"]
    profile = calculate_dataset_profile(df)
    assert profile["rows"] == 200
    assert "Fare" in profile["numeric_columns"]
    assert "Sex" in profile["categorical_columns"]

    fare_stats = profile["stats"]["Fare"]
    assert fare_stats["median"] > 0
    assert fare_stats["mean"] > 0
    assert fare_stats["std"] > 0
    assert fare_stats["outliers_count"] >= 0

def test_correlation_matrix():
    df = DATASETS["housing"]
    corr = calculate_correlation_matrix(df)
    assert "columns" in corr
    assert len(corr["columns"]) >= 4
    assert len(corr["matrix"]) == len(corr["columns"])
    # Diagonal should be 1.0
    for i in range(len(corr["columns"])):
        assert abs(corr["matrix"][i][i] - 1.0) < 0.01

def test_api_datasets_and_preview():
    res = client.get("/api/datasets")
    assert res.status_code == 200
    data = res.json()
    assert len(data["datasets"]) == 4

    res2 = client.get("/api/dataset/titanic")
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["rows"] == 200
    assert len(d2["preview"]) <= 15

def test_api_query_endpoint():
    # Natural language query for median
    res = client.post("/api/query", json={
        "dataset_name": "titanic",
        "query_text": "Какая медиана Fare?"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "CALCULATE_MEDIAN"
    assert "value" in data["summary_card"]

    # Blocked dangerous query
    res_bad = client.post("/api/query", json={
        "dataset_name": "titanic",
        "query_text": "import os; os.system('echo hi')"
    })
    assert res_bad.status_code == 400
    assert "AST Security Guard" in res_bad.json()["detail"]

def test_pdf_report_generation():
    df = DATASETS["sales"]
    pdf_bytes = generate_pdf_report(df, "sales_sample.csv")
    assert len(pdf_bytes) > 2000
    # PDF magic bytes
    assert pdf_bytes[:4] == b"%PDF"

def test_datapulse_bot_initialization():
    bot, dp = create_datapulse_bot()
    assert bot is not None
    assert dp is not None
    assert len(dp.sub_routers) >= 1
