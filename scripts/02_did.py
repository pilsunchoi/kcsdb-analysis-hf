# -*- coding: utf-8 -*-
"""
hf_paper_02_did.py
DiD 추정: 2x2(일본, 처치vs대조) + event-study(사전 리드/사후 래그).

  log(import) = a + b*(Treated x Post) + item_FE + time_FE + e
  event-study: Treated x 각 상대월 더미 (기준 = 2019m6)

사후 0값(2019m8,9) → IHS 변환(log 대체) 사용. 로그 결과는 부록.
"""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from pathlib import Path

import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PAPER_DIR
OUT = PAPER_DIR
tc = pd.read_parquet(OUT / "hf_treated_control.parquet")

TREATED, CONTROL = "2811111000", "2811119000"
JAPAN = "일본"
T0 = 201907  # 처치 시점

def ihs(x):  # inverse hyperbolic sine: 0에도 정의됨
    return np.arcsinh(x)

# ---- 일본 한정 2x2 ----------------------------------------------------------
jp = tc[tc["country"] == JAPAN].copy()
jp = jp[jp["hsk10"].isin([TREATED, CONTROL])]
jp["treated"] = (jp["hsk10"] == TREATED).astype(int)
jp["post"] = (jp["ym"] >= T0).astype(int)
jp["y"] = ihs(jp["value_usd"].fillna(0))

# 처치창 한정(±24m)으로 극단 사전기간 배제
lo, hi = 201707, 202107
win = jp[(jp["ym"] >= lo) & (jp["ym"] <= hi)].copy()

m22 = smf.ols("y ~ treated*post", data=win).fit(
    cov_type="cluster", cov_kwds={"groups": win["hsk10"]})
print("=== 2x2 DiD (일본, IHS 수입액) ===")
print(m22.summary().tables[1])

# ---- event-study: 상대월 더미 ----------------------------------------------
es = jp[(jp["ym"] >= 201707) & (jp["ym"] <= 202107)].copy()
# 상대월 인덱스(연·월 → 월경과)
def to_idx(ym):
    y, m = ym // 100, ym % 100
    return y * 12 + (m - 1)
es["k"] = es["ym"].map(to_idx) - to_idx(T0)   # 0 = 처치월
# 기준월 = -1 (2019m6). 리드/래그 더미 생성
kmin, kmax = int(es["k"].min()), int(es["k"].max())
for k in range(kmin, kmax + 1):
    if k == -1:  # 기준
        continue
    es[f"d{('m' if k<0 else 'p')}{abs(k)}"] = (
        ((es["k"] == k) & (es["hsk10"] == TREATED)).astype(int))
dummies = [c for c in es.columns if c.startswith(("dm", "dp"))]
es["y"] = ihs(es["value_usd"].fillna(0))
es["treated"] = (es["hsk10"] == TREATED).astype(int)

# item + time FE = treated + C(ym)
formula = "y ~ treated + C(ym) + " + " + ".join(dummies)
mes = smf.ols(formula, data=es).fit(
    cov_type="cluster", cov_kwds={"groups": es["hsk10"]})

# event-study 계수 추출·저장
rows = []
for c in dummies:
    k = int(c[2:]) * (-1 if c.startswith("dm") else 1)
    rows.append({"k": k, "coef": mes.params[c],
                 "se": mes.bse[c],
                 "lo": mes.conf_int().loc[c, 0],
                 "hi": mes.conf_int().loc[c, 1]})
esdf = pd.DataFrame(rows).sort_values("k")
esdf.to_csv(OUT / "event_study_coefs.csv", index=False, encoding="utf-8-sig")
print("\n=== event-study 계수 (기준 k=-1) ===")
print(esdf.to_string(index=False))
print(f"\n[out] {OUT/'event_study_coefs.csv'}")

# 사전 리드 합동유의성(병행추세 검정)
leads = [c for c in dummies if c.startswith("dm")]
if leads:
    ft = mes.f_test(" = 0, ".join(leads) + " = 0")
    print(f"\n[병행추세] 사전 리드 합동 F={float(ft.fvalue):.3f}  p={float(ft.pvalue):.4f}")
print("[done] 02_did")
