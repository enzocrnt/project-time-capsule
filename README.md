Here is the clean, updated `README.md` that accurately reflects the web dashboard, multi-device ingestion, and zero-manual-config setup of **v2.4.0**:

```markdown
# Project Time Capsule

A local media ingestion pipeline and dashboard written in Python to organize raw photo dumps, camera RAWs, and screen recordings into a chronological archive.

---

## Overview

When transferring photos and videos from phones, SD cards, or computer capture folders, files often arrive in flat, disorganized directories. Project Time Capsule automatically reads date stamps from filenames and embedded EXIF metadata, creates a chronological year/month folder structure, and separates images and videos into clean subdirectories.

---

## Target Directory Structure

```text
Archive Root/
└── 2026/
    ├── 01-00-2026 (Jan. 2026)/
    │   ├── Pics/
    │   └── Vids/
    ├── 02-00-2026 (Feb. 2026)/
    │   ├── Pics/
    │   └── Vids/
    └── ...

```

---

## Features

* **Local Web Dashboard:** Intuitive browser interface running locally with real-time throughput metrics (MB/s), dynamic ETAs, and a live activity feed.
* **Multi-Device Routing Profiles:** Switch between dedicated profiles (*Mobile Phone*, *Camera / SD Card*, and *PC / Laptop*). Each profile independently remembers its own source inbox and archive vault.
* **Camera RAW & Video Support:** Parses standard camera conventions (`DSC0001`, `C0001`, `CLIP0001`) and RAW files (`.ARW`, `.DNG`, `.CR2`, `.CR3`, `.NEF`), reading embedded EXIF capture dates.
* **Screen Recordings & PC Captures:** Built-in pattern recognition and timestamp fallback for OBS recordings, Windows Snipping Tool clips, and desktop screenshots.
* **Incoming Media Preview:** Thumbnail preview strip with format badges (`ARW`, `JPG`, `MP4`, `MOV`) to inspect files before organizing.
* **SHA-256 Deduplication:** Prevents duplicate imports by matching file hashes and tracks total disk space saved.
* **Batch Undo Rollback:** Reverses the last non-dry-run operation and safely returns files to the source directory in one click.
* **Non-Destructive Dry Run & Copy Modes:** Test your layout safely in preview mode or duplicate files without altering source media.

---

## Setup & Quickstart

1. **Clone the repository:**
```bash
git clone [https://github.com/enzocrnt/project-time-capsule.git](https://github.com/enzocrnt/project-time-capsule.git)
cd project-time-capsule

```


2. **Install dependencies:**
```bash
pip install -r requirements.txt

```


3. **Launch the application:**
```bash
python app.py

```


*Your default browser will launch automatically at `http://localhost:8000`.*

---

## Usage

1. Choose your device profile tab (**Mobile Phone**, **Camera / SD Card**, or **PC / Laptop**).
2. Click **Browse** next to *Unsorted Media Folder* to select your raw dump.
3. Click **Browse** next to *Dedicated Archive Destination* to set your target directory.
* *Your paths save automatically to your local machine on selection.*


4. Keep **Safe Preview Mode (Dry-Run)** enabled and click **Run Safe Preview** to check the output structure.
5. Uncheck Safe Preview Mode and click **Start Media Sorting** to execute the pipeline.

---

## Configuration

No manual JSON editing is required. The application automatically generates and updates your configuration locally upon folder selection. Configuration files and transaction logs are git-ignored by default to keep your personal directory paths private.

---

## License

MIT

```

```