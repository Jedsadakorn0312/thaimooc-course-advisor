"""Local E5 retrieval over the same course text and filters as the baseline."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from threading import Lock
import numpy as np
from .data import ROOT
from .search import eligible_indices

MODEL_ID = 'intfloat/multilingual-e5-small'
MODEL_REVISION = '614241f622f53c4eeff9890bdc4f31cfecc418b3'
MODEL_DIR = ROOT / 'models/multilingual-e5-small'
CACHE_DIR = ROOT / 'data/processed/semantic'


def corpus_fingerprint(courses):
    payload = json.dumps([asdict(c) for c in courses], sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def token_windows(token_ids, size=448, overlap=64):
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError('Invalid chunk window')
    for start in range(0, len(token_ids), size-overlap):
        yield token_ids[start:start+size]
        if start+size >= len(token_ids):
            break


def load_model():
    import torch
    from sentence_transformers import SentenceTransformer
    torch.set_num_threads(4)
    return SentenceTransformer(str(MODEL_DIR), device='cpu', local_files_only=True, trust_remote_code=False)


def build_index(courses, model, revision, destination=CACHE_DIR):
    passages, owners = [], []
    for index, course in enumerate(courses):
        ids = model.tokenizer.encode(course.search_text(), add_special_tokens=False)
        for chunk in token_windows(ids):
            passages.append('passage: ' + model.tokenizer.decode(chunk, skip_special_tokens=True))
            owners.append(index)
    vectors = model.encode(passages, batch_size=8, normalize_embeddings=True, show_progress_bar=True)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {'model_id': MODEL_ID, 'revision': revision, 'corpus_fingerprint': corpus_fingerprint(courses),
                'course_ids': [c.course_id for c in courses], 'courses': len(courses), 'chunks': len(owners),
                'chunk_tokens': 448, 'overlap_tokens': 64, 'aggregation': 'maximum chunk cosine per course',
                'query_prefix': 'query: ', 'passage_prefix': 'passage: ', 'device': 'cpu',
                'max_sequence_length': model.max_seq_length,
                'source_fields': 'Course.search_text(): title twice + description + learning_outcomes'}
    temporary = destination / 'vectors.tmp.npz'
    np.savez_compressed(temporary, vectors=np.asarray(vectors, dtype=np.float32), owners=np.asarray(owners, dtype=np.int32))
    temporary.replace(destination / 'vectors.npz')
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


class SemanticEngine:
    def __init__(self, courses, model, vectors, owners, manifest):
        if manifest['corpus_fingerprint'] != corpus_fingerprint(courses):
            raise ValueError('Semantic cache belongs to a different corpus; rebuild it')
        vectors, owners = np.asarray(vectors), np.asarray(owners)
        if vectors.ndim != 2 or len(vectors) != len(owners) or owners.ndim != 1 or not np.isfinite(vectors).all():
            raise ValueError('Invalid semantic cache arrays')
        if not np.issubdtype(owners.dtype, np.integer) or set(owners.tolist()) != set(range(len(courses))):
            raise ValueError('Semantic cache must cover every course exactly by valid owner indices')
        self.courses, self.model, self.vectors, self.owners = courses, model, vectors, owners
        self.manifest = manifest
        self.lock = Lock()

    @classmethod
    def from_disk(cls, courses, directory=CACHE_DIR):
        directory = Path(directory)
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        # Validate the corpus before the relatively expensive model load.
        if manifest['corpus_fingerprint'] != corpus_fingerprint(courses):
            raise ValueError('Semantic cache belongs to a different corpus; rebuild it')
        with np.load(directory / 'vectors.npz', allow_pickle=False) as archive:
            vectors, owners = archive['vectors'].copy(), archive['owners'].copy()
        return cls(courses, load_model(), vectors, owners, manifest)

    def search(self, query, *, top_k=5, max_hours=None, level=None, category=None):
        eligible = eligible_indices(self.courses, query, top_k, max_hours, level, category)
        if not eligible:
            return []
        with self.lock:
            query_vector = self.model.encode(['query: ' + query], normalize_embeddings=True, show_progress_bar=False)[0]
        chunk_scores = self.vectors @ query_vector
        course_scores = np.full(len(self.courses), -np.inf)
        np.maximum.at(course_scores, self.owners, chunk_scores)
        ranked = sorted(eligible, key=lambda i: (-course_scores[i], i))[:top_k]
        return [{'course': asdict(self.courses[i]), 'score': round(float(course_scores[i]), 6),
                 'method': 'multilingual_e5_small'} for i in ranked]
