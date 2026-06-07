#!/usr/bin/env python3
"""Gabungkan semua file sumber nama menjadi file bersih, unik, + BERBOBOT.

Output:
    data/first_names.txt          -> nama depan unik (ASCII, huruf kecil)
    data/last_names.txt           -> nama belakang unik
    data/first_names_weighted.tsv -> "nama<TAB>bobot" (bobot = popularitas)
    data/last_names_weighted.tsv  -> "nama<TAB>bobot" (bobot = jumlah sensus)

Bobot dipakai generator untuk sampling REALISTIS: nama umum (John, Smith)
muncul jauh lebih sering daripada nama langka, seperti distribusi manusia nyata.

Pembersihan tiap nama:
    - decompose unicode & buang aksen (José -> jose)
    - huruf kecil semua, hanya simpan a-z
    - panjang 2..20 karakter
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

MIN_LEN = 2
MAX_LEN = 20


def clean(raw: str) -> str:
    """Normalisasi nama menjadi ASCII huruf kecil a-z saja."""
    if not raw:
        return ""
    decomposed = unicodedata.normalize("NFKD", raw)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    letters = "".join(ch for ch in ascii_only.lower() if "a" <= ch <= "z")
    if MIN_LEN <= len(letters) <= MAX_LEN:
        return letters
    return ""


def _read_lines(filename: str):
    path = ROOT / filename
    if not path.exists():
        print(f"  ! lewati (tidak ada): {filename}", file=sys.stderr)
        return
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        yield from fh


def build_first_names() -> dict[str, int]:
    """Kumpulkan nama depan + bobot popularitas.

    Bobot dari firstnames.csv: tiap sel berisi kode frekuensi per negara
    (-8 = paling langka .. +2 = paling umum). Popularitas = jumlah
    2**(kode+8) atas semua negara tempat nama itu muncul. Nama yang ada
    di banyak negara dengan kode tinggi -> bobot besar.
    Nama yang hanya ada di first_names.all.txt -> bobot dasar 1.
    """
    weights: dict[str, int] = {}

    # sumber 1: daftar lengkap (bobot dasar)
    n = 0
    for line in _read_lines("first_names.all.txt"):
        name = clean(line.strip())
        if name:
            weights[name] = weights.get(name, 0)  # pastikan ada (dasar nanti)
            n += 1
    print(f"  + first_names.all.txt: {len(weights):,} nama unik")

    # sumber 2: firstnames.csv (popularitas per negara)
    before = len(weights)
    for i, line in enumerate(_read_lines("firstnames.csv")):
        if i == 0:
            continue  # header
        parts = line.rstrip("\n").split(";")
        if len(parts) < 3:
            continue
        name = clean(parts[0].strip())
        if not name:
            continue
        score = 0
        for cell in parts[2:]:
            cell = cell.strip()
            if not cell:
                continue
            try:
                code = int(cell)
            except ValueError:
                continue
            code = max(-8, min(2, code))
            score += 1 << (code + 8)  # 2**(code+8): -8->1 .. +2->1024
        weights[name] = weights.get(name, 0) + score
    print(f"  + firstnames.csv: +{len(weights) - before:,} nama baru, "
          f"popularitas ditambahkan")

    # bobot minimal 1 agar tiap nama tetap mungkin muncul
    for k in weights:
        if weights[k] < 1:
            weights[k] = 1
    return weights


def build_last_names() -> dict[str, int]:
    """Kumpulkan nama belakang + bobot = jumlah sensus (surnames.csv).

    Nama di luar sensus (hanya di file lain) -> bobot dasar 1.
    """
    weights: dict[str, int] = {}

    for filename in ("last_names.all.txt", "last-names.txt"):
        before = len(weights)
        for line in _read_lines(filename):
            name = clean(line.strip())
            if name:
                weights.setdefault(name, 0)
        print(f"  + {filename}: +{len(weights) - before:,} nama baru "
              f"(total {len(weights):,})")

    before = len(weights)
    for i, line in enumerate(_read_lines("surnames.csv")):
        if i == 0:
            continue  # header: name,rank,count,...
        parts = line.rstrip("\n").split(",")
        if len(parts) < 3:
            continue
        name = clean(parts[0].strip())
        if not name:
            continue
        try:
            count = int(parts[2])
        except ValueError:
            count = 0
        weights[name] = weights.get(name, 0) + count
    print(f"  + surnames.csv: +{len(weights) - before:,} nama baru, "
          f"jumlah sensus ditambahkan")

    for k in weights:
        if weights[k] < 1:
            weights[k] = 1
    return weights


def write_plain(names, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for name in sorted(names):
            fh.write(name + "\n")


def write_weighted(weights: dict[str, int], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # urutkan dari bobot terbesar agar file enak dibaca manusia
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for name, w in sorted(weights.items(), key=lambda kv: (-kv[1], kv[0])):
            fh.write(f"{name}\t{w}\n")


def main() -> None:
    print("== Nama depan ==")
    first = build_first_names()
    print("== Nama belakang ==")
    last = build_last_names()

    write_plain(first.keys(), DATA / "first_names.txt")
    write_plain(last.keys(), DATA / "last_names.txt")
    write_weighted(first, DATA / "first_names_weighted.tsv")
    write_weighted(last, DATA / "last_names_weighted.tsv")

    top_first = sorted(first.items(), key=lambda kv: -kv[1])[:10]
    top_last = sorted(last.items(), key=lambda kv: -kv[1])[:10]
    print()
    print(f"Selesai.")
    print(f"  first_names.txt : {len(first):,} nama depan unik")
    print(f"  last_names.txt  : {len(last):,} nama belakang unik")
    print(f"  kombinasi       : {len(first) * len(last):,}")
    print(f"  10 nama depan terpopuler  : "
          f"{', '.join(n for n, _ in top_first)}")
    print(f"  10 nama belakang terpopuler: "
          f"{', '.join(n for n, _ in top_last)}")


if __name__ == "__main__":
    main()
