"""パイプラインの統合。

入口は 2 つ:
  run_from_values() … 抽出済みの値(dict/JSON)から個人票を生成（Phase 1 で今すぐ動く）
  run_ocr()         … 画像 → 前処理 → Vision OCR → 抽出 → 個人票（要 認証・実画像）
"""
from __future__ import annotations

from pathlib import Path

from . import compute, excel_writer
from .models import PatientRecord


def record_from_values(values: dict) -> PatientRecord:
    """{field_key: 値 もしくは {"value":.., "confidence":.., "needs_check":..}} を Record へ。

    特別キー(任意): 身長/体重/腹囲/生年月日raw/受診日 を渡すと BMI・年齢を算出して
    『BMI腹囲』『生年月日』欄を組み立てる。
    """
    rec = PatientRecord()
    for key, v in values.items():
        if key in {"身長", "体重", "腹囲", "生年月日raw", "受診日raw"}:
            continue  # 算出の材料。下でまとめて処理
        if isinstance(v, dict):
            rec.set(key, v.get("value"), v.get("confidence"), v.get("needs_check", False))
        else:
            rec.set(key, v)

    # BMI/腹囲 の組み立て
    h, w, wc = _to_float(values.get("身長")), _to_float(values.get("体重")), values.get("腹囲")
    if h is not None and w is not None:
        b = compute.bmi(h, w)
        if b is not None:
            waist = "" if wc in (None, "") else f" / {wc}"
            rec.set("BMI腹囲", f"{b}{waist}")
        rec.set("身長体重", f"{values.get('身長')} / {values.get('体重')}")

    # 生年月日(+年齢)
    birth, exam = values.get("生年月日raw"), values.get("受診日raw")
    if birth and exam:
        rec.set("生年月日", compute.fmt_birth_with_age(birth, exam))
        rec.set("受診日", exam)
    return rec


def _to_float(v) -> float | None:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def run_from_values(values: dict, config: dict, out_path: str | Path,
                    base_dir: str | Path = ".", conf_threshold: float = 0.6):
    rec = record_from_values(values)
    flagged = excel_writer.write(rec, config, out_path, base_dir, conf_threshold)
    return flagged


def run_llm(check_image: str | Path, lab_images: list[str | Path], config: dict,
            out_path: str | Path, base_dir: str | Path = "."):
    """画像 → 個人票。Claude(LLM)で項目抽出 → 既存の書き込み経路へ。要 ANTHROPIC_API_KEY。"""
    from . import extract_llm

    values = extract_llm.extract(check_image, lab_images, list(config["fields"].keys()))
    return run_from_values(values, config, out_path, base_dir)
