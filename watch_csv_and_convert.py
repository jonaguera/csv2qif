#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time
import uuid
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_WATCH_FOLDER = Path.home() / "Descargas"
DEFAULT_OUTPUT_FOLDER = Path.home() / "Documentos" / "csv2qif"
TMP_FOLDER = SCRIPT_DIR / ".tmp"
WATCHED_EXTENSIONS = {".csv", ".xls"}


def is_watched_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in WATCHED_EXTENSIONS


def wait_until_file_ready(path: Path, stable_checks: int = 3, wait_seconds: float = 1.0) -> bool:
    stable_count = 0
    last_size = -1
    last_mtime = -1.0

    while stable_count < stable_checks:
        if not path.exists():
            return False

        try:
            stat = path.stat()
            size = stat.st_size
            mtime = stat.st_mtime
        except OSError:
            return False

        if size > 0 and size == last_size and mtime == last_mtime:
            stable_count += 1
        else:
            stable_count = 0

        last_size = size
        last_mtime = mtime
        time.sleep(wait_seconds)

    return True


def run_command(command: list[str]) -> bool:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode != 0:
        print(f"Error: command returned code {result.returncode}", file=sys.stderr)
        return False
    return True


def run_csv_to_qif(csv_file: Path, output_folder: Path) -> bool:
    command = [sys.executable, str(SCRIPT_DIR / "csv2qif.py"), str(csv_file), str(output_folder)]
    return run_command(command)


def run_xls_pipeline(xls_file: Path, output_folder: Path) -> None:
    TMP_FOLDER.mkdir(parents=True, exist_ok=True)
    temp_csv = TMP_FOLDER / f"{xls_file.stem}-{uuid.uuid4().hex}.csv"
    xls_to_csv_command = [sys.executable, str(SCRIPT_DIR / "xls2csv.py"), str(xls_file), str(temp_csv)]

    try:
        print(f"Converting XLS to temporary CSV: {xls_file}")
        if not run_command(xls_to_csv_command):
            return
        print(f"Converting temporary CSV to QIF: {temp_csv}")
        run_csv_to_qif(temp_csv, output_folder)
    finally:
        if temp_csv.exists():
            temp_csv.unlink()
            print(f"Temporary CSV removed: {temp_csv}")


def process_detected_file(file_path: Path, output_folder: Path) -> None:
    suffix = file_path.suffix.lower()
    print(f"Processing: {file_path}")
    if suffix == ".xls":
        run_xls_pipeline(file_path, output_folder)
    elif suffix == ".csv":
        run_csv_to_qif(file_path, output_folder)


def watch_folder(folder: Path, output_folder: Path, interval: float) -> None:
    seen_files = set()

    for file_path in folder.iterdir():
        if is_watched_file(file_path):
            seen_files.add(file_path.resolve())

    print(f"Watching folder: {folder}")
    print("Waiting for new .csv or .xls files...")

    while True:
        try:
            current_files = []
            for file_path in folder.iterdir():
                if is_watched_file(file_path):
                    current_files.append(file_path.resolve())

            for file_path in current_files:
                if file_path in seen_files:
                    continue

                seen_files.add(file_path)
                print(f"New file detected: {file_path}")

                if wait_until_file_ready(file_path):
                    process_detected_file(file_path, output_folder)
                else:
                    print(f"Skipped (file not available): {file_path}")

            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        except FileNotFoundError:
            print(f"Folder does not exist: {folder}", file=sys.stderr)
            break
        except Exception as exc:
            print(f"Unexpected watcher error: {exc}", file=sys.stderr)
            time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Watch a folder and convert new .csv/.xls files into QIF."
    )
    parser.add_argument(
        "-f",
        "--folder",
        type=Path,
        default=DEFAULT_WATCH_FOLDER,
        help="Folder to watch (default: ~/Descargas).",
    )
    parser.add_argument(
        "-o",
        "--output-folder",
        type=Path,
        default=DEFAULT_OUTPUT_FOLDER,
        help="Destination folder for generated QIF files.",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds (default: 1.0).",
    )
    args = parser.parse_args()

    folder = args.folder.expanduser().resolve()
    output_folder = args.output_folder.expanduser().resolve()
    output_folder.mkdir(parents=True, exist_ok=True)

    if not folder.exists() or not folder.is_dir():
        print(f"Invalid folder: {folder}", file=sys.stderr)
        sys.exit(1)

    watch_folder(folder, output_folder, args.interval)


if __name__ == "__main__":
    main()
