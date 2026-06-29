"""データ構造の定義。

OCR が読んだ各項目は「値」だけでなく「どれくらい自信があるか(confidence)」を持つ。
confidence が低い項目は個人票では空欄＋色付けにして、医師が目視で埋める
（= 見落としゼロを優先する、という合意済みの方針）。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FieldValue:
    """1 項目の読み取り結果。

    value:       書き込む文字列（None / 空文字 は「未取得」扱い）
    confidence:  0.0〜1.0。None は「確信度の概念を持たない値（手入力・算出など）」
    needs_check: 明示的に「要確認」にしたいときに True
    """
    value: str | None = None
    confidence: float | None = None
    needs_check: bool = False

    def is_uncertain(self, threshold: float) -> bool:
        if self.needs_check:
            return True
        if self.value is None or str(self.value).strip() == "":
            return True
        if self.confidence is not None and self.confidence < threshold:
            return True
        return False


# 患者 1 名分の読み取り結果。field_key -> FieldValue
@dataclass
class PatientRecord:
    fields: dict[str, FieldValue] = field(default_factory=dict)

    def set(self, key: str, value: str | None, confidence: float | None = None,
            needs_check: bool = False) -> None:
        self.fields[key] = FieldValue(value, confidence, needs_check)

    def get(self, key: str) -> FieldValue | None:
        return self.fields.get(key)
