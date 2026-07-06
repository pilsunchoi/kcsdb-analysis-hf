# -*- coding: utf-8 -*-
"""
hf_paper_01_extract.py
2019 일본 수출규제 논문 — 자료 추출.

원칙:
- fact 테이블은 원자료만. 파생변수(year, month, 로그, 강도 등)는 여기(DB 밖)서 만든다.
- SELECT는 read_only=True.
- 산출물: data/paper/ 아래 parquet.

출력:
  hf_treated_control.parquet : 2811111000(처치)·2811119000(대조) 월별 국가별·집계
  donor_pool.parquet         : 도너풀 후보(28/38류 화학 HS10) 월별 총수입·대일수입
"""

import duckdb
import pandas as pd
from pathlib import Path

# ---- 경로. 실제 DB 경로에 맞게 한 곳만 고친다 --------------------------------
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, PAPER_DIR
DB = str(DB_PATH)
OUT = PAPER_DIR
OUT.mkdir(parents=True, exist_ok=True)

TREATED = "2811111000"   # 반도체 제조용 불화수소
CONTROL = "2811119000"   # 기타 불화수소
JAPAN = "일본"           # 국가명 컬럼 값. 실제 스키마의 코드/명에 맞게 확인 필요.

# fact 스키마 가정: 아래 컬럼명은 실제 KCSDB2 스키마로 반드시 대조 확인.
#   hsk10, ym(YYYYMM), country(원산국명 또는 코드), trade_type(수출/수입 구분),
#   value_usd, weight_kg
# 다를 경우 SELECT의 컬럼명만 교체한다.

# ---- 스키마 자기점검 --------------------------------------------------------
con = duckdb.connect(DB, read_only=True)

tables = con.execute("SHOW TABLES").df()
print("[tables]"); print(tables.to_string(index=False))

# fact 테이블명 자동 탐색(이름에 fact 포함, total 제외)
cand = [t for t in tables["name"].tolist()
        if "fact" in t.lower() and "total" not in t.lower()]
if not cand:
    raise SystemExit("fact 테이블을 찾지 못했다. tables 출력을 붙여 다시 진단한다.")
FACT = cand[0]
print(f"[fact] {FACT}")

cols = con.execute(f"DESCRIBE {FACT}").df()
print("[columns]"); print(cols.to_string(index=False))
COLSET = set(cols["column_name"].str.lower())

# 컬럼명 후보 매핑(스키마 방언 흡수)
def pick(*names):
    for n in names:
        if n.lower() in COLSET:
            return n
    raise SystemExit(f"컬럼 없음: {names}. DESCRIBE 출력을 붙여 진단한다.")

c_hsk   = pick("hsk10", "hsk", "hs10", "item_cd")
c_ym    = pick("ym", "yyyymm", "period")
c_ctry  = pick("country", "ctry", "natcd", "country_nm", "hs_cnty")
c_type  = pick("trade_type", "type", "io_gubun", "impexp")
c_val   = pick("value_usd", "usd", "value", "amt")
c_wgt   = pick("weight_kg", "kg", "weight", "wgt")

# 수입 구분값 확인
tvals = con.execute(f"SELECT DISTINCT {c_type} AS t FROM {FACT} LIMIT 20").df()
print("[trade_type values]"); print(tvals.to_string(index=False))
# 아래 IMPORT_VAL은 위 출력 보고 실제 '수입' 표기로 고친다.
IMPORT_VAL = "수입"

# ---- 처치·대조 품목 추출 ----------------------------------------------------
q_tc = f"""
SELECT {c_hsk} AS hsk10,
       {c_ym}  AS ym,
       {c_ctry} AS country,
       SUM({c_val}) AS value_usd,
       SUM({c_wgt}) AS weight_kg
FROM {FACT}
WHERE {c_hsk} IN ('{TREATED}','{CONTROL}')
  AND {c_type} = '{IMPORT_VAL}'
GROUP BY 1,2,3
"""
tc = con.execute(q_tc).df()

# ---- 도너풀: 28류·38류 화학 HS10 (규제 미대상), 월별 총·대일 -----------------
q_donor = f"""
SELECT {c_hsk} AS hsk10,
       {c_ym}  AS ym,
       SUM({c_val}) AS total_usd,
       SUM(CASE WHEN {c_ctry} = '{JAPAN}' THEN {c_val} ELSE 0 END) AS japan_usd
FROM {FACT}
WHERE ({c_hsk} LIKE '28%' OR {c_hsk} LIKE '38%')
  AND {c_hsk} NOT IN ('{TREATED}')
  AND {c_type} = '{IMPORT_VAL}'
GROUP BY 1,2
"""
donor = con.execute(q_donor).df()
con.close()

# ---- DB 밖 파생변수 ---------------------------------------------------------
for df in (tc, donor):
    df["year"] = (df["ym"].astype(int) // 100)
    df["month"] = (df["ym"].astype(int) % 100)

tc.to_parquet(OUT / "hf_treated_control.parquet", index=False)
donor.to_parquet(OUT / "donor_pool.parquet", index=False)

print(f"[out] {OUT/'hf_treated_control.parquet'}  rows={len(tc)}")
print(f"[out] {OUT/'donor_pool.parquet'}  rows={len(donor)}  hsk={donor['hsk10'].nunique()}")
print("[done] 01_extract")
