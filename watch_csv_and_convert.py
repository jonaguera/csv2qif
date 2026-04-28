#!/usr/bin/env python3
import argparse
import shlex
import subprocess
import sys
import time
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_WATCH_FOLDER = Path.home() / "Descargas"
DEFAULT_WATCHED_FILE_TYPE = "csv"
DEFAULT_SCRIPT_TO_INVOKE = SCRIPT_DIR / "csv2qif.py"
DEFAULT_CALL_FORMAT = "csv2qif.py %filename% ~/Documentos/csv2qif"


def normalize_extension(file_type: str) -> str:
    cleaned_type = file_type.strip().lower()
    if not cleaned_type:
        return ".csv"
    if not cleaned_type.startswith("."):
        return f".{cleaned_type}"
    return cleaned_type


def is_watched_file(path: Path, extension: str) -> bool:
    return path.is_file() and path.suffix.lower() == extension


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


def build_command(script_to_invoke: Path, detected_file: Path, call_format: str) -> list[str]:
    command_text = call_format.replace("%filename%", shlex.quote(str(detected_file)))
    command_text = command_text.replace("%script%", shlex.quote(str(script_to_invoke)))
    command = shlex.split(command_text)

    if command and command[0] == script_to_invoke.name:
        command[0] = str(script_to_invoke)

    command = [str(Path(part).expanduser()) if part.startswith("~") else part for part in command]
    if command and command[0].endswith(".py"):
        command.insert(0, sys.executable)

    return command


def run_conversion(script_to_invoke: Path, detected_file: Path, call_format: str) -> None:
    print(f"Processing: {detected_file}")
    command = build_command(script_to_invoke, detected_file, call_format)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)

    if result.returncode != 0:
        print(f"Error: script returned code {result.returncode}", file=sys.stderr)


def watch_folder(
    folder: Path,
    extension: str,
    script_to_invoke: Path,
    call_format: str,
    interval: float,
) -> None:
    seen_files = set()

    for file_path in folder.iterdir():
        if is_watched_file(file_path, extension):
            seen_files.add(file_path.resolve())

    print(f"Watching folder: {folder}")
    print(f"Waiting for new {extension} files...")

    while True:
        try:
            current_files = []
            for file_path in folder.iterdir():
                if is_watched_file(file_path, extension):
                    current_files.append(file_path.resolve())

            for file_path in current_files:
                if file_path in seen_files:
                    continue

                seen_files.add(file_path)
                print(f"New file detected: {file_path}")

                if wait_until_file_ready(file_path):
                    run_conversion(script_to_invoke, file_path, call_format)
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
        description="Watch a folder and run a script when new files appear."
    )
    parser.add_argument(
        "-f",
        "--folder",
        type=Path,
        default=DEFAULT_WATCH_FOLDER,
        help="Folder to watch (default: ~/Descargas).",
    )
    parser.add_argument(
        "-t",
        "--file-type",
        type=str,
        default=DEFAULT_WATCHED_FILE_TYPE,
        help="File extension to watch (default: csv).",
    )
    parser.add_argument(
        "-s",
        "--script",
        type=Path,
        default=DEFAULT_SCRIPT_TO_INVOKE,
        help="Script path to execute (default: csv2qif.py next to this script).",
    )
    parser.add_argument(
        "-c",
        "--call-format",
        type=str,
        default=DEFAULT_CALL_FORMAT,
        help="Execution template. Use %%filename%% for detected file and %%script%% for script path.",
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
    extension = normalize_extension(args.file_type)
    script_to_invoke = args.script.expanduser().resolve()
    call_format = args.call_format

    if "%filename%" not in call_format:
        print("Call template must include the %filename% placeholder.", file=sys.stderr)
        sys.exit(1)

    if not script_to_invoke.exists():
        print(f"Script not found: {script_to_invoke}", file=sys.stderr)
        sys.exit(1)

    if not folder.exists() or not folder.is_dir():
        print(f"Invalid folder: {folder}", file=sys.stderr)
        sys.exit(1)

    watch_folder(folder, extension, script_to_invoke, call_format, args.interval)


if __name__ == "__main__":
    main()
