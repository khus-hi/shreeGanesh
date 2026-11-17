"""
Skill dictionary used to match job descriptions against your resumes.
Each skill: name -> (regex, weight). Weight 2 = core skill that matters a lot.
Add skills here if you see important ones missing.
"""

import re

SKILLS = {
    # languages
    "Python": (r"\bpython\b", 2),
    "SQL": (r"\bsql\b", 2),
    "R": (r"(?<![\w-])R(?=[\s,/;)]|$)(?!\s*&\s*D)", 1),
    "Scala": (r"\bscala\b", 1),
    "Java": (r"\bjava\b(?!script)", 1),
    "SAS": (r"\bsas\b", 1),
    # python libs
    "pandas": (r"\bpandas\b", 1),
    "NumPy": (r"\bnumpy\b", 1),
    "scikit-learn": (r"scikit-?learn|\bsklearn\b", 1),
    "statsmodels": (r"\bstatsmodels\b", 1),
    "PyTorch": (r"\bpytorch\b|\btorch\b", 1),
    "TensorFlow": (r"\btensorflow\b|\bkeras\b", 1),
    "Gradient boosting": (r"xgboost|lightgbm|catboost|gradient boost", 1),
    "SHAP": (r"\bshap\b", 1),
    # analytics / BI
    "Excel": (r"\bexcel\b", 1),
    "Tableau": (r"\btableau\b", 2),
    "Power BI": (r"power\s?bi", 2),
    "Looker": (r"\blooker\b", 1),
    "Dashboards": (r"dashboard", 1),
    "Data visualization": (r"visuali[sz]ation", 1),
    "KPIs/metrics": (r"\bkpis?\b|metrics definition|business metrics", 1),
    # stats / DS
    "Statistics": (r"statistic", 2),
    "A/B testing": (r"a/b test|ab test|experimentation|split test", 2),
    "Regression": (r"regression", 1),
    "Forecasting": (r"forecast|time[- ]series", 1),
    "Causal inference": (r"causal|difference[- ]in[- ]differences|regression discontinuity|quasi-experiment", 1),
    "Machine learning": (r"machine learning|\bml\b", 2),
    "Deep learning": (r"deep learning|neural network", 1),
    "NLP": (r"\bnlp\b|natural language", 1),
    "LLMs": (r"\bllms?\b|large language model|generative ai|genai|\bgpt\b", 1),
    "RAG": (r"\brag\b|retrieval[- ]augmented", 1),
    "Model evaluation": (r"model evaluation|precision|recall|roc[- ]auc|\bf1\b", 1),
    "EDA": (r"\beda\b|exploratory data analysis", 1),
    # data engineering
    "ETL/ELT": (r"\betl\b|\belt\b|data pipelines?|ingestion", 2),
    "Airflow": (r"\bairflow\b", 1),
    "dbt": (r"\bdbt\b", 1),
    "Spark": (r"\bspark\b|pyspark", 1),
    "Kafka": (r"\bkafka\b", 1),
    "Data modeling": (r"data model|star[- ]schema|dimensional model|data warehous", 1),
    "Data quality": (r"data quality|data validation|data tests?", 1),
    "DuckDB": (r"\bduckdb\b", 1),
    "BigQuery": (r"bigquery", 1),
    "PostgreSQL": (r"postgres", 1),
    "MySQL": (r"\bmysql\b", 1),
    "Snowflake": (r"snowflake", 1),
    "Databricks": (r"databricks", 1),
    "Redshift": (r"redshift", 1),
    "NoSQL": (r"nosql|mongodb|dynamodb|cassandra", 1),
    "Hadoop/Hive": (r"hadoop|\bhive\b", 1),
    # cloud / devops
    "AWS": (r"\baws\b|amazon web services|\bs3\b|sagemaker|\bglue\b|lambda", 1),
    "GCP": (r"\bgcp\b|google cloud", 1),
    "Azure": (r"\bazure\b", 1),
    "Docker": (r"\bdocker\b|container", 1),
    "Kubernetes": (r"kubernetes|\bk8s\b|openshift", 1),
    "CI/CD": (r"ci/cd|github actions|jenkins|continuous integration", 1),
    "Git": (r"\bgit\b|github|gitlab", 1),
    "Testing": (r"pytest|unit test", 1),
    "MLOps": (r"mlops|kubeflow|mlflow|model deployment|model serving", 1),
    "Terraform": (r"terraform", 1),
    "APIs": (r"\brest\b|\bapis?\b|flask|fastapi", 1),
}

COMPILED = {
    name: (re.compile(rx) if name == "R" else re.compile(rx, re.I), w)
    for name, (rx, w) in SKILLS.items()
}


def find_skills(text):
    return {name for name, (rx, _) in COMPILED.items() if rx.search(text or "")}


def weight(skill):
    return SKILLS[skill][1]
