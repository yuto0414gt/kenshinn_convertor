"""算出系の項目（BMI・年齢）と和暦パース。

個人票には手書き/印字をそのまま転記するだけでなく、計算で求める欄がある:
- BMI       … 身長と体重から
- 年齢      … 生年月日と受診日から
帳票そのものには書かれていないので、ここで計算して埋める。
"""
from __future__ import annotations

import re
from datetime import date

# 和暦の元号 -> （西暦 = 元号年 + offset）。例: 昭和46年 = 1925 + 46 = 1971年
_WAREKI_OFFSET = {
    "M": 1867, "明治": 1867,
    "T": 1911, "大正": 1911,
    "S": 1925, "昭和": 1925,
    "H": 1988, "平成": 1988,
    "R": 2018, "令和": 2018,
}


def parse_wareki(s: str) -> date | None:
    """'S46.04.06' / '昭和46年4月6日' / '2026-06-25' などを date へ。失敗時 None。"""
    if not s:
        return None
    s = s.strip()

    # 西暦 (YYYY.MM.DD / YYYY-MM-DD / YYYY/MM/DD)
    m = re.match(r"^(\d{4})[.\-/年](\d{1,2})[.\-/月](\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        return _safe_date(y, mo, d)

    # 和暦 (アルファベット 1 文字 or 元号名)
    m = re.match(r"^([MTSHR]|明治|大正|昭和|平成|令和)\s*0*(\d{1,2})[.\-/年]0*(\d{1,2})[.\-/月]0*(\d{1,2})", s)
    if m:
        era, yy, mo, d = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        return _safe_date(_WAREKI_OFFSET[era] + yy, mo, d)
    return None


def _safe_date(y: int, mo: int, d: int) -> date | None:
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def age_at(birth: str, on: str) -> int | None:
    """生年月日 birth 時点の、受診日 on における満年齢。"""
    b, o = parse_wareki(birth), parse_wareki(on)
    if not b or not o:
        return None
    return o.year - b.year - ((o.month, o.day) < (b.month, b.day))


def bmi(height_cm: float, weight_kg: float) -> float | None:
    """BMI = 体重kg / (身長m)^2。小数第1位で四捨五入。"""
    if not height_cm or height_cm <= 0:
        return None
    m = height_cm / 100.0
    return round(weight_kg / (m * m), 1)


def fmt_birth_with_age(birth: str, exam: str) -> str:
    """'S46.04.06' + 受診日 -> 'S46.04.06 (55歳)'。年齢が出せなければ原文のまま。"""
    a = age_at(birth, exam)
    return f"{birth} ({a}歳)" if a is not None else birth
