#!/usr/bin/env python3
"""kenshin_convertor の入口。

使い方:
  python run.py demo
      組み込みのサンプル値で個人票を生成（OCR 不要・動作確認用）。

  python run.py from-json 値.json [--type 企業] [--out 出力.xlsx]
      抽出済みの値(JSON)から個人票を生成。OCR の前段を飛ばして書き込み部分を使う。

  python run.py llm チェック表.jpg 採血1.jpg 採血2.jpg [--type 企業] [--out 出力.xlsx]
      画像 → Claude(LLM)で項目抽出 → 個人票（要 ANTHROPIC_API_KEY）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from kenshin import excel_writer, pipeline  # noqa: E402

# OCR を介さず動作確認するためのサンプル値（実在の患者データではない）
DEMO_VALUES = {
    "氏名": "サンプル 太郎 (ID: 000000000)",
    "性別": "男性",
    "既往歴": "なし",
    "自覚症状": {"value": "頭痛", "needs_check": True},   # ← 要確認の例（黄色塗り）
    "身長": 170, "体重": 68, "腹囲": 80,                    # ← BMI を算出
    "生年月日raw": "S50.01.01", "受診日raw": "2026-06-25",  # ← 年齢を算出
    "最高血圧": "130", "最低血圧": "80",
    "視力": "右1.2 / 左1.2", "聴力右": "25 / 30", "聴力左": "30 / 30",
    "白血球数": "5500", "赤血球数": "480",
    "血色素量": {"value": "14.0", "confidence": 0.4},        # ← 確信度低 → 黄色塗り
    "MCH_MCV": "30.0 / 90.0",
    "GOT": "20", "GPT": "18", "γGTP": "30",
    "LDL": "110", "HDL": "60", "中性脂肪": "90",
    "随時血糖_HbA1c": "95 / 5.3",
    "胸部レントゲン": "異常所見無", "心電図": "異常所見無",
}


def load_config(kind: str) -> dict:
    return excel_writer.load_config(ROOT / "configs" / f"{kind}.json")


def report(flagged: list[tuple[str, str]], out: Path) -> None:
    print(f"生成: {out}")
    if flagged:
        print(f"要確認 {len(flagged)} 件（空欄＋黄色）:")
        for key, cell in flagged:
            print(f"  - {key} ({cell})")
    else:
        print("要確認なし")


def main() -> None:
    p = argparse.ArgumentParser(description="健診帳票 → 個人票 Excel 変換")
    sub = p.add_subparsers(dest="cmd", required=True)

    pd = sub.add_parser("demo", help="サンプル値で生成")
    pd.add_argument("--type", default="企業")
    pd.add_argument("--out", default=None)

    pj = sub.add_parser("from-json", help="抽出済み値(JSON)から生成")
    pj.add_argument("json")
    pj.add_argument("--type", default="企業")
    pj.add_argument("--out", default=None)

    po = sub.add_parser("llm", help="画像から生成（Claude で抽出・要 ANTHROPIC_API_KEY）")
    po.add_argument("check", help="チェック表の画像")
    po.add_argument("labs", nargs="+", help="検査結果票の画像（複数可）")
    po.add_argument("--type", default="企業")
    po.add_argument("--out", default=None)

    args = p.parse_args()
    config = load_config(args.type)
    out = Path(args.out) if args.out else ROOT / "outputs" / f"{args.type}_個人票.xlsx"

    if args.cmd == "demo":
        report(pipeline.run_from_values(DEMO_VALUES, config, out, base_dir=ROOT), out)
    elif args.cmd == "from-json":
        values = json.loads(Path(args.json).read_text(encoding="utf-8"))
        report(pipeline.run_from_values(values, config, out, base_dir=ROOT), out)
    elif args.cmd == "llm":
        report(pipeline.run_llm(args.check, args.labs, config, out, base_dir=ROOT), out)


if __name__ == "__main__":
    main()
