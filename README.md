# Project Time Capsule

A command-line tool written in Python to automatically ingest raw media dumps from mobile devices and organize them into chronological folder structures.

## Overview

When transferring photos and videos from mobile storage to external drives, files often arrive in flat, unsorted directories. Project Time Capsule parses date timestamps directly from media filenames (`IMG_YYYYMMDD_...` and `VID_YYYYMMDD_...`), creates the appropriate year and month directory hierarchy, and routes items into dedicated image and video subdirectories.

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

## Features

- Non-destructive execution: includes a dry-run flag to preview actions before modifying files.
- Conflict detection: prevents accidental overwrites if a target file already exists.
- Configurable defaults: supports path loading via `config.json` alongside standard CLI arguments.
- Zero external dependencies: built using Python standard library modules (`pathlib`, `shutil`, `re`, `argparse`, `json`).

## Setup

1. Clone the repository:
   ```bash
   git clone [https://github.com/your-username/project-time-capsule.git](https://github.com/your-username/project-time-capsule.git)
   cd project-time-capsule
   ```

2. Configure default paths in `config.json`:
   ```json
   {
     "source_path": "/path/to/source/dump",
     "target_path": "/path/to/destination/archive"
   }
   ```

## Usage

### Preview Actions (Dry Run)
Simulate directory creation and file movements without making actual disk changes:
```bash
python organize.py --dry-run
```

### Execute File Organization
Move files using paths defined in `config.json`:
```bash
python organize.py
```

### Override Paths via CLI
Specify custom source and target paths on the fly:
```bash
python organize.py --source /path/to/custom/source --target /path/to/custom/target
```

### Copy Instead of Move
Preserve files in the source directory while creating the organized archive:
```bash
python organize.py --copy
```

## License

MIT