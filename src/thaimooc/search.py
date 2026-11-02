"""Thai-friendly character TF-IDF baseline; scores are not probabilities."""
from dataclasses import asdict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


def eligible_indices(courses, query, top_k=5, max_hours=None, level=None, category=None):
    if not query.strip():
        raise ValueError("Query must not be blank")
    if not 1 <= top_k <= 20:
        raise ValueError("top_k must be between 1 and 20")
    if max_hours is not None and (not np.isfinite(max_hours) or max_hours <= 0):
        raise ValueError("max_hours must be positive")
    return [i for i, c in enumerate(courses)
            if (max_hours is None or (c.duration_hours is not None and c.duration_hours <= max_hours))
            and (level is None or c.level == level)
            and (category is None or c.category == category)]


class SearchEngine:
    def __init__(self, courses):
        if not courses:
            raise ValueError("Cannot index an empty catalog")
        self.courses = courses
        # Character n-grams handle Thai without assuming whitespace word boundaries.
        self.vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 5), sublinear_tf=True, max_features=100_000)
        self.matrix = self.vectorizer.fit_transform([c.search_text() for c in courses])

    def search(self, query, *, top_k=5, max_hours=None, level=None, category=None, min_score=0.10):
        eligible = set(eligible_indices(self.courses, query, top_k, max_hours, level, category))
        if min_score is not None and not 0 <= min_score <= 1:
            raise ValueError("min_score must be between 0 and 1")
        scores = (self.matrix @ self.vectorizer.transform([query]).T).toarray().ravel()
        results = []
        for index in np.argsort(-scores, kind="stable"):
            c = self.courses[index]
            if index not in eligible:
                continue
            if min_score is not None and (scores[index] <= 0 or scores[index] < min_score):
                continue
            results.append({"course": asdict(c), "score": round(float(scores[index]), 6), "method": "char_tfidf"})
            if len(results) == top_k:
                break
        return results
