#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

import xlrd


def cell_to_text(cell: xlrd.sheet.Cell, datemode: int) -> str:
    if cell.ctype == xlrd.XL_CELL_DATE:
        dt = xlrd.xldate_as_datetime(cell.value, datemode)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    if cell.ctype == xlrd.XL_CELL_NUMBER:
        number_value = float(cell.value)
        return str(int(number_value)) if number_value.is_integer() else str(number_value)
    if cell.ctype == xlrd.XL_CELL_BOOLEAN:
        return "TRUE" if cell.value else "FALSE"
    return str(cell.value).strip()


def convert_xls_to_csv(
    input_xls: Path,
    output_csv: Path,
    sheet_index: int = 0,
    first_row: int = 1,
) -> None:
    workbook = xlrd.open_workbook(str(input_xls))
    sheet = workbook.sheet_by_index(sheet_index)
    row_start = max(first_row - 1, 0)

    with output_csv.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        for row_idx in range(row_start, sheet.nrows):
            row_values = [
                cell_to_text(sheet.cell(row_idx, col_idx), workbook.datemode)
                for col_idx in range(sheet.ncols)
            ]
            writer.writerow(row_values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert XLS files to UTF-8 CSV.")
    parser.add_argument("input_xls", help="Input XLS file path.")
    parser.add_argument("output_csv", help="Output CSV file path.")
    parser.add_argument(
        "--sheet",
        type=int,
        default=0,
        help="Sheet index to export (0-based).",
    )
    parser.add_argument(
        "--first-row",
        type=int,
        default=1,
        help="First row to export (1-based).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.first_row < 1:
        print("Error: --first-row must be >= 1.")
    else:
        convert_xls_to_csv(
            input_xls=Path(args.input_xls),
            output_csv=Path(args.output_csv),
            sheet_index=args.sheet,
            first_row=args.first_row,
        )
