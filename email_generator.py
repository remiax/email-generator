#!/usr/bin/env python3
"""Generator email realistis (mirip manusia) untuk domain Microsoft.

Domain default: hotmail.com, outlook.com, live.com, msn.com

Desain:
    - FORMAT selalu valid menurut aturan akun Microsoft (0% invalid format).
    - REALISTIS / "human": nama diambil berbobot frekuensi (nama umum seperti
      John/Maria/Smith jauh lebih sering muncul daripada nama langka), pola
      username meniru kebiasaan asli, domain dibagi dengan proporsi realistis.
    - SKALA: mampu menghasilkan miliaran alamat (streaming + batch, hemat memori).

Catatan: "valid format" != "kotak surat benar-benar ada". Keberadaan kotak
surat hanya bisa dipastikan lewat verifikasi (SMTP/API), bukan dari generator.

Contoh:
    python email_generator.py 20
    python email_generator.py 1000000 -o emails.txt
    python email_generator.py 5000000000 -o miliar.txt          # 5 miliar
    python email_generator.py 100 --domains outlook.com,live.com
    python email_generator.py 50 --uniform        # acak seragam (lebih beragam)
    python email_generator.py --self-test
"""

from __future__ import annotations

import argparse
import itertools
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

DEFAULT_DOMAINS = ["hotmail.com", "outlook.com", "live.com", "msn.com"]
# Proporsi realistis pemakaian domain (perkiraan; bisa diubah).
DEFAULT_DOMAIN_WEIGHTS = {
    "hotmail.com": 42,
    "outlook.com": 34,
    "live.com": 16,
    "msn.com": 8,
}

# Aturan local-part (sebelum '@') akun Microsoft:
#   1..64 karakter, diawali huruf, diakhiri huruf/angka,
#   hanya [a-z0-9._-], tanpa pemisah berurutan / di awal / di akhir.
VALID_LOCAL_RE = re.compile(r"^[a-z][a-z0-9]*([._-][a-z0-9]+)*$")


# ----------------------------------------------------------------------------
# Pemuatan data (berbobot bila tersedia)
# ----------------------------------------------------------------------------
def load_pool(tsv_path: Path, txt_path: Path, uniform: bool):
    """Kembalikan (names, cum_weights).

    cum_weights = None berarti seragam. Memakai file .tsv berbobot bila ada
    dan mode bukan --uniform; selain itu pakai .txt biasa (seragam).
    """
    if not uniform and tsv_path.exists():
        names: list[str] = []
        weights: list[int] = []
        with tsv_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line:
                    continue
                name, _, w = line.partition("\t")
                if not name:
                    continue
                try:
                    weights.append(int(w))
                except ValueError:
                    weights.append(1)
                names.append(name)
        if names:
            return names, list(itertools.accumulate(weights))

    # fallback: daftar biasa, seragam
    if not txt_path.exists():
        sys.exit(
            f"File tidak ditemukan: {txt_path}\nJalankan dulu: python build_names.py"
        )
    with txt_path.open("r", encoding="utf-8") as fh:
        names = [ln.strip() for ln in fh if ln.strip()]
    if not names:
        sys.exit(f"File kosong: {txt_path}")
    return names, None


# ----------------------------------------------------------------------------
# Angka & pola username (realistis)
# ----------------------------------------------------------------------------
def make_number(rnd: random.Random) -> str:
    """Akhiran angka bergaya manusia."""
    style = rnd.random()
    if style < 0.40:
        return str(rnd.randint(1960, 2008))       # tahun lahir (paling umum)
    if style < 0.72:
        return str(rnd.randint(1, 99))            # angka kecil 1..99
    if style < 0.86:
        return f"{rnd.randint(0, 99):02d}"        # dua digit 00..99
    return str(rnd.randint(100, 999))             # tiga digit (lebih jarang)


# Pola + bobot meniru kebiasaan username asli (gabungan dengan/ tanpa angka).
_PATTERNS: list[tuple[int, str]] = [
    (16, "first.last"),    # john.smith
    (12, "firstlast"),     # johnsmith
    (16, "first.last#"),   # john.smith88
    (12, "firstlast#"),    # johnsmith88
    (8,  "first#"),        # john1990
    (8,  "flast"),         # jsmith
    (6,  "flast#"),        # jsmith88
    (5,  "f.last"),        # j.smith
    (5,  "first_last"),    # john_smith
    (4,  "firstl#"),       # johns88 (depan + inisial belakang + angka)
    (3,  "first.last.#"),  # john.smith.7 (jarang)
]
_PATTERN_KEYS = [p for _, p in _PATTERNS]
_PATTERN_CUM = list(itertools.accumulate(w for w, _ in _PATTERNS))


def build_local(f: str, l: str, pat: str, rnd: random.Random) -> str:
    if pat == "first.last":
        return f + "." + l
    if pat == "firstlast":
        return f + l
    if pat == "first.last#":
        return f + "." + l + make_number(rnd)
    if pat == "firstlast#":
        return f + l + make_number(rnd)
    if pat == "first#":
        return f + make_number(rnd)
    if pat == "flast":
        return f[0] + l
    if pat == "flast#":
        return f[0] + l + make_number(rnd)
    if pat == "f.last":
        return f[0] + "." + l
    if pat == "first_last":
        return f + "_" + l
    if pat == "firstl#":
        return f + l[0] + make_number(rnd)
    if pat == "first.last.#":
        return f + "." + l + "." + make_number(rnd)
    return f + "." + l


