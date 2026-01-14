
import streamlit as st
import pandas as pd
import re
import unicodedata

st.set_page_config(page_title="公報番号 変換ツール", layout="wide")
st.title("SR⇒DI用 公報番号 変換ツール")
st.markdown("""
ShareresearchからDLしたCSVの **公報番号(抄録リンク)** と **公報種別** を用い、**DI公報番号** を生成します。

""")

# - 置換規則:
#   - `特開平0|特表平0|特公平0|実開平0|実表平0|実公平0|特開昭|特公昭|特表昭|実開昭|実公昭|実表昭` → `JP`
#   - `特開平1|特表平1|実開平1|実表平1|実公平1` → `JP1`
#   - `特許|特表|特開|実登` → `JP`
# - 公報番号の数字中の `-` は削除（例: `JP2009-009682` → `JP2009009682`）
# - 公報種別の括弧内記号（例: （Ａ）, （Ｂ２））を **NFKC正規化**して `(A)`, `(B2)` に変換し、英**大文字**（`A`, `B2`）で末尾に連結

uploaded = st.file_uploader("CSVファイルをアップロード", type=["csv"])

patterns = [
    (r"特開平0|特表平0|特公平0|実開平0|実表平0|実公平0|特開昭|特公昭|特表昭|実開昭|実公昭|実表昭", "JP"),
    (r"特開平1|特表平1|実開平1|実表平1|実公平1", "JP1"),
    (r"特許|特表|特開|実登", "JP"),
]
paren_re = re.compile(r"\(([A-Za-z])([0-9]?)\)")

def normalize_pubnum(s: str) -> str:
    if not isinstance(s, str):
        s = str(s)
    t = s
    for pat, repl in patterns:
        t = re.sub(pat, repl, t)
    t = t.replace(" ", "")
    t = t.replace("-", "")  # ハイフン除去
    return t

def kind_suffix(kind: str) -> str:
    if not isinstance(kind, str):
        kind = str(kind)
    k = unicodedata.normalize('NFKC', kind).strip()
    
    # 追加条件: PCTの国際公開（日本語表記）の場合はサフィックスなし
    if k == "特許協力条約に基づいて公開された国際出願":
        return ""

    m = paren_re.search(k)
    if not m:
        return ""
    return (m.group(1).upper() + m.group(2))  # 大文字

if uploaded:
    df = pd.read_csv(uploaded, engine="python")
    required_cols = ["公報番号(抄録リンク)", "公報種別"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        st.error(f"必要な列が不足しています: {missing}")
    else:
        st.success("ファイルを読み込みました。変換を実行します…")

        # DI公報番号の生成
        di_num = df["公報番号(抄録リンク)"].map(normalize_pubnum)
        suffix = df["公報種別"].map(kind_suffix)

        # 出力用データフレーム作成
        df_out = df.copy()
        # 既に列があれば削除してから先頭へ挿入（安全策）
        if "DI公報番号" in df_out.columns:
            df_out.drop(columns=["DI公報番号"], inplace=True)
        df_out.insert(0, "DI公報番号", di_num + suffix)  # 先頭（左端）に配置

        st.subheader("変換結果のプレビュー（先頭50件）")
        st.dataframe(df_out.head(50))

        # ダウンロード（列順を維持したまま）
        csv_bytes = df_out.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="変換済みCSVをダウンロード",
            data=csv_bytes,
            file_name="di_numbers.csv",
            mime="text/csv",
        )
else:
    st.info("SRからDLしたCSVをアップロードしてください。")
