#!/usr/bin/env python3
"""
Package the mobile-api-audit skill into a .skill archive.

Usage:
  python scripts/package.py
  python scripts/package.py --output ../my-skills/

Produces: mobile-api-audit.skill
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
SKILL_NAME = "mobile-api-audit"


def package(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{SKILL_NAME}.skill"

    # skill files are zip archives
    tmp = Path("/tmp") / SKILL_NAME
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(SKILL_DIR, tmp, ignore=shutil.ignore_patterns(
        "*.skill", "__pycache__", ".DS_Store", ".git", "*.pyc"
    ))

    shutil.make_archive(str(output_dir / SKILL_NAME), "zip", tmp.parent, SKILL_NAME)
    zip_path = output_dir / f"{SKILL_NAME}.zip"
    if output_path.exists():
        output_path.unlink()
    zip_path.rename(output_path)

    shutil.rmtree(tmp)
    print(f"✅  Packaged: {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Package the skill into a .skill file")
    parser.add_argument("--output", "-o", default=".", help="Output directory (default: current dir)")
    args = parser.parse_args()

    out = package(Path(args.output))
    print(f"\nInstall with:\n  claude skill install {out}\n")
