# kcsdb-analysis-hf

2019 일본 수출규제(불화수소) 분석. **KCSDB2 릴리스 `v1.0-202603`을 입력으로 쓰는 독립 분석 저장소**다.
인프라 저장소([pilsunchoi/KCSDB2](https://github.com/pilsunchoi/KCSDB2))와 분리돼 있다 —
이 저장소는 DB를 만들지 않고, 고정된 릴리스를 소비만 한다.

## 이 저장소가 의존하는 것

- DB: KCSDB2 릴리스 `v1.0-202603` (`DB_VERSION` 파일에 명시)
- DB는 저장소에 포함하지 않는다(334MB). 부트스트랩이 릴리스에서 받는다.

## 재현 절차

```bash
# 0) 환경 (기존 conda env 재사용 가능)
conda activate kcsdb
pip install -r requirements.txt

# 1) DB 내려받기 (data/kcsdb.duckdb 로 놓임, 수 분)
python scripts/00_fetch_db.py

# 2) 추출 → DiD → 합성통제
python scripts/01_extract.py
python scripts/02_did.py
python scripts/03_synth.py
```

이미 KCSDB2 인프라 저장소가 같은 머신에 있고 그 DB를 직접 쓰려면, 1)을 건너뛰고 환경변수만 지정한다:

```powershell
# PowerShell
$env:KCSDB_PATH="C:\Work\Projects\KCSDB2\data\processed\kcsdb.duckdb"
```

## 폴더 구조

```
config.py            경로 설정 한 곳(DB_PATH, PAPER_DIR). 하드코딩 금지.
DB_VERSION           의존 릴리스 태그.
scripts/
  00_fetch_db.py     릴리스 DB 다운로드·압축해제·검증(행수 27,533,937 대조)
  01_extract.py      처치/대조/도너풀 추출 → data/paper/*.parquet
  02_did.py          2x2 + event-study DiD, clustered SE
  03_synth.py        합성통제 + permutation 추론
notebooks/           재현 노트북
paper/
  draft.md           초안(발전 대상)
  설계.md            논문 설계·구성
data/                DB·중간산출(.gitignore 처리, 저장소에 안 올라감)
```

## 처음 Git을 쓰는 경우 — 새 저장소 만들기

이 폴더는 KCSDB2와 **별개의 새 저장소**다. GitHub에서 빈 저장소를 하나 더 만든 뒤 연결한다.

1. GitHub에서 `New repository` → 이름 `kcsdb-analysis-hf`, **빈 저장소로**(README·gitignore 추가하지 말 것, 여기 이미 있음).
2. 이 폴더에서:

```bash
cd C:\Work\Projects\kcsdb-analysis-hf
git init
git add .
git commit -m "init: HF export-control analysis, depends on KCSDB2 v1.0-202603"
git branch -M main
git remote add origin https://github.com/pilsunchoi/kcsdb-analysis-hf.git
git push -u origin main
```

`.gitignore` 덕분에 DB·중간산출은 올라가지 않는다. 코드·문서·노트북만 올라간다.

## 출처·라이선스

DB 출처는 KCSDB2 릴리스 노트 참조(관세청 OpenAPI 15100475 등, 공공누리 제1유형 — 출처표시).
