# -*- coding: utf-8 -*-
"""
00_fetch_db.py — KCSDB2 릴리스 DB를 내려받아 data/kcsdb.duckdb 로 놓는다.

- 표준 라이브러리만 사용(urllib, gzip, hashlib). 외부 패키지 불필요.
- 검증 3단: (1) 파일 크기 (2) 압축 해제 성공 (3) DuckDB 행수 == EXPECTED_ROWS.
- SHA256 기대값이 있으면(EXPECTED_SHA256_GZ) 다운로드 .gz 해시도 대조한다.

이미 data/kcsdb.duckdb 가 있으면 재다운로드하지 않는다(--force로 강제).
KCSDB_PATH 환경변수로 외부 DB를 직접 가리키는 경우 이 스크립트는 불필요하다.
"""
import sys
import gzip
import hashlib
import shutil
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DATA, DB_VERSION, EXPECTED_ROWS  # noqa: E402

GZ_URL = (f"https://github.com/pilsunchoi/KCSDB2/releases/download/"
          f"{DB_VERSION}/kcsdb.duckdb.gz")
GZ_PATH = DATA / "kcsdb.duckdb.gz"
DB_OUT = DATA / "kcsdb.duckdb"

# 원본 .gz 의 SHA256 을 알고 있으면 여기에 넣는다(선택). 없으면 None.
EXPECTED_SHA256_GZ = None


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def download(url, dest):
    print(f"[download] {url}")
    print(f"[download] -> {dest}  (334MB, 수 분 소요)")
    with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        got = 0
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b); got += len(b)
            if total:
                pct = got * 100 // total
                print(f"\r  {got//(1<<20)}/{total//(1<<20)} MB ({pct}%)",
                      end="", flush=True)
    print()


def main():
    force = "--force" in sys.argv
    DATA.mkdir(parents=True, exist_ok=True)

    if DB_OUT.exists() and not force:
        print(f"[skip] 이미 존재: {DB_OUT}  (재다운로드하려면 --force)")
    else:
        download(GZ_URL, GZ_PATH)

        # (선택) 해시 검증
        if EXPECTED_SHA256_GZ:
            got = sha256(GZ_PATH)
            if got.lower() != EXPECTED_SHA256_GZ.lower():
                sys.exit(f"[FAIL] SHA256 불일치\n  기대 {EXPECTED_SHA256_GZ}\n  실제 {got}")
            print("[ok] SHA256 일치")
        else:
            print("[info] SHA256 기대값 미설정 — 해시 검증 생략(전송손상은 행수검증으로 잡는다)")

        print("[decompress] gz -> duckdb")
        with gzip.open(GZ_PATH, "rb") as fin, open(DB_OUT, "wb") as fout:
            shutil.copyfileobj(fin, fout, length=1 << 20)
        GZ_PATH.unlink()  # .gz 삭제(용량 절약)

    # 행수 검증(무결성 sanity)
    try:
        import duckdb
    except ImportError:
        sys.exit("[FAIL] duckdb 미설치. conda activate kcsdb 후 재실행.")

    con = duckdb.connect(str(DB_OUT), read_only=True)
    tables = con.execute("SHOW TABLES").df()["name"].tolist()
    fact = [t for t in tables if "fact" in t.lower() and "total" not in t.lower()]
    if not fact:
        con.close()
        sys.exit(f"[FAIL] fact 테이블 없음. 테이블: {tables}")
    n = con.execute(f"SELECT COUNT(*) FROM {fact[0]}").fetchone()[0]
    con.close()

    print(f"[verify] {fact[0]} 행수 = {n:,}  (기대 {EXPECTED_ROWS:,})")
    if n != EXPECTED_ROWS:
        sys.exit(f"[FAIL] 행수 불일치. DB 손상 또는 버전 상이 의심.")
    print(f"[done] DB 준비 완료: {DB_OUT}  (릴리스 {DB_VERSION})")


if __name__ == "__main__":
    main()
