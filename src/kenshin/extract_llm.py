"""LLM(Claude)で帳票画像から項目を抽出する。

健診問診票・検査結果票の画像を Claude（claude-opus-4-8）に渡し、健診の文脈を
理解させながら各項目を読み取る。Google Vision のような単純な文字起こしと違い、
「自覚症状の手書きは『なし／動悸／息切れ』等を優先」といった健診特化の指示を
"認識の最中" に効かせられるのが利点。

出力は run.py の from-json と同じ値 dict なので、後段（BMI/年齢算出・例外色付け・
Excel 書き込み）は一切変えずに使える。

実行に必要: 環境変数 ANTHROPIC_API_KEY、`pip install anthropic`。
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

MODEL = "claude-opus-4-8"

# 算出/導出する欄（モデルには出力させない。raw から計算する）
_DERIVED = {"BMI腹囲", "生年月日", "受診日"}
# 算出の材料として別途読ませる raw 項目
_RAW = ["身長", "体重", "腹囲", "生年月日raw", "受診日raw"]

_MEDIA = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
          ".gif": "image/gif", ".webp": "image/webp"}

SYSTEM = """\
あなたは日本の健康診断帳票を読み取る専門アシスタントです。入力画像は次の2種類:
(1) 手書きの「健康診断チェック表(問診票)」 — 身体計測・血圧・視力・聴力・既往歴・
    自覚症状・喫煙/飲酒/運動・画像検査の所見(○囲み)。
(2) 印字の「検査結果票」(複数ページ可) — 採血・尿検査の数値。基準値列と複数の採血日列を持つ。

健診特化のルール:
- 自覚症状/既往歴/治療中の病気の手書きは、健診で頻出する語を優先して解釈する
  (例: 「なし」「動悸」「息切れ」「胸痛」「めまい」「頭痛」「咳」「痰」「服薬中」)。
- 検査結果票の採血日列の選び方(重要):
  * 今回の受診日(チェック表の健診日)に属する列の値だけを使う。前年など別日付の列は使わない。
  * 同じ受診日に複数の時刻列(例 00:00 と 11:17)がある場合、項目ごとに、どちらかの列に
    値があればその値を採用する。両方の列に値があるときは時刻の早い方を採用する。
  * 受診日のどの列にも値が無い項目だけを文字列 "未実施" とする。
- 2つの値を持つ項目(MCH/MCV, 尿蛋白/尿糖, 随時血糖/HbA1c, 視力 右/左, 聴力 右/左 等)は、
  各値を個別に上記ルールで読む。片方だけ値が無ければ、その側を "未実施" とする
  (例 MCH 30.0 だけで MCV が無ければ "30.0 / 未実施")。
- 画像検査の所見は ○ で囲まれた側を採る(「異常なし」に○なら "異常所見無"、「異常あり」に
  ○ならその内容)。○が判読できれば読み取り、判読できないときだけ _uncertain に入れる。

厳守(医療データのため):
- **見えない値・読めない値を絶対に創作しない。** 読めない/自信がない項目は値を "" (空文字)
  にして、そのキーを _uncertain 配列に入れる。検査結果票の数値は特に、確信が持てなければ
  推測せず _uncertain に入れる。

書式(出力の揃え方):
- 数値は単位を付けず数字のみ(例 身長 "170.0")。
- 2値はスラッシュ区切りで値のみ。単位やラベル(Hz, dB, mg/dL, %, 血糖, HbA1c 等)は付けない
  (例 聴力右 "25 / 25"、随時血糖_HbA1c "86 / 5.8")。
- 視力は矯正の有無を全角括弧で付す(例 "右0.9 / 左1.0（矯正有）" / "（矯正無）")。
- 受診日は時刻を含めず日付のみ(例 "2026年6月25日")。
- 生年月日は元号略号＋ゼロ埋め2桁の月日をドット区切り(例 "S46.04.06"。"S46.4.6" としない)。
出力は指定された JSON スキーマに厳密に従うこと。"""

INSTRUCTION = """\
添付の健診帳票(手書きチェック表 + 検査結果票)から各項目を読み取り、JSON で返してください。
各キーに読み取った文字列を入れ、読めない/該当無しは ""。読み取りに自信が無いキーは
すべて _uncertain 配列に列挙してください。氏名は黒塗り等で読めなければ "" で構いません。"""


def _build_schema(field_keys: list[str]) -> dict:
    keys = [k for k in field_keys if k not in _DERIVED] + _RAW
    props = {k: {"type": "string"} for k in keys}
    props["_uncertain"] = {"type": "array", "items": {"type": "string"}}
    return {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": props,
            "required": list(props.keys()),
            "additionalProperties": False,
        },
    }


def _image_block(path: str | Path) -> dict:
    p = Path(path)
    media = _MEDIA.get(p.suffix.lower())
    if media is None:
        raise RuntimeError(
            f"未対応の画像形式です: {p.suffix}（jpg/png/gif/webp に変換してください。PDFは別途対応）"
        )
    data = base64.standard_b64encode(p.read_bytes()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}


def extract(check_image: str | Path, lab_images: list[str | Path], field_keys: list[str]) -> dict:
    """画像 → 値 dict（from-json と同じ形）。_uncertain のキーは needs_check 付きにする。"""
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("anthropic SDK が未インストールです。`pip install anthropic`") from e

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY を環境から読む

    content: list[dict] = [{"type": "text", "text": "【手書きチェック表】"}, _image_block(check_image)]
    for i, lab in enumerate(lab_images, 1):
        content.append({"type": "text", "text": f"【検査結果票 {i}ページ目】"})
        content.append(_image_block(lab))
    content.append({"type": "text", "text": INSTRUCTION})

    resp = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        thinking={"type": "adaptive"},  # 手書き判読は丁寧に考えさせる
        output_config={"format": _build_schema(field_keys)},
        messages=[{"role": "user", "content": content}],
    )

    text = next((b.text for b in resp.content if b.type == "text"), None)
    if text is None:
        raise RuntimeError(f"モデルから JSON 応答が得られませんでした (stop_reason={resp.stop_reason})")
    data = json.loads(text)

    # _uncertain のキーは「空欄＋色付け」対象にする（raw 項目はそのまま compute へ流す）
    uncertain = set(data.pop("_uncertain", []))
    for k in list(data.keys()):
        if k in uncertain and k not in _RAW:
            data[k] = {"value": data.get(k) or "", "needs_check": True}
    return data
