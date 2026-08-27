#!/usr/bin/env python3
import os
import re
import json
import shutil
import hashlib
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic', '.dng', '.raw', '.webp'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.3gp', '.m4v'}

MONTH_NAMES = {
    "01": "Jan.", "02": "Feb.", "03": "Mar.", "04": "Apr.",
    "05": "May",  "06": "Jun.", "07": "Jul.", "08": "Aug.",
    "09": "Sept.", "10": "Oct.", "11": "Nov.", "12": "Dec."
}

FILENAME_PATTERN = re.compile(
    r'^(?P<prefix>IMG|VID|PXL|PHOTO|VIDEO|Screenshot)?[_\-]?'
    r'(?P<year>\d{4})[_\-]?'
    r'(?P<month>\d{2})[_\-]?'
    r'(?P<day>\d{2})',
    re.IGNORECASE
)

CONFIG_FILE = Path(__file__).parent / "config.json"

def load_config():
    if not CONFIG_FILE.exists():
        return {"source_path": "", "target_path": ""}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"source_path": "", "target_path": ""}

def save_config(source_path: str, target_path: str):
    data = {"source_path": source_path, "target_path": target_path}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    return data

def compute_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()

def extract_exif_date(file_path: Path):
    if not HAS_PILLOW or file_path.suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    try:
        with Image.open(file_path) as img:
            exif = img.getexif()
            if not exif:
                return None
            date_str = exif.get(36867) or exif.get(306)
            if date_str:
                dt = datetime.strptime(str(date_str)[:10], "%Y:%m:%d")
                return f"{dt.year:04d}", f"{dt.month:02d}"
    except Exception:
        pass
    return None

def get_folder_metadata(file_path: Path, year_dir: Path = None):
    filename = file_path.stem
    extension = file_path.suffix.lower()
    match = FILENAME_PATTERN.match(filename)

    year, month = None, None
    prefix = ""

    if match:
        year = match.group('year')
        month = match.group('month')
        prefix = (match.group('prefix') or '').upper()
    else:
        exif_result = extract_exif_date(file_path)
        if exif_result:
            year, month = exif_result
        else:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            year, month = f"{mtime.year:04d}", f"{mtime.month:02d}"

    if month not in MONTH_NAMES:
        return None

    month_folder_name = None
    if year_dir and year_dir.exists():
        target_prefix = f"{month}-00-{year}"
        for existing in year_dir.iterdir():
            if existing.is_dir() and existing.name.startswith(target_prefix):
                month_folder_name = existing.name
                break

    if not month_folder_name:
        month_label = MONTH_NAMES[month]
        month_folder_name = f"{month}-00-{year} ({month_label} {year})"
    
    sub_folder = "Vids" if (extension in VIDEO_EXTENSIONS or prefix in {"VID", "VIDEO"}) else "Pics"
    return year, month_folder_name, sub_folder

def resolve_unique_path(destination_folder: Path, original_name: str) -> Path:
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix
    counter = 1
    new_path = destination_folder / f"{stem}_{counter}{suffix}"
    while new_path.exists():
        counter += 1
        new_path = destination_folder / f"{stem}_{counter}{suffix}"
    return new_path

def process_media_stream(source_dir: Path, target_dir: Path, dry_run: bool = False, copy_mode: bool = False):
    """Generator that yields real-time progress dicts for FastAPI SSE."""
    if not source_dir.exists():
        yield {"type": "error", "message": f"Source directory does not exist: {source_dir}"}
        return

    all_files = [p for p in source_dir.rglob('*') if p.is_file() and not p.name.startswith('.')]
    total_files = len(all_files)
    
    yield {"type": "start", "total": total_files}

    if total_files == 0:
        yield {"type": "done", "summary": {"processed": 0, "duplicates": 0, "conflicts": 0, "skipped": 0}}
        return

    action_label = "Copying" if copy_mode else "Moving"
    action_fn = shutil.copy2 if copy_mode else shutil.move
    
    processed = 0
    duplicates = 0
    conflicts = 0
    skipped = 0

    for idx, file_path in enumerate(all_files, start=1):
        match = FILENAME_PATTERN.match(file_path.stem)
        year_dir = target_dir / match.group('year') if match else None
        metadata = get_folder_metadata(file_path, year_dir=year_dir)
        
        if not metadata:
            skipped += 1
            yield {
                "type": "progress", "index": idx, "total": total_files,
                "status": "SKIP", "file": file_path.name, "target": "Unmatched metadata format"
            }
            continue

        year, month_folder, sub_folder = metadata
        dest_folder = target_dir / year / month_folder / sub_folder
        dest_path = dest_folder / file_path.name
        rel_dest = f"{year}/{month_folder}/{sub_folder}/{dest_path.name}"

        if not dry_run:
            dest_folder.mkdir(parents=True, exist_ok=True)
            if dest_path.exists():
                src_hash = compute_sha256(file_path)
                dest_hash = compute_sha256(dest_path)
                if src_hash == dest_hash:
                    duplicates += 1
                    yield {
                        "type": "progress", "index": idx, "total": total_files,
                        "status": "DUPLICATE", "file": file_path.name, "target": "Exact SHA-256 match (Skipped)"
                    }
                    continue
                else:
                    dest_path = resolve_unique_path(dest_folder, file_path.name)
                    rel_dest = f"{year}/{month_folder}/{sub_folder}/{dest_path.name}"
                    conflicts += 1
                    yield {
                        "type": "progress", "index": idx, "total": total_files,
                        "status": "CONFLICT", "file": file_path.name, "target": f"Auto-renamed -> {dest_path.name}"
                    }

            action_fn(file_path, dest_path)
            processed += 1
            yield {
                "type": "progress", "index": idx, "total": total_files,
                "status": action_label.upper(), "file": file_path.name, "target": rel_dest
            }
        else:
            processed += 1
            yield {
                "type": "progress", "index": idx, "total": total_files,
                "status": "DRY-RUN", "file": file_path.name, "target": rel_dest
            }

    yield {
        "type": "done",
        "summary": {
            "processed": processed,
            "duplicates": duplicates,
            "conflicts": conflicts,
            "skipped": skipped
        }
    }