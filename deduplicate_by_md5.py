#!/usr/bin/env python3

import hashlib
import os
from pathlib import Path

def md5_for_file(filepath, blocksize=65536):
    """Compute MD5 hash of a file (in blocks for large files)."""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        while True:
            buf = f.read(blocksize)
            if not buf:
                break
            hasher.update(buf)
    return hasher.hexdigest()

def deduplicate_by_md5(target_dir):
    # Maps md5 -> list of files with that md5
    md5_to_files = {}
    for file in Path(target_dir).rglob('*'):
        if file.is_file():
            try:
                md5 = md5_for_file(file)
                md5_to_files.setdefault(md5, []).append(file)
            except Exception as e:
                print(f"[x] Error hashing {file}: {e}")

    removed = 0
    for md5, files in md5_to_files.items():
        if len(files) > 1:
            # Pick file with longest name (break ties alphabetically)
            files_sorted = sorted(files, key=lambda f: (-len(str(f)), str(f)))
            to_keep = files_sorted[0]
            to_delete = files_sorted[1:]
            print(f"[DUPLICATE] Keeping: {to_keep}")
            for f in to_delete:
                try:
                    f.unlink()
                    print(f"[DUPLICATE] Removed duplicate: {f}")
                    removed += 1
                except Exception as e:
                    print(f"[x] Could not remove {f}: {e}")
    print(f"[i] Deduplication complete. {removed} duplicate file(s) removed.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = "downloads"
    deduplicate_by_md5(target)

