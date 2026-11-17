"""
Picks the best story (experience or project) for a job's outreach email, and pulls
a "why this role" line out of the job description. Free: no AI, just matching.

The story texts themselves live in docs/index.html (STORIES); ids must match.
"""

import re

from skills import find_skills, weight

# story id -> (skills it shows, domain words that make it extra relevant, tracks it suits)
STORIES = {
    "redhat":          ({"Python", "MLOps", "Kubernetes", "LLMs", "ETL/ELT", "Docker", "Machine learning", "NLP", "APIs"},
                        r"pipeline|automat|mlops|platform|production|genai|generative|llm|video|media", {"DE", "DS"}),
    "gbh":             ({"Python", "ETL/ELT", "Dashboards", "Data visualization", "LLMs", "RAG", "Statistics", "EDA"},
                        r"dashboard|census|public|media|news|journalis|nonprofit|government|policy|stakeholder|report", {"DA", "DS"}),
    "muckrock":        ({"Python", "SQL", "ETL/ELT", "Data quality", "EDA"},
                        r"pdf|document|unstructured|extract|records|investigat|cleaning|data entry|compliance|audit", {"DA", "DE"}),
    "experimentation": ({"A/B testing", "Statistics", "Python", "SQL", "dbt", "DuckDB", "Regression"},
                        r"a/b|experiment|test(ing)? and learn|growth|product analytic|marketing|conversion|causal|lift", {"DS", "DA"}),
    "hrrp_dollars":    ({"SQL", "Python", "DuckDB", "Excel", "Tableau", "Dashboards", "Data visualization"},
                        r"health|hospital|medicare|clinical|patient|payer|finance|financial|cost|roi|revenue|pricing", {"DA"}),
    "hrrp_rd":         ({"Causal inference", "Regression", "Statistics", "Python", "SQL", "DuckDB"},
                        r"health|hospital|medicare|policy|econom|causal|evaluation|impact|research", {"DS"}),
    "metro_pulse":     ({"SQL", "Python", "dbt", "DuckDB", "Tableau", "Dashboards", "KPIs/metrics", "ETL/ELT"},
                        r"econom|labor|market|kpi|scorecard|metric|reporting|bi\b|business intelligence|automat", {"DA", "DE"}),
    "bikeshare":       ({"Forecasting", "Gradient boosting", "Causal inference", "Python", "SQL", "Machine learning", "Statistics"},
                        r"forecast|demand|supply|transport|mobility|logistic|operations|planning|location|site", {"DS"}),
    "job_pipeline":    ({"Airflow", "dbt", "DuckDB", "AWS", "Spark", "Data modeling", "Data quality", "ETL/ELT", "SQL", "Python"},
                        r"pipeline|warehouse|lakehouse|orchestrat|batch|ingest|elt|etl|data platform|modeling", {"DE"}),
    "sec_llm":         ({"LLMs", "NLP", "Python", "Airflow", "dbt", "AWS", "Testing", "CI/CD", "Model evaluation"},
                        r"llm|nlp|genai|generative|document|extraction|finance|financial|sec\b|filings|unstructured", {"DE", "DS"}),
    "aki":             ({"BigQuery", "SQL", "Python", "Gradient boosting", "SHAP", "Machine learning", "Model evaluation"},
                        r"health|clinical|patient|hospital|medical|risk|predict|classification|biotech|pharma", {"DS"}),
}
DEFAULT_BY_TRACK = {"DA": "gbh", "DE": "redhat", "DS": "experimentation"}


def pick_story(jd_text, title, track):
    """Best-matching story id for this job."""
    text = f"{title}\n{jd_text or ''}"
    jd_skills = find_skills(text)
    best, best_score = DEFAULT_BY_TRACK.get(track, "experimentation"), -1.0
    for sid, (skills, domain, tracks) in STORIES.items():
        score = sum(weight(s) for s in jd_skills & skills)
        score += 3 * min(len(re.findall(domain, text, re.I)), 3)  # domain fit counts a lot
        score += 2 if track in tracks else 0
        if score > best_score:
            best, best_score = sid, score
    return best


# ---------------- "why this role" line ----------------
SECTION = re.compile(r"(responsibilit|what you.?ll do|what you will do|the role|in this role|your impact|"
                     r"day[- ]to[- ]day|key duties|you will)", re.I)
STOP = re.compile(r"(qualification|requirement|what you.?ll bring|about you|who you are|nice to have|"
                  r"preferred|benefits|compensation|about us|equal opportunity)", re.I)
VERB = re.compile(r"^(build|design|develop|create|own|lead|partner|analy[sz]e|deliver|drive|support|maintain|"
                  r"collaborate|work|translate|define|develop|automate|improve|implement|deploy|monitor|"
                  r"conduct|perform|produce|manage|research|model|turn|use|apply|help|identify|write|"
                  r"present|communicate|prepare|track|measure|optimi[sz]e|scale|architect|integrate)\b", re.I)


def why_line(jd_text, matched_skills):
    """Text that completes: 'I just applied for the X role at Y, and …'"""
    lines = [l.strip(" \t•-*·–—") for l in (jd_text or "").splitlines()]
    in_section, picks = False, []
    for l in lines:
        if not l:
            continue
        if SECTION.search(l) and len(l) < 80:
            in_section = True
            continue
        if STOP.search(l) and len(l) < 80:
            if in_section and picks:
                break
            in_section = False
            continue
        if in_section and VERB.match(l) and 5 <= len(l.split()) <= 30:
            picks.append(l)
    if not picks:  # no clear section: any verb-led bullet-like line
        picks = [l for l in lines if VERB.match(l) and 6 <= len(l.split()) <= 25][:1]
    if picks:
        p = re.split(r"(?<=[.;])\s", picks[0])[0].rstrip(".;:, ")
        words = p.split()
        if len(words) > 20:
            p = " ".join(words[:20]).rstrip(",;") + "…"
        return f"the posting says you'll {p[0].lower() + p[1:]}"
    skills = [s.strip() for s in (matched_skills or "").split(",") if s.strip()][:3]
    if skills:
        s = skills[0] if len(skills) == 1 else ", ".join(skills[:-1]) + " and " + skills[-1]
        return f"the posting puts a lot of weight on {s}"
    return ""
