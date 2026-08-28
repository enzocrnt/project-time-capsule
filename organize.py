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

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic', '.dng', '.raw', '.arw', '.cr2', '.cr3', '.nef', '.webp', '.bmp', '.tiff'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.3gp', '.m4v', '.wmv', '.webm', '.mts'}

MONTH_NAMES = {
    "01": "Jan.", "02": "Feb.", "03": "Mar.", "04": "Apr.",
    "05": "May",  "06": "Jun.", "07": "Jul.", "08": "Aug.",
    "09": "Sept.", "10": "Oct.", "11": "Nov.", "12": "Dec."
}

PATTERNS = [
    re.compile(r'^(?P<prefix>IMG|VID|PXL|PHOTO|VIDEO|Screenshot|Recording|Screen Recording)?[_\-\s]?(?P<year>\d{4})[_\-]?(?P<month>\d{2})[_\-]?(?P<day>\d{2})', re.IGNORECASE),
    re.compile(r'^(?P<year>\d{4})[_\-\.](?P<month>\d{2})[_\-\.](?P<day>\d{2})', re.IGNORECASE),
]

CONFIG_FILE = Path(__file__).parent / "config.json"
HISTORY_FILE = Path(__file__).parent / "last_run.json"

DEFAULT_PROFILES = {
    "mobile": {
        "name": "Mobile Phone",
        "source_path": "",
        "target_path": ""
    },
    "camera": {
        "name": "Camera / SD Card",
        "source_path": "",
        "target_path": ""
    },
    "computer": {
        "name": "PC / Laptop",
        "source_path": "",
        "target_path": ""
    }
}

def load_config():
    if not CONFIG_FILE.exists():
        data = {
            "active_profile": "mobile",
            "profiles": DEFAULT_PROFILES
        }
        return data
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "profiles" not in data:
                data = {
                    "active_profile": "mobile",
                    "profiles": DEFAULT_PROFILES
                }
            return data
    except Exception:
        return {"active_profile": "mobile", "profiles": DEFAULT_PROFILES}

def save_raw_config(data: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def save_active_profile(profile_key: str, source_path: str, target_path: str, profile_name: str = None):
    config = load_config()
    if profile_key not in config["profiles"]:
        config["profiles"][profile_key] = {
            "name": profile_name or profile_key.replace("_", " ").title(),
            "source_path": "",
            "target_path": ""
        }
    if profile_name:
        config["profiles"][profile_key]["name"] = profile_name

    config["active_profile"] = profile_key
    config["profiles"][profile_key]["source_path"] = source_path
    config["profiles"][profile_key]["target_path"] = target_path
    save_raw_config(config)
    return config

def save_transaction_history(records: list, copy_mode: bool, profile_key: str):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "profile": profile_key,
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
    if not HAS_PILLOW:
        return None
    try:
        with Image.open(file_path) as img:
            exif = img.getexif()
            if not exif:
                return None
            date_str = exif.get(36867) or exif.get(306)
            if date_str:
                dt = datetime.strptime(str(date_str)[:10].replace("-", ":"), "%Y:%m:%d")
                return f"{dt.year:04d}", f"{dt.month:02d}"
    except Exception:
        pass
    return None

def get_destination_subpath(file_path: Path, year_dir: Path = None):
    filename = file_path.stem
    extension = file_path.suffix.lower()

    year, month = None, None
    prefix = ""

    for pattern in PATTERNS:
        match = pattern.match(filename)
        if match:
            groups = match.groupdict()
            year = groups.get('year')
            month = groups.get('month')
            prefix = (groups.get('prefix') or '').upper()
            break

    if not year or not month:
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

    is_video = (
        extension in VIDEO_EXTENSIONS or
        prefix in {"VID", "VIDEO", "RECORDING", "SCREEN RECORDING"} or
        filename.upper().startswith("C00")
    )
    sub_folder = "Vids" if is_video else "Pics"

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

def process_media_stream(source_dir: Path, target_dir: Path, profile_key: str = "default", dry_run: bool = False, copy_mode: bool = False):
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

        year_guess = None
        for p in PATTERNS:
            m = p.match(file_path.stem)
            if m:
                year_guess = m.groupdict().get('year')
                break

        year_dir = target_dir / year_guess if year_guess else None
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
        save_transaction_history(transactions, copy_mode, profile_key)

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