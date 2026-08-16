from __future__ import annotations

import csv
import io
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class CsvMetadata:
    encoding: str
    delimiter: str
    rows_read: int
    columns_read: int


def detect_encoding(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "iso-8859-1"):
        try:
            content.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "iso-8859-1"


def detect_delimiter(text: str) -> str:
    sample = text[:32_768]
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,\t|").delimiter
    except csv.Error:
        return max((";", ",", "\t", "|"), key=lambda delimiter: sample.count(delimiter))


def read_csv(content: bytes) -> tuple[pd.DataFrame, CsvMetadata]:
    encoding = detect_encoding(content)
    text = content.decode(encoding)
    delimiter = detect_delimiter(text)
    frame = pd.read_csv(
        io.StringIO(text),
        sep=delimiter,
        dtype="string",
        keep_default_na=True,
        on_bad_lines="error",
    )
    frame.columns = [str(column).strip() for column in frame.columns]
    for column in frame.columns:
        frame[column] = frame[column].str.strip().replace("", pd.NA)
    return frame, CsvMetadata(encoding, delimiter, len(frame), len(frame.columns))

