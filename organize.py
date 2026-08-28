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
HISTORY_FILE = Path(__file__).parent / "last_run.json"

def load_config():
    default_cfg = {"source_path": "", "target_path": ""}
    if not CONFIG_FILE.exists():
        return default_cfg
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {**default_cfg, **data}
    except Exception:
        return default_cfg

def save_config(source_path: str, target_path: str):
    data = {"source_path": source_path, "target_path": target_path}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    return data

def save_transaction_history(records: list, copy_mode: bool):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "copy_mode": copy_mode,
            "records": records
        }, f, indent=4)

def load_transaction_history():
    if not HISTORY_FILE.exists():
        return None
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

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

def get_destination_subpath(file_path: Path, year_dir: Path = None):
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

    month_label = MONTH_NAMES[month]
    month_folder_name = None
    if year_dir and year_dir.exists():
        target_prefix = f"{month}-00-{year}"
        for existing in year_dir.iterdir():
            if existing.is_dir() and existing.name.startswith(target_prefix):
                month_folder_name = existing.name
                break

    if not month_folder_name:
        month_folder_name = f"{month}-00-{year} ({month_label} {year})"
    
    sub_folder = "Vids" if (extension in VIDEO_EXTENSIONS or prefix in {"VID", "VIDEO"}) else "Pics"
    return Path(year) / month_folder_name / sub_folder

def resolve_unique_path(destination_folder: Path, original_name: str) -> Path:
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix
    counter = 1
    new_path = destination_folder / f"{stem}_{counter}{suffix}"
    while new_path.exists():
        counter += 1
        new_path = destination_folder / f"{stem}_{counter}{suffix}"
    return new_path

def rollback_last_run():
    """Rolls back files moved during the last non-dry-run operation."""
    history = load_transaction_history()
    if not history or not history.get("records"):
        return {"status": "error", "message": "No transaction history found to undo."}

    if history.get("copy_mode"):
        return {"status": "error", "message": "Last run was executed in Copy Mode (no files were displaced)."}

    restored = 0
    errors = 0
    records = history["records"]

    for item in reversed(records):
        src_orig = Path(item["source_path"])
        dest_moved = Path(item["dest_path"])

        if dest_moved.exists():
            try:
                src_orig.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(dest_moved, src_orig)
                restored += 1
            except Exception:
                errors += 1

    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()

    return {"status": "ok", "restored": restored, "errors": errors}

def process_media_stream(source_dir: Path, target_dir: Path, dry_run: bool = False, copy_mode: bool = False):
    """Generator yielding real-time stats including bytes moved and saved."""
    if not source_dir.exists():
        yield {"type": "error", "message": f"Source directory does not exist: {source_dir}"}
        return

    all_files = [p for p in source_dir.rglob('*') if p.is_file() and not p.name.startswith('.')]
    total_files = len(all_files)
    
    yield {"type": "start", "total": total_files}

    if total_files == 0:
        yield {
            "type": "done",
            "summary": {
                "processed": 0, "duplicates": 0, "conflicts": 0, "skipped": 0,
                "bytes_processed": 0, "bytes_saved": 0
            }
        }
        return

    action_label = "Copying" if copy_mode else "Moving"
    action_fn = shutil.copy2 if copy_mode else shutil.move
    
    processed = 0
    duplicates = 0
    conflicts = 0
    skipped = 0
    bytes_processed = 0
    bytes_saved = 0
    transactions = []

    for idx, file_path in enumerate(all_files, start=1):
        try:
            file_size = file_path.stat().st_size
        except Exception:
            file_size = 0

        match = FILENAME_PATTERN.match(file_path.stem)
        year_dir = target_dir / match.group('year') if match else None
        subpath = get_destination_subpath(file_path, year_dir=year_dir)
        
        if not subpath:
            skipped += 1
            yield {
                "type": "progress", "index": idx, "total": total_files,
                "status": "SKIP", "file": file_path.name, "target": "Unmatched metadata format",
                "bytes_processed": bytes_processed, "bytes_saved": bytes_saved, "bytes_current": file_size
            }
            continue

        dest_folder = target_dir / subpath
        dest_path = dest_folder / file_path.name
        rel_dest = str(subpath / dest_path.name).replace("\\", "/")

        if not dry_run:
            dest_folder.mkdir(parents=True, exist_ok=True)
            if dest_path.exists():
                src_hash = compute_sha256(file_path)
                dest_hash = compute_sha256(dest_path)
                if src_hash == dest_hash:
                    duplicates += 1
                    bytes_saved += file_size
                    yield {
                        "type": "progress", "index": idx, "total": total_files,
                        "status": "DUPLICATE", "file": file_path.name, "target": "Exact SHA-256 twin (Skipped)",
                        "bytes_processed": bytes_processed, "bytes_saved": bytes_saved, "bytes_current": file_size
                    }
                    continue
                else:
                    dest_path = resolve_unique_path(dest_folder, file_path.name)
                    rel_dest = str(subpath / dest_path.name).replace("\\", "/")
                    conflicts += 1

            action_fn(file_path, dest_path)
            processed += 1
            bytes_processed += file_size

            transactions.append({
                "source_path": str(file_path),
                "dest_path": str(dest_path)
            })

            yield {
                "type": "progress", "index": idx, "total": total_files,
                "status": action_label.upper(), "file": file_path.name, "target": rel_dest,
                "bytes_processed": bytes_processed, "bytes_saved": bytes_saved, "bytes_current": file_size
            }
        else:
            processed += 1
            bytes_processed += file_size
            yield {
                "type": "progress", "index": idx, "total": total_files,
                "status": "DRY-RUN", "file": file_path.name, "target": rel_dest,
                "bytes_processed": bytes_processed, "bytes_saved": bytes_saved, "bytes_current": file_size
            }

    if not dry_run and transactions:
        save_transaction_history(transactions, copy_mode)

    yield {
        "type": "done",
        "summary": {
            "processed": processed,
            "duplicates": duplicates,
            "conflicts": conflicts,
            "skipped": skipped,
            "bytes_processed": bytes_processed,
            "bytes_saved": bytes_saved
        }
    }