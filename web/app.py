import os
import io
import ast
import json
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np

app = FastAPI(title="DataPulse AI Backend", version="1.0.0")

# 4 Preloaded Datasets Generation (realistic sample frames)
def init_default_datasets() -> Dict[str, pd.DataFrame]:
    np.random.seed(42)
    n = 200

    # 1. Titanic Dataset
    pclass = np.random.choice([1, 2, 3], size=n, p=[0.25, 0.25, 0.5])
    sex = np.random.choice(["male", "female"], size=n, p=[0.6, 0.4])
    age = np.clip(np.random.normal(30, 14, size=n), 1, 80).round(1)
    fare = np.where(pclass == 1, np.random.exponential(80, n) + 40,
           np.where(pclass == 2, np.random.exponential(25, n) + 15,
                                np.random.exponential(12, n) + 7)).round(2)
    # Survival probability depends on sex and pclass
    prob_surv = 0.2 + (sex == "female") * 0.45 + (pclass == 1) * 0.25 - (age > 60) * 0.1
    prob_surv = np.clip(prob_surv, 0.05, 0.95)
    survived = (np.random.rand(n) < prob_surv).astype(int)

    df_titanic = pd.DataFrame({
        "PassengerId": range(1, n + 1),
        "Survived": survived,
        "Pclass": pclass,
        "Sex": sex,
        "Age": age,
        "Fare": fare,
        "SibSp": np.random.choice([0, 1, 2, 3], size=n, p=[0.7, 0.2, 0.07, 0.03]),
        "Parch": np.random.choice([0, 1, 2], size=n, p=[0.75, 0.18, 0.07])
    })

    # 2. California Real Estate Dataset
    med_inc = np.clip(np.random.normal(4.2, 1.8, size=n), 1.0, 15.0).round(2)
    house_age = np.random.randint(5, 52, size=n)
    ave_rooms = np.clip(np.random.normal(5.4, 1.2, size=n), 2.0, 12.0).round(1)
    pop = np.random.randint(200, 4500, size=n)
    price = (med_inc * 42000 + house_age * 1200 + ave_rooms * 8000 + np.random.normal(50000, 25000, n)).round(-2)
    price = np.clip(price, 80000, 850000)

    df_housing = pd.DataFrame({
        "HouseId": range(101, 101 + n),
        "MedIncome": med_inc,
        "HouseAge": house_age,
        "AveRooms": ave_rooms,
        "Population": pop,
        "PriceUSD": price
    })

    # 3. Spotify Tracks Dataset
    danceability = np.random.beta(5, 2, size=n).round(3)
    energy = np.random.beta(4, 2, size=n).round(3)
    valence = np.random.beta(3, 3, size=n).round(3)
    tempo = np.random.normal(120, 24, size=n).round(1)
    popularity = np.clip((danceability * 35 + energy * 30 + np.random.normal(15, 10, n)), 5, 100).round().astype(int)

    genres = np.random.choice(["Pop", "Hip-Hop", "Indie Rock", "Electronic", "R&B"], size=n)
    df_spotify = pd.DataFrame({
        "TrackId": [f"TRK{i:04d}" for i in range(1, n + 1)],
        "Genre": genres,
        "Danceability": danceability,
        "Energy": energy,
        "Valence": valence,
        "TempoBPM": tempo,
        "Popularity": popularity
    })

    # 4. Global Retail Sales Dataset
    categories = np.random.choice(["Technology", "Furniture", "Office Supplies"], size=n, p=[0.4, 0.3, 0.3])
    revenue = np.where(categories == "Technology", np.random.exponential(1200, n) + 200,
              np.where(categories == "Furniture", np.random.exponential(800, n) + 150,
                                                 np.random.exponential(150, n) + 20)).round(2)
    quantity = np.random.randint(1, 10, size=n)
    discount = np.random.choice([0.0, 0.1, 0.2, 0.3, 0.5], size=n, p=[0.4, 0.3, 0.15, 0.1, 0.05])
    profit = (revenue * (0.35 - discount) + np.random.normal(20, 15, n)).round(2)

    df_sales = pd.DataFrame({
        "OrderId": [f"ORD-{i:05d}" for i in range(1001, 1001 + n)],
        "Category": categories,
        "Revenue": revenue,
        "Quantity": quantity,
        "Discount": discount,
        "Profit": profit
    })

    return {
        "titanic": df_titanic,
        "housing": df_housing,
        "spotify": df_spotify,
        "sales": df_sales
    }

DATASETS = init_default_datasets()

# AST Safety Guard
DISALLOWED_AST_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Delete,
    ast.Global,
    ast.Nonlocal,
    ast.With,
    ast.AsyncWith,
)

DISALLOWED_CALL_NAMES = {
    "eval", "exec", "open", "compile", "__import__", "getattr", "setattr", "delattr",
    "globals", "locals", "system", "popen", "spawn", "subprocess", "socket", "urllib", "requests"
}

def is_code_safe(code_str: str) -> bool:
    try:
        tree = ast.parse(code_str)
        for node in ast.walk(tree):
            if isinstance(node, DISALLOWED_AST_NODES):
                return False
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in DISALLOWED_CALL_NAMES:
                    return False
                if isinstance(node.func, ast.Attribute) and node.func.attr in DISALLOWED_CALL_NAMES:
                    return False
        return True
    except Exception:
        return False

def calculate_dataset_profile(df: pd.DataFrame) -> dict:
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()

    summary_stats = {}
    for col in numeric_cols:
        series = df[col].dropna()
        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outliers = series[(series < lower_bound) | (series > upper_bound)]

        summary_stats[col] = {
            "mean": round(float(series.mean()), 2),
            "median": round(float(series.median()), 2),
            "std": round(float(series.std()), 2),
            "min": round(float(series.min()), 2),
            "max": round(float(series.max()), 2),
            "q25": round(q1, 2),
            "q75": round(q3, 2),
            "iqr": round(iqr, 2),
            "outliers_count": int(len(outliers)),
            "missing_count": int(df[col].isna().sum())
        }

    return {
        "rows": len(df),
        "columns_count": len(df.columns),
        "columns": list(df.columns),
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "stats": summary_stats
    }

def calculate_correlation_matrix(df: pd.DataFrame) -> dict:
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.empty:
        return {"columns": [], "matrix": []}

    corr = numeric_df.corr().round(3).fillna(0)
    matrix = []
    cols = list(corr.columns)
    for col1 in cols:
        row = []
        for col2 in cols:
            row.append(float(corr.loc[col1, col2]))
        matrix.append(row)

    return {
        "columns": cols,
        "matrix": matrix
    }

class QueryRequest(BaseModel):
    dataset_name: str
    query_text: str

class QueryResponse(BaseModel):
    query: str
    intent: str
    code_executed: str
    summary_card: dict
    data_preview: Optional[List[dict]] = None

@app.get("/api/datasets")
def list_datasets():
    meta = []
    for k, v in DATASETS.items():
        meta.append({
            "id": k,
            "name": k.capitalize(),
            "rows": len(v),
            "columns": len(v.columns),
            "column_names": list(v.columns)
        })
    return {"datasets": meta}

@app.get("/api/dataset/{name}")
def get_dataset(name: str):
    if name not in DATASETS:
        raise HTTPException(status_code=404, detail="Датасет не найден")
    df = DATASETS[name]
    return {
        "id": name,
        "rows": len(df),
        "columns": list(df.columns),
        "preview": df.head(15).to_dict(orient="records")
    }

@app.get("/api/dataset/{name}/profile")
def get_dataset_profile(name: str):
    if name not in DATASETS:
        raise HTTPException(status_code=404, detail="Датасет не найден")
    return calculate_dataset_profile(DATASETS[name])

@app.get("/api/dataset/{name}/correlation")
def get_dataset_correlation(name: str):
    if name not in DATASETS:
        raise HTTPException(status_code=404, detail="Датасет не найден")
    return calculate_correlation_matrix(DATASETS[name])

@app.post("/api/query", response_model=QueryResponse)
def execute_query(req: QueryRequest):
    if req.dataset_name not in DATASETS:
        raise HTTPException(status_code=404, detail="Dataset not found")

    df = DATASETS[req.dataset_name]
    q = req.query_text.lower().strip()

    # Safety check on raw query
    if any(bad in q for bad in ["import", "os.", "sys.", "__", "open(", "eval("]):
        raise HTTPException(status_code=400, detail="AST Security Guard: Запрещенный вызов кода обнаружен.")

    # Natural Language translation heuristic
    if "median" in q or "медиан" in q:
        num_cols = df.select_dtypes(include=[np.number]).columns
        target_col = next((c for c in num_cols if c.lower() in q), num_cols[-1])
        val = round(float(df[target_col].median()), 2)
        code = f"df['{target_col}'].median()"
        return QueryResponse(
            query=req.query_text,
            intent="CALCULATE_MEDIAN",
            code_executed=code,
            summary_card={"metric": f"Медиана {target_col}", "value": val, "type": "median"}
        )

    elif "outlier" in q or "выброс" in q:
        num_cols = df.select_dtypes(include=[np.number]).columns
        target_col = next((c for c in num_cols if c.lower() in q), num_cols[-1])
        q1 = df[target_col].quantile(0.25)
        q3 = df[target_col].quantile(0.75)
        iqr = q3 - q1
        outliers = df[(df[target_col] < q1 - 1.5 * iqr) | (df[target_col] > q3 + 1.5 * iqr)]
        code = f"iqr_outliers(df['{target_col}'])"
        return QueryResponse(
            query=req.query_text,
            intent="DETECT_OUTLIERS",
            code_executed=code,
            summary_card={"metric": f"Выбросы по {target_col}", "count": int(len(outliers)), "pct": f"{len(outliers)/len(df)*100:.1f}%"},
            data_preview=outliers.head(5).to_dict(orient="records")
        )

    elif "top" in q or "лучш" in q or "highest" in q:
        num_cols = df.select_dtypes(include=[np.number]).columns
        target_col = num_cols[-1]
        top_df = df.nlargest(5, target_col)
        code = f"df.nlargest(5, '{target_col}')"
        return QueryResponse(
            query=req.query_text,
            intent="TOP_RECORDS",
            code_executed=code,
            summary_card={"metric": f"Топ-5 записей по {target_col}", "top_value": float(top_df[target_col].iloc[0])},
            data_preview=top_df.to_dict(orient="records")
        )

    else:
        # Default statistical summary
        profile = calculate_dataset_profile(df)
        first_num = profile["numeric_columns"][0] if profile["numeric_columns"] else "Rows"
        first_stat = profile["stats"].get(first_num, {"mean": len(df)})
        code = f"df.describe()"
        return QueryResponse(
            query=req.query_text,
            intent="GENERAL_SUMMARY",
            code_executed=code,
            summary_card={
                "metric": f"Обзор {req.dataset_name}",
                "rows": len(df),
                "columns": len(df.columns),
                "sample_mean": first_stat.get("mean", 0)
            }
        )

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(CURRENT_DIR, "index.html")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>DataPulse AI API is running. UI template not found.</h1>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8003, reload=False)
