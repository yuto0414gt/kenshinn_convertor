# kenshinn_convertor

健診の **2 種類の帳票**（手書きの問診票＋印字の検査結果票）をスキャン画像から OCR で読み取り、両者を統合して **健康診断個人票（Excel）** を生成するツール。Python / macOS。

```
[手書きチェック表 画像]  ┐
                       ├─→  Claude(LLM)で項目抽出  ─→  個人票テンプレへ書き込み  ─→  個人票.xlsx
[検査結果票 画像(印字)]   ┘     ＋ 健診特化の用語補正        ＋ BMI/年齢の算出
                              ＋ 読めない値は色付け保留      ＋ 例外セルは黄色塗り
```

---

## このプロジェクトの目的（受け取り手向け）

**「Vibecoding（AIに作らせる開発）で同じものを再現できる雛形」を提供すること**が目的です。

- 元々クリニック側で Gemini / Gem / GAS を使って試作されていたが、仕様のドキュメント化が追いつかず途中で止まっていた
- そこで Kajita（外部・形成外科医）が **Claude Code で試作機を製作 → GitHub で公開**
- クリニック側がこのリポジトリを**自分たちの AI（Gemini / Claude 等）に読ませて、同じ機能の自社実装を組み上げる**

つまり、このリポジトリは「動くサンプル＋仕様書＋設計判断の記録」をひとまとめにした **引き継ぎパッケージ**です。コードをそのまま使ってもいいですし、仕様だけを参考に GAS で書き直してもらっても構いません。

> **AI に読ませる場合の優先順位**: 最初に `README.md`（このファイル）→ `CONTEXT.md`（用語）→ `docs/spec.md`（仕様詳細）→ `CLAUDE.md`（設計判断の理由）の順で読み込ませてください。

---

## Current Status

**実装済み（企業プランで動作確認済み）:**
- 手書きチェック表＋検査結果票 → 個人票 Excel への変換（end-to-end）
- Claude(LLM) による画像→項目抽出（健診用語を優先解釈）
- BMI・年齢・和暦の算出
- 確信度の低い項目は空欄＋色付けで医師確認に回す（捏造ゼロ）
- 最小テスト同梱（API 不要で動く部分）

**未着手（受け取り手の次の判断ポイント）:**
- 判定 A〜E と生活アドバイスの自動挿入（設計はあるが未実装 → [docs/development.md](docs/development.md) Phase 3）
- ライト / 特定プランへの種別拡張（[docs/development.md](docs/development.md) Phase 4）
- 複数人バッチ処理

詳細なロードマップは **[docs/development.md](docs/development.md)** にあります（Phase 0〜4 + 開発経緯ログ）。

---

## 何ができるか・できないか（運用前の理解）

**できること**
- 1 患者分の問診票＋採血票を 1 コマンドで個人票 Excel にする
- 手書きの自覚症状を健診頻出語（「なし／動悸／息切れ／胸痛／めまい」等）を優先して解釈
- スキャン時の上下回転を文脈で吸収（前処理不要）
- 「未実施」の自動判定（採血結果票で受診日列に値が無い項目）

**できないこと（仕様上）**
- **OCR は完璧ではない** → 自信が持てなかった項目は値を書き込まず、セルを**黄色く塗る**。そこは医師が目視で埋める前提
- **判定・アドバイス・総合所見は現在自動化していない** → 個人票の「判定」「生活アドバイス」「医師の総合所見」は空欄のまま出力（Phase 3 で対応予定）
- **医療データを Claude API（クラウド）へ送る** → 院内規程と整合をとった上で利用してください

---

## 必要なもの

- macOS（Linux でも動く想定だが未検証）
- Python 3.11+
- Anthropic API キー（[console.anthropic.com](https://console.anthropic.com/settings/keys) で発行・課金あり）

---

## クイックスタート

```bash
# 1. 依存をインストール
pip install -r requirements.txt

# 2. テスト（API 不要・全部緑になることを確認）
python tests/test_basic.py

# 3. サンプル値でデモ生成（API 不要・書き込み機能のみ確認）
python run.py demo
#  → outputs/企業_個人票.xlsx が生成される

# 4. 実画像から個人票を生成（要 API キー・課金あり）
export ANTHROPIC_API_KEY=sk-ant-...
python run.py llm 問診票.jpg 採血1.jpg 採血2.jpg --type 企業 --out outputs/個人票.xlsx
#  → 「要確認 N 件（空欄＋黄色）」と一緒に xlsx が出力される
```

---

## ディレクトリ構成

```
kenshinn_convertor/
├── README.md                  # このファイル（プロジェクト入口）
├── CONTEXT.md                 # 用語集（混同しやすい言葉の定義）
├── CLAUDE.md                  # Claude Code 向け開発方針・確定判断
├── docs/
│   ├── spec.md                # 詳細仕様（変換ワークフロー・セル対応・判定方針）
│   └── development.md         # Phase ロードマップ・開発経緯ログ
├── run.py                     # CLI 入口（demo / from-json / llm）
├── configs/
│   └── 企業.json              # 種別ごとの「項目 → 個人票のセル位置」対応表
├── templates/
│   └── 企業健診プラン.xlsx     # 個人票テンプレ（書き込み先＋記入例の2シート）
├── src/kenshin/               # 本体ソース
│   ├── extract_llm.py         #   画像→値の抽出（Claude）
│   ├── excel_writer.py        #   テンプレへ書き込み・例外色付け
│   ├── compute.py             #   BMI・年齢・和暦パース
│   ├── pipeline.py            #   全体の統合
│   └── models.py              #   データ構造
├── tests/test_basic.py        # 最小テスト
├── samples/   (gitignore)     # 実患者画像を置く場所（リポジトリには入らない）
└── outputs/   (gitignore)     # 変換結果の出力先
```

---

## 技術スタック

| 領域 | 採用 | 理由 |
|---|---|---|
| 言語 | Python 3.11+ | macOS ローカル優先 |
| 画像 → 値の抽出 | **Claude（LLM）`claude-opus-4-8`** | 手書き×健診特化を「認識の最中」に効かせられる。Vision の文字起こし＋辞書補正より素直 |
| Excel 出力 | openpyxl | 既存テンプレへの書き込み（体裁を壊さない） |

> **GAS への移植について**: 本実装は Python ですが、設計（特に「項目→セル」対応表の外出し・例外の色付け・LLM への構造化出力指示）は GAS でも素直に再現できる構造にしています。詳細は [docs/spec.md](docs/spec.md) の「設計メモ」を参照してください。

---

## ドキュメントの読み方

| 知りたいこと | 読むファイル |
|---|---|
| プロジェクトの目的・現状・使い方 | このファイル（README） |
| プロジェクトで使う言葉の定義 | [CONTEXT.md](CONTEXT.md) |
| 変換の詳細仕様・セル対応・判定方針 | [docs/spec.md](docs/spec.md) |
| **今後のロードマップ・開発経緯** | [docs/development.md](docs/development.md) |
| 「なぜそう作ったか」「触ってはいけないもの」 | [CLAUDE.md](CLAUDE.md) |

---

## プライバシー

- 問診票・検査結果票・生成 Excel・認証情報は **`.gitignore` で全除外**（リポジトリには絶対に入れない設計）
- テンプレと記入例は**合成データ**（架空患者「サンプル太郎」）
- 詳細は [CLAUDE.md](CLAUDE.md) の「Deny zone」セクション

---

## ライセンス・連絡先

開発・公開: Kajita（個人）。ご質問・改善提案は GitHub Issues へ。
