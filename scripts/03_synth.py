# -*- coding: utf-8 -*-
"""
hf_paper_03_synth.py
합성통제 + permutation 추론. 외부 SCM 패키지 없이 scipy만으로 구현.

처치단위: 2811111000 대일 수입액(월별, IHS).
도너풀:   donor_pool.parquet 의 각 HS10 대일 수입액(japan_usd).
반사실:   도너들의 가중합으로 사전기간 처치추세를 근사(가중치 w>=0, sum=1).
추론:     in-space placebo — 각 도너를 가짜 처치로 돌려 RMSPE비율 분포 → p값.
          in-time placebo — 처치시점을 2018m7로 옮겨 위약 단절 확인.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.optimize import minimize

import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PAPER_DIR
OUT = PAPER_DIR
donor = pd.read_parquet(OUT / "donor_pool.parquet")
tc = pd.read_parquet(OUT / "hf_treated_control.parquet")

TREATED = "2811111000"
JAPAN = "일본"
T0 = 201907
PRE_LO, PRE_HI = 201501, 201906   # 사전기간

def ihs(x): return np.arcsinh(np.asarray(x, float))

# ---- 월 그리드 -------------------------------------------------------------
months = sorted(donor["ym"].unique())
months = [m for m in months if m >= 201501 and m <= 202603]
pre = [m for m in months if PRE_LO <= m <= PRE_HI]
idx = {m: i for i, m in enumerate(months)}

def series_from(df, ymcol_val):
    """ym→값 dict를 월그리드 벡터로."""
    s = pd.Series(ymcol_val)
    return np.array([s.get(m, 0.0) for m in months], float)

# 처치 벡터(대일, HF)
tj = tc[(tc["hsk10"] == TREATED) & (tc["country"] == JAPAN)]
treat_map = dict(zip(tj["ym"], tj["value_usd"].fillna(0)))
Y_treat = ihs(series_from(None, treat_map))

# 도너 행렬: HS10 x 월  (대일 수입액)
donors = []
names = []
for hsk, g in donor.groupby("hsk10"):
    mp = dict(zip(g["ym"], g["japan_usd"].fillna(0)))
    vec = series_from(None, mp)
    # 사전기간 전부 0인 도너 제외(정보 없음)
    if np.sum(np.abs(vec[[idx[m] for m in pre]])) == 0:
        continue
    donors.append(ihs(vec)); names.append(hsk)
D = np.array(donors)            # (J, T)
names = np.array(names)
pre_i = [idx[m] for m in pre]

def fit_weights(y, X):
    """사전기간 RMSPE 최소화하는 단순가중(w>=0, sum=1)."""
    J = X.shape[0]
    def loss(w):
        pred = w @ X[:, pre_i]
        return np.mean((y[pre_i] - pred) ** 2)
    cons = ({"type": "eq", "fun": lambda w: w.sum() - 1},)
    bnds = [(0, 1)] * J
    w0 = np.full(J, 1 / J)
    r = minimize(loss, w0, method="SLSQP", bounds=bnds, constraints=cons,
                 options={"maxiter": 500, "ftol": 1e-10})
    return r.x

def rmspe(y, pred, sl):
    return np.sqrt(np.mean((y[sl] - pred[sl]) ** 2))

post_i = [idx[m] for m in months if m >= T0]

# ---- 처치 합성 --------------------------------------------------------------
w = fit_weights(Y_treat, D)
synth = w @ D
pre_rm = rmspe(Y_treat, synth, pre_i)
post_rm = rmspe(Y_treat, synth, post_i)
ratio_treat = post_rm / pre_rm if pre_rm > 0 else np.inf

# 가중치 상위 도너 보고
top = pd.DataFrame({"hsk10": names, "w": w}).sort_values("w", ascending=False).head(8)
print("=== 합성통제 가중(상위) ===")
print(top.to_string(index=False))
print(f"\n[HF] pre-RMSPE={pre_rm:.3f}  post-RMSPE={post_rm:.3f}  ratio={ratio_treat:.2f}")

# 처치 gap 저장
gap = pd.DataFrame({"ym": months, "actual": Y_treat, "synth": synth,
                    "gap": Y_treat - synth})
gap.to_csv(OUT / "scm_gap_hf.csv", index=False, encoding="utf-8-sig")

# ---- in-space placebo -------------------------------------------------------
ratios = []
for j in range(D.shape[0]):
    y = D[j]
    Xj = np.delete(D, j, axis=0)
    wj = fit_weights(y, Xj)
    sj = wj @ Xj
    pr = rmspe(y, sj, pre_i); po = rmspe(y, sj, post_i)
    if pr > 0:
        ratios.append(po / pr)
ratios = np.array(ratios)
# p값 = 처치 비율 이상인 위약 비율의 분율
pval = (np.sum(ratios >= ratio_treat) + 1) / (len(ratios) + 1)
print(f"[permutation] placebo n={len(ratios)}  p(RMSPE-ratio) = {pval:.4f}")

pd.DataFrame({"placebo_ratio": ratios}).to_csv(
    OUT / "scm_placebo_ratios.csv", index=False, encoding="utf-8-sig")

# ---- in-time placebo (2018m7) ----------------------------------------------
T_FAKE = 201807
pre_f = [idx[m] for m in months if 201501 <= m <= 201806]
def fit_pre(y, X, sl):
    J = X.shape[0]
    def loss(w): return np.mean((y[sl] - (w @ X[:, sl])) ** 2)
    cons = ({"type": "eq", "fun": lambda w: w.sum() - 1},)
    r = minimize(loss, np.full(J,1/J), method="SLSQP",
                 bounds=[(0,1)]*J, constraints=cons,
                 options={"maxiter":500,"ftol":1e-10})
    return r.x
wf = fit_pre(Y_treat, D, pre_f)
synth_f = wf @ D
# 가짜 처치~실제 처치 직전 구간의 gap이 0 근처면 in-time placebo 통과
mid = [idx[m] for m in months if 201807 <= m <= 201906]
print(f"[in-time placebo 2018m7] 위약구간 평균 gap = "
      f"{np.mean((Y_treat-synth_f)[mid]):.3f} (0 근처여야 함)")

print(f"\n[out] {OUT/'scm_gap_hf.csv'}, {OUT/'scm_placebo_ratios.csv'}")
print("[done] 03_synth")