# ----------------------------------------------------------------------------
# Generator utama (batch + streaming)
# ----------------------------------------------------------------------------
def generate(
    count: int,
    domains: list[str],
    domain_cum: list[int] | None,
    out,
    rnd: random.Random,
    min_len: int,
    max_len: int,
    dedupe: bool,
    uniform: bool,
    progress_every: int,
) -> int:
    first, first_cum = load_pool(
        DATA / "first_names_weighted.tsv", DATA / "first_names.txt", uniform
    )
    last, last_cum = load_pool(
        DATA / "last_names_weighted.tsv", DATA / "last_names.txt", uniform
    )

    seen: set[str] | None = set() if dedupe else None
    BATCH = 50_000
    written = 0
    next_mark = progress_every
    start = time.time()
    attempts = 0
    attempt_cap = count * 25 + 10_000

    choices = rnd.choices  # lokal -> sedikit lebih cepat

    while written < count and attempts < attempt_cap:
        need = min(BATCH, count - written)
        # ambil sampel sekaligus (jauh lebih cepat daripada per-item);
        # sedikit lebih banyak untuk menutup yang tersaring panjang/duplikat.
        k = need + (need // 3) + 16
        fs = choices(first, cum_weights=first_cum, k=k)
        ls = choices(last, cum_weights=last_cum, k=k)
        ps = choices(_PATTERN_KEYS, cum_weights=_PATTERN_CUM, k=k)
        ds = choices(domains, cum_weights=domain_cum, k=k)

        lines: list[str] = []
        for i in range(k):
            attempts += 1
            local = build_local(fs[i], ls[i], ps[i], rnd)
            ll = len(local)
            if ll < min_len or ll > max_len:
                continue
            email = local + "@" + ds[i]
            if seen is not None:
                if email in seen:
                    continue
                seen.add(email)
            lines.append(email)
            if len(lines) >= need:
                break

        if lines:
            out.write("\n".join(lines) + "\n")
            written += len(lines)

        if progress_every and written >= next_mark:
            rate = written / max(time.time() - start, 1e-9)
            print(f"  {written:,} email ({rate:,.0f}/dtk)", file=sys.stderr)
            while next_mark <= written:
                next_mark += progress_every

        if not lines and attempts >= attempt_cap:
            break

    if written < count:
        print(
            f"Peringatan: hanya {written:,}/{count:,} dihasilkan "
            f"(ruang unik habis untuk parameter ini).",
            file=sys.stderr,
        )
    return written


# ----------------------------------------------------------------------------
# Self-test validitas format
# ----------------------------------------------------------------------------
def self_test(rnd: random.Random) -> None:
    first, first_cum = load_pool(
        DATA / "first_names_weighted.tsv", DATA / "first_names.txt", False
    )
    last, last_cum = load_pool(
        DATA / "last_names_weighted.tsv", DATA / "last_names.txt", False
    )
    sample = 300_000
    fs = rnd.choices(first, cum_weights=first_cum, k=sample)
    ls = rnd.choices(last, cum_weights=last_cum, k=sample)
    ps = rnd.choices(_PATTERN_KEYS, cum_weights=_PATTERN_CUM, k=sample)
    bad = 0
    for i in range(sample):
        local = build_local(fs[i], ls[i], ps[i], rnd)
        if not VALID_LOCAL_RE.match(local) or not (1 <= len(local) <= 64):
            bad += 1
            if bad <= 5:
                print(f"  INVALID: {local}", file=sys.stderr)
    pct = 100.0 * (sample - bad) / sample
    print(f"Self-test: {sample:,} sampel, valid format = {pct:.4f}% "
          f"({bad} invalid)")
    if bad == 0:
        print("OK: 100% local-part valid menurut aturan Microsoft.")


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def build_domain_weights(domains: list[str], uniform: bool) -> list[int] | None:
    if uniform:
        return None
    return [DEFAULT_DOMAIN_WEIGHTS.get(d, 10) for d in domains]


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description="Generator email Microsoft realistis (hotmail/outlook/live/msn).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("count", nargs="?", type=int, default=1000,
                   help="jumlah email yang dihasilkan")
    p.add_argument("-o", "--output", default=None,
                   help="file keluaran (default: layar/stdout)")
    p.add_argument("--domains", default=",".join(DEFAULT_DOMAINS),
                   help="daftar domain dipisah koma")
    p.add_argument("--seed", type=int, default=None,
                   help="seed acak agar hasil bisa diulang")
    p.add_argument("--min-len", type=int, default=6,
                   help="panjang minimum local-part")
    p.add_argument("--max-len", type=int, default=30,
                   help="panjang maksimum local-part")
    p.add_argument("--uniform", action="store_true",
                   help="sampling seragam (lebih beragam, kurang realistis)")
    p.add_argument("--dedupe", action="store_true",
                   help="jamin unik (pakai memori; hanya untuk jumlah wajar)")
    p.add_argument("--progress-every", type=int, default=1_000_000,
                   help="tampilkan progres tiap N email (0 = mati)")
    p.add_argument("--self-test", action="store_true",
                   help="uji validitas format lalu keluar")
    args = p.parse_args(argv)

    if args.count < 0:
        sys.exit("count tidak boleh negatif.")
    if args.min_len < 1 or args.max_len < args.min_len:
        sys.exit("rentang panjang tidak valid (--min-len/--max-len).")

    rnd = random.Random(args.seed)

    if args.self_test:
        self_test(rnd)
        return

    domains = [d.strip().lower() for d in args.domains.split(",") if d.strip()]
    if not domains:
        sys.exit("Tidak ada domain valid.")
    domain_cum = None
    dw = build_domain_weights(domains, args.uniform)
    if dw is not None:
        domain_cum = list(itertools.accumulate(dw))

    if args.output:
        out = open(args.output, "w", encoding="utf-8", newline="\n")
    else:
        out = sys.stdout

    start = time.time()
    try:
        written = generate(
            count=args.count,
            domains=domains,
            domain_cum=domain_cum,
            out=out,
            rnd=rnd,
            min_len=args.min_len,
            max_len=args.max_len,
            dedupe=args.dedupe,
            uniform=args.uniform,
            progress_every=args.progress_every,
        )
    finally:
        if out is not sys.stdout:
            out.close()

    if args.output:
        dur = time.time() - start
        print(f"Selesai: {written:,} email -> {args.output} ({dur:.1f} dtk)",
              file=sys.stderr)


if __name__ == "__main__":
    main()
