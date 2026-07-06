# -*- coding: utf-8 -*-
r"""
config.py — 경로 설정 한 곳.
모든 스크립트는 여기서 DB_PATH, PAPER_DIR을 가져온다. 경로 하드코딩 금지.

DB_PATH 결정 순서:
  1) 환경변수 KCSDB_PATH 가 있으면 그걸 쓴다.
  2) 없으면 이 저장소의 data/kcsdb.duckdb (부트스트랩 00_fetch_db.py가 받아 놓는 위치).

KCSDB2 인프라 저장소가 같은 머신에 있고 그 DB를 직접 쓰고 싶으면:
  Windows(PowerShell):  $env:KCSDB_PATH="C:\Work\Projects\KCSDB2\data\processed\kcsdb.duckdb"
  Windows(cmd):         set KCSDB_PATH=C:\Work\Projects\KCSDB2\data\processed\kcsdb.duckdb
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PAPER_DIR = DATA / "paper"
PAPER_DIR.mkdir(parents=True, exist_ok=True)

# 의존 릴리스. DB_VERSION 파일과 일치해야 한다.
DB_VERSION = (ROOT / "DB_VERSION").read_text(encoding="utf-8").strip() \
    if (ROOT / "DB_VERSION").exists() else "v1.0-202603"

DB_PATH = Path(os.getenv("KCSDB_PATH", str(DATA / "kcsdb.duckdb")))

# DB에 기대되는 총 행수(무결성 sanity check용). 릴리스 노트 기준.
EXPECTED_ROWS = 27_533_937
