# kenshinn_convertor

健診の**手書きチェック表**と**印字の検査結果票**をスキャンから読み取り、両者を統合して**健康診断個人票（Excel）**へ書き出す変換ツール。

手書きの自覚症状などを **Claude（LLM）の画像認識**で解析し、健診の用語を優先して認識する。健診には **企業 / ライト / 特定** の 3 種別があり、種別ごとに検査項目が異なる。**まずは macOS ローカルでの完成を最短で目指す**（Windows / GAS への移植は当面考えない）。

---

## Current Status

**実装済み:**
- 個人票テンプレ（`templates/企業健診プラン.xlsx`）への実測値書き込み
- BMI・年齢の算出（和暦パース込み）、例外項目の空欄＋色付け
- CLI（`run.py demo / from-json / ocr`）と最小テスト

**進行中:**
- Phase 1 の抽出側（`extract_llm.py`）: Claude で画像→値。実装済み。`ANTHROPIC_API_KEY` を設定して実データで精度検証する段階

---

## 何をするツールか（入力 → 出力）

**入力 = 2 種類の帳票**（同一患者を ID で突合）:

| | 帳票 | 記入 | 内容 |
|---|---|---|---|
| 入力① | 健診チェック表（問診票） | **手書き** | 身体計測・血圧・視力・聴力・既往歴・自覚症状・画像所見 |
| 入力② | 検査結果票（2 ページ） | **印字** | 採血・尿検査の数値 |

**処理**: ① 前処理（PDF→画像・向き補正・領域切り出し）→ ② OCR（Vision）→ ③ 項目抽出 → ④ 個人票テンプレの対応セルへ配置（BMI・年齢・判定 A〜E などは算出）→ ⑤ 読めない / 確信度の低いものを例外として仕分け

**出力**: 適切なセルに統合された Excel「健康診断個人票」

---

## Docs

| ファイル | 役割 |
|---|---|
| `README.md`（このファイル） | プロジェクト入口 + 仕様の概観 + Current Status |
| `CONTEXT.md` | このプロジェクトで使う言葉の定義（用語集） |
| `docs/spec.md` | 詳細仕様（OCR・セル配置・例外処理）と **未確定事項（一緒に決めること）** |
| `docs/development.md` | ロードマップ・開発経緯・未着手課題 |
| `CLAUDE.md` | Claude Code 向けの開発方針・deny zone・確定済み設計判断 |

---

## ディレクトリ構成

```
kenshinn_convertor/
├── README.md            # このファイル
├── CONTEXT.md           # 用語集
├── docs/
│   ├── spec.md          # 詳細仕様 + 未確定事項
│   └── development.md    # ロードマップ・経緯
├── run.py               # CLI 入口（demo / from-json / ocr）
├── configs/             # 種別ごとの「項目→セル」対応づけ（企業.json）
├── templates/           # 出力テンプレ Excel（種別ごと・git 追跡する）
│   └── 企業健診プラン.xlsx   #   「テンプレ」(書き込み先) ＋「記入例」(検証用) の 2 シート
├── src/kenshin/         # 本体（excel_writer / compute / pipeline / extract_llm / models）
├── tests/               # 最小テスト（test_basic.py）
├── samples/             # ★患者情報を含むため git 追跡しない（.gitignore 済）
│   ├── input/           #   問診票スキャン（画像 / PDF）のサンプル置き場
│   └── output/          #   期待する Excel の見本置き場
└── outputs/             # ★変換結果の出力先（git 追跡しない）
```

> `samples/` と `outputs/` は実患者の自覚症状を含みうるため `.gitignore` で除外済み。
> ここに入れたファイルはローカルのみに残り、リポジトリには入りません。

---

## 技術スタック

| 領域 | 採用 | 備考 |
|---|---|---|
| 言語 | Python 3.11+ | macOS ローカル優先（移植は当面考えない） |
| OCR/抽出 | **Claude（LLM）`claude-opus-4-8`** | 手書き×健診特化を認識の最中に効かせる。要 `ANTHROPIC_API_KEY` |
| Excel 出力 | openpyxl | 既存テンプレ Excel への書き込み |
| PDF → 画像 | pdf2image / PyMuPDF | PDF 入力時の前処理（必要になったら） |

> 患者画像を Claude API（クラウド）へ送る点は院内規程との整合を別途確認。API キーは `.gitignore` 済み・コミット禁止。

---

## Repository Rules

統括 [`AppDevelopment/CLAUDE.md`](../CLAUDE.md) を継承。

- **個人情報を絶対にコミットしない** — 問診票スキャン・期待Excel・変換結果（患者の自覚症状を含む）
- 上記は `.gitignore` で広めに除外済み（画像 / PDF / Excel 拡張子を一括除外 → 必要時のみ `git add -f`）
- GitHub リポジトリは **Private** で運用
- クラウド OCR を使う場合、認証キー（`*-credentials.json` 等）はコミットしない

---

## 使い方

```bash
pip install -r requirements.txt        # Phase 1 は openpyxl だけで動く

# サンプル値で個人票を生成（OCR 不要・動作確認）
python run.py demo
#   → outputs/企業_個人票.xlsx を生成。確信度の低い項目は空欄＋黄色で示す

# 抽出済みの値(JSON)から個人票を生成（OCR の前段を飛ばす）
python run.py from-json 値.json --type 企業 --out outputs/個人票.xlsx

# 画像から生成（Claude で抽出・要 ANTHROPIC_API_KEY・課金あり）
export ANTHROPIC_API_KEY=sk-ant-...
python run.py llm チェック表.jpg 採血1.jpg 採血2.jpg --type 企業

# テスト（API 不要）
python tests/test_basic.py
```

**現状**: 個人票への書き込み・BMI/年齢の算出・例外の色付けは動作・テスト済み（実サンプルで期待出力と全項目一致）。画像からの抽出（`extract_llm.py`）は実装済みで、`ANTHROPIC_API_KEY` を設定すれば動く。
