"""Small judged-query evaluation; label quality remains a human responsibility."""
import math


def evaluate(engine, cases, k=5):
    rows = []
    for case in cases:
        judgments = case["relevance"]
        if not judgments or not any(v > 0 for v in judgments.values()):
            raise ValueError("Each case needs at least one positively judged course")
        if any(not isinstance(v, int) or not 0 <= v <= 2 for v in judgments.values()):
            raise ValueError("Relevance grades must be 0, 1, or 2")
        hits = engine.search(case["query"], top_k=k, **case.get("filters", {}))
        ids = [r["course"]["course_id"] for r in hits]
        if any(cid not in judgments for cid in ids):
            raise ValueError("Judge every retrieved course before computing metrics")
        grades = [judgments[cid] for cid in ids]
        dcg = sum((2**g-1)/math.log2(i+2) for i, g in enumerate(grades))
        ideal = sorted(judgments.values(), reverse=True)[:k]
        idcg = sum((2**g-1)/math.log2(i+2) for i, g in enumerate(ideal))
        rows.append({"query": case["query"], "ids": ids, "precision_at_k": sum(g > 0 for g in grades)/k,
                     "ndcg_at_k": dcg/idcg if idcg else 0.0})
    if not rows:
        raise ValueError("No evaluation cases")
    return {"k": k, "queries": len(rows), "precision_at_k": sum(r["precision_at_k"] for r in rows)/len(rows),
            "ndcg_at_k": sum(r["ndcg_at_k"] for r in rows)/len(rows), "details": rows}
