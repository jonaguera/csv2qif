#!/usr/bin/env python3
import argparse
import csv
from dataclasses import dataclass
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
        name="Revolut",
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
        name="Laboral Kutxa",
        header_markers=("Cantidades expresadas en euros",),
        entity_code="LK",
        delimiter=";",
        input_date_format="%d/%m/%Y",
        date_idx=1,
        description_idx=3,
        amount_idx=4,
        skip_header_rows=1,
    ),
    FormatProfile(
        name="Banco Santander",
        header_markers=(",,CUENTA SANTANDER,FECHA,",),
        entity_code="SN",
        delimiter=",",
        input_date_format="%d/%m/%Y",
        date_idx=0,
        description_idx=2,
        amount_idx=3,
        skip_header_rows=8,
    ),
)


def read_file_preview(input_path: Path, lines_to_read: int = 3, first_row: int = 1) -> str:
    preview_lines = []
    with input_path.open("r", encoding="utf-8-sig") as input_file:
        for _ in range(max(first_row - 1, 0)):
            if not input_file.readline():
                return ""
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


def parse_transactions(input_path: Path, profile: FormatProfile, first_row: int = 1) -> list[Transaction]:
    transactions = []
    max_index = max(profile.date_idx, profile.description_idx, profile.amount_idx)

    with input_path.open("r", encoding="utf-8-sig") as csv_file:
        reader = csv.reader(csv_file, delimiter=profile.delimiter)
        for _ in range(max(first_row - 1, 0)):
            next(reader, None)
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


def process_file(
    input_file_path: str,
    output_folder_path: str | None = None,
    first_row: int = 1,
) -> None:
    input_path = Path(input_file_path)
    output_folder = (
        Path(output_folder_path).expanduser()
        if output_folder_path is not None
        else Path.home() / "Documentos" / "csv2qif"
    )
    output_folder.mkdir(parents=True, exist_ok=True)

    try:
        header_preview = read_file_preview(input_path, first_row=first_row)
        profile = detect_format_profile(header_preview)
        if profile is None:
            print("Error: unsupported header format.")
            return

        print(f"Detected: {profile.name}")
        transactions = parse_transactions(input_path, profile, first_row=first_row)
        if not transactions:
            print("Warning: no transactions found.")
            return

        output_path = write_qif_file(transactions, profile, output_folder)
        print(f"Success: {len(transactions)} transactions exported to {output_path}")
        send_notification(output_path)
    except Exception as exc:
        print(f"Critical error: {exc}")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert CSV bank exports to QIF.")
    parser.add_argument("input_file", help="Input CSV file path.")
    parser.add_argument(
        "output_folder",
        nargs="?",
        help="Output folder path. Defaults to ~/Documentos/csv2qif",
    )
    parser.add_argument(
        "--first-row",
        type=int,
        default=1,
        help="First row to read from the CSV file (1-based).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.first_row < 1:
        print("Error: --first-row must be >= 1.")
    else:
        process_file(args.input_file, args.output_folder, args.first_row)