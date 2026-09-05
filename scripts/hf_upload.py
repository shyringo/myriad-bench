"""One-command Hugging Face dataset upload (requires HF token).

    python scripts/hf_upload.py                 # uses HF_TOKEN env var
    python scripts/hf_upload.py --token hf_xxx

Creates/updates dataset repo `shyringo/myriad-bench-pilot` (or --repo NAME)
with data/hf-dataset/* and the data card. Needs the `datasets` or
`huggingface_hub` package (~/SoftwaresSetup conda env).
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data", "hf-dataset")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", default=None)
    ap.add_argument("--repo", default="shyringo/myriad-bench-pilot")
    args = ap.parse_args()

    token = args.token or os.environ.get("HF_TOKEN")
    if not token:
        print("no token: set HF_TOKEN env var or pass --token (https://huggingface.co/settings/tokens)")
        return 1
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("install huggingface_hub first: pip install -U huggingface_hub")
        return 1

    api = HfApi(token=token)
    api.create_repo(repo_id=args.repo, repo_type="dataset", exist_ok=True)
    for fn in ("README.md", "metrics.csv", "sessions.jsonl", "traces.jsonl"):
        path = os.path.join(DATA, fn)
        if os.path.exists(path):
            api.upload_file(path_or_fileobj=path, path_in_repo=fn,
                            repo_id=args.repo, repo_type="dataset")
            print(f"uploaded {fn}")
    print(f"done: https://huggingface.co/datasets/{args.repo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())