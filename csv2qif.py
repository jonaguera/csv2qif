#!/usr/bin/env python3
import csv
from dataclasses import dataclass
import sys
import subprocess
from pathlib import Path
from datetime import datetime

@dataclass(frozen=True)
class FormatProfile:
    name: str
    header_markers: tuple[str, ...]
    entity_code: str
    delimiter: str
    input_date_format: str
    date_idx: int
    description_idx: int
    amount_idx: int
    skip_header_rows: int = 1


@dataclass
class Transaction:
    qif_date: str
    original_date: datetime
    amount: str
    description: str


FORMAT_PROFILES = (
    FormatProfile(
        name="Digital format (Type A)",
        header_markers=("Tipo,Producto",),
        entity_code="RV",
        delimiter=",",
        input_date_format="%Y-%m-%d",
        date_idx=2,
        description_idx=4,
        amount_idx=5,
        skip_header_rows=1,
    ),
    FormatProfile(
        name="Traditional bank format (Type B)",
        header_markers=("Cantidades expresadas en euros",),
        entity_code="LK",
        delimiter=";",
        input_date_format="%d/%m/%Y",
        date_idx=1,
        description_idx=3,
        amount_idx=4,
        skip_header_rows=1,
    ),
)


def read_file_preview(input_path: Path, lines_to_read: int = 3) -> str:
    preview_lines = []
    with input_path.open("r", encoding="utf-8-sig") as input_file:
        for _ in range(lines_to_read):
            line = input_file.readline()
            if not line:
                break
            preview_lines.append(line)
    return "".join(preview_lines)


def detect_format_profile(header_preview: str) -> FormatProfile | None:
    normalized_preview = header_preview.lower()
    for profile in FORMAT_PROFILES:
        if all(marker.lower() in normalized_preview for marker in profile.header_markers):
            return profile
    return None


def parse_transactions(input_path: Path, profile: FormatProfile) -> list[Transaction]:
    transactions = []
    max_index = max(profile.date_idx, profile.description_idx, profile.amount_idx)

    with input_path.open("r", encoding="utf-8-sig") as csv_file:
        reader = csv.reader(csv_file, delimiter=profile.delimiter)
        for _ in range(profile.skip_header_rows):
            next(reader, None)

        for row in reader:
            if not row or len(row) <= max_index:
                continue
            try:
                raw_date = row[profile.date_idx].strip().split(" ")[0]
                parsed_date = datetime.strptime(raw_date, profile.input_date_format)
                qif_date = parsed_date.strftime("%d/%m/%Y")
                amount = row[profile.amount_idx].strip().replace(",", ".")
                description = row[profile.description_idx].strip()
                transactions.append(
                    Transaction(
                        qif_date=qif_date,
                        original_date=parsed_date,
                        amount=amount,
                        description=description,
                    )
                )
            except (ValueError, IndexError):
                continue

    return transactions


def write_qif_file(transactions: list[Transaction], profile: FormatProfile, output_folder: Path) -> Path:
    start_date = min(t.original_date for t in transactions).strftime("%Y%m%d")
    end_date = max(t.original_date for t in transactions).strftime("%Y%m%d")
    qif_name = f"{profile.entity_code}{start_date}-{end_date}.qif"
    output_path = output_folder / qif_name

    with output_path.open("w", encoding="utf-8") as qif_file:
        qif_file.write("!Type:Bank\n")
        for transaction in transactions:
            qif_file.write(
                f"D{transaction.qif_date}\n"
                f"T{transaction.amount}\n"
                f"P{transaction.description}\n^\n"
            )

    return output_path


def send_notification(output_path: Path) -> None:
    subprocess.run(
        ["notify-send", "QIF Generated", f"File {output_path.name} ready in {output_path.parent}"],
        check=False,
    )


def process_file(input_file_path: str, output_folder_path: str | None = None) -> None:
    input_path = Path(input_file_path)
    output_folder = (
        Path(output_folder_path).expanduser()
        if output_folder_path is not None
        else Path.home() / "Documentos" / "csv2qif"
    )
    output_folder.mkdir(parents=True, exist_ok=True)

    try:
        header_preview = read_file_preview(input_path)
        profile = detect_format_profile(header_preview)
        if profile is None:
            print("Error: unsupported header format.")
            return

        print(f"Detected: {profile.name}")
        transactions = parse_transactions(input_path, profile)
        if not transactions:
            print("Warning: no transactions found.")
            return

        output_path = write_qif_file(transactions, profile, output_folder)
        print(f"Success: {len(transactions)} transactions exported to {output_path}")
        send_notification(output_path)
    except Exception as exc:
        print(f"Critical error: {exc}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 csv2qif.py input_file.csv [output_folder]")
    else:
        target_output_folder = sys.argv[2] if len(sys.argv) > 2 else None
        process_file(sys.argv[1], target_output_folder)