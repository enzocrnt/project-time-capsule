#!/usr/bin/env python3
import os
import re
import json
import shutil
import argparse
from pathlib import Path

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic', '.dng', '.raw', '.webp'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.3gp', '.m4v'}

MONTH_NAMES = {
    "01": "Jan.",
    "02": "Feb.",
    "03": "Mar.",
    "04": "Apr.",
    "05": "May",
    "06": "Jun.",
    "07": "Jul.",
    "08": "Aug.",
    "09": "Sept.",
    "10": "Oct.",
    "11": "Nov.",
    "12": "Dec."
}

FILENAME_PATTERN = re.compile(
    r'^(?P<prefix>IMG|VID|PXL|PHOTO|VIDEO)?_?(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})',
    re.IGNORECASE
)

CONFIG_FILE = Path(__file__).parent / "config.json"

def load_config():
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Error reading config.json: {e}")
        return {}

def get_folder_metadata(filename: str, extension: str, year_dir: Path = None):
    match = FILENAME_PATTERN.match(filename)
    if not match:
        return None

    year = match.group('year')
    month = match.group('month')
    
    if month not in MONTH_NAMES:
        return None

    month_folder_name = None
    if year_dir and year_dir.exists():
        prefix = f"{month}-00-{year}"
        for existing in year_dir.iterdir():
            if existing.is_dir() and existing.name.startswith(prefix):
                month_folder_name = existing.name
                break

    if not month_folder_name:
        month_label = MONTH_NAMES[month]
        month_folder_name = f"{month}-00-{year} ({month_label} {year})"
    
    ext = extension.lower()
    if ext in IMAGE_EXTENSIONS or filename.upper().startswith("IMG"):
        sub_folder = "Pics"
    elif ext in VIDEO_EXTENSIONS or filename.upper().startswith("VID"):
        sub_folder = "Vids"
    else:
        sub_folder = "Pics"

    return year, month_folder_name, sub_folder

def process_media(source_dir: Path, target_dir: Path, dry_run: bool = False, copy_mode: bool = False):
    if not source_dir.exists():
        print(f"[!] Source path does not exist: {source_dir}")
        return

    action_label = "Copying" if copy_mode else "Moving"
    action_fn = shutil.copy2 if copy_mode else shutil.move
    
    processed_count = 0
    skipped_count = 0

    for file_path in source_dir.iterdir():
        if file_path.is_dir() or file_path.name.startswith('.'):
            continue

        match = FILENAME_PATTERN.match(file_path.stem)
        year_dir = target_dir / match.group('year') if match else None

        metadata = get_folder_metadata(file_path.stem, file_path.suffix, year_dir=year_dir)
        
        if not metadata:
            print(f"[SKIP] Unmatched filename format: {file_path.name}")
            skipped_count += 1
            continue

        year, month_folder, sub_folder = metadata
        destination_folder = target_dir / year / month_folder / sub_folder
        destination_path = destination_folder / file_path.name

        print(f"[{'DRY-RUN' if dry_run else action_label}] {file_path.name} -> {destination_folder.relative_to(target_dir)}")

        if not dry_run:
            destination_folder.mkdir(parents=True, exist_ok=True)
            
            if destination_path.exists():
                print(f"[!] Conflict: {destination_path.name} already exists in destination. Skipping.")
                continue
                
            action_fn(file_path, destination_path)

        processed_count += 1

    print("\n--- Summary ---")
    print(f"Processed: {processed_count} files")
    print(f"Skipped:   {skipped_count} files")

def main():
    config = load_config()
    default_source = config.get("source_path")
    default_target = config.get("target_path")

    parser = argparse.ArgumentParser(description="Automate phone media transfer and year/month organization.")
    parser.add_argument("-s", "--source", type=Path, default=default_source, help="Source folder where raw phone dumps sit.")
    parser.add_argument("-t", "--target", type=Path, default=default_target, help="Target root directory.")
    parser.add_argument("--dry-run", action="store_true", help="Preview moves without writing or relocating files.")
    parser.add_argument("--copy", action="store_true", help="Copy files instead of moving them.")

    args = parser.parse_args()

    if not args.source or not args.target:
        print("[!] Missing paths. Provide them via CLI flags (--source / --target) or configure config.json.")
        return

    process_media(Path(args.source), Path(args.target), dry_run=args.dry_run, copy_mode=args.copy)

if __name__ == "__main__":
    main()