"""Download a pinned public embedding checkpoint once, then build a local index."""
import json
import argparse
from thaimooc.data import read_courses, ROOT
from thaimooc.semantic import MODEL_ID, MODEL_REVISION, MODEL_DIR, build_index, load_model


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default=MODEL_REVISION,
                        help='Pinned Hugging Face revision; override explicitly for a new experiment')
    args = parser.parse_args()
    from huggingface_hub import snapshot_download
    courses = read_courses()  # Check catalog before downloading.
    revision = args.revision
    snapshot_download(repo_id=MODEL_ID, revision=revision, local_dir=str(MODEL_DIR),
                      cache_dir=str(ROOT / 'models/hub-cache'),
                      allow_patterns=['*.json', '*.txt', '*.model', 'model.safetensors'], max_workers=2)
    manifest = build_index(courses, load_model(), revision)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
