"""Assemble a clean release repository (zero private traces).

Copies the public surface of the dev repo into a fresh git repo, excluding:
    .git/  docs/汇报-夜间工作.md  data/pilot/  data/results/  data/generated/
    __pycache__/  papers/ (unless --with-papers)

Usage:
    python scripts/make_release.py [--dest D:\\Projects_PyCharm\\myriad-release] [--with-papers]

After it finishes:
    cd <dest> && gh repo create myriad-bench --public --source . --remote origin --push
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["README.md", "LICENSE", "CONTRIBUTING.md", ".gitignore"]
DIRS = ["assets", "data", "docs", "harness", "spec", "tests", "scripts"]
EXCLUDE_FILES = {"docs/汇报-夜间工作.md"}
# note: "data/pilot" is a PREFIX match on purpose -> also excludes pilot-demo/pilot-stale
EXCLUDE_DIRS = {"__pycache__", ".git", "data/pilot", "data/results", "data/generated", "papers"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="D:/Projects_PyCharm/myriad-bench-release")
    ap.add_argument("--with-papers", action="store_true")
    args = ap.parse_args()

    dest = args.dest
    # never delete anything: if the staging dir exists, pick a fresh suffixed name
    n = 2
    d = dest
    while os.path.exists(d):
        d = f"{dest}-{n}"
        n += 1
    dest = d
    os.makedirs(dest)

    copied, skipped = [], []

    def excluded(frel: str) -> bool:
        if frel in EXCLUDE_FILES:
            return True
        if frel == ".gitignore":
            return False
        if "/__pycache__/" in "/" + frel:
            return True
        return any(frel.startswith(e) for e in EXCLUDE_DIRS)

    def copy_file(frel: str, src_path: str):
        if excluded(frel):
            skipped.append(frel)
            return
        rel = os.path.dirname(frel)
        os.makedirs(os.path.join(dest, rel) if rel else dest, exist_ok=True)
        shutil.copy2(src_path, os.path.join(dest, frel))
        copied.append(frel)

    for name in FILES:
        src = os.path.join(SRC, name)
        if os.path.exists(src):
            copy_file(name, src)
        else:
            skipped.append(name)
    for name in DIRS:
        src = os.path.join(SRC, name)
        if not os.path.exists(src):
            continue
        if name == "papers" and not args.with_papers:
            skipped.append(name)
            continue
        for dirpath, dirnames, filenames in os.walk(src):
            rel = os.path.relpath(dirpath, SRC).replace(os.sep, "/")
            dirnames[:] = [d for d in dirnames
                           if d != "__pycache__"
                           and not any((rel + "/" + d).startswith(e) for e in EXCLUDE_DIRS)]
            for fn in filenames:
                src_path = os.path.join(dirpath, fn)
                frel = (rel + "/" + fn) if rel != "." else fn
                copy_file(frel, src_path)

    # README citation placeholder -> actual account
    readme = os.path.join(dest, "README.md")
    if os.path.exists(readme):
        txt = open(readme, encoding="utf-8").read().replace("github.com/<you>/myriad-bench",
                                                            "github.com/shyringo/myriad-bench")
        open(readme, "w", encoding="utf-8", newline="").write(txt)

    # fresh repo, single clean commit
    subprocess.run(["git", "init", "-b", "main"], cwd=dest, check=True,
                   capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=dest, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.name=shy", "-c", "user.email=shyringo@163.com",
         "commit", "-m", "MyriadBench v0.1: single-session, unbounded multi-task benchmark protocol"],
        cwd=dest, check=True, capture_output=True)

    print(f"release repo -> {dest}")
    print(f"  copied: {len(copied)} files; excluded: {len(skipped)}")
    if skipped:
        print("  excluded:", ", ".join(sorted(set(skipped))[:10]), "...")
    print("\nnext:")
    print(f"  cd {dest}")
    print("  gh repo create myriad-bench --public --source . --remote origin --push")
    print("  (set description/topics/social preview per docs/release-checklist.md)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())