
import streamlit as st
import pandas as pd
import re
import unicodedata
from io import BytesIO, StringIO

st.set_page_config(page_title="公報番号 変換ツール", layout="wide")
st.title("公報番号 変換ツール")
st.markdown("""
DI / Shareresearch の一覧ファイルと JP-NET 番号ファイル（`.DNO`, `.JNV`, `.AN`）を読み込み、
**DI / JP-NET 形式**へ変換します。

- 必要項目
    - DI: `公報番号` または `Publication Number` を含む CSV / Excel
    - JP-NET: 1行1件の番号ファイル（`.DNO`, `.JNV`, `.AN`）
    - Shareresearch: `公報番号(抄録リンク)` と `公報種別` を含む CSV / Excel

""")

uploaded = st.file_uploader("ファイルをアップロード", type=["csv", "xlsx", "xls", "dno", "jnv", "an"])

JP_NET_EXTENSIONS = {"dno", "jnv", "an"}
TABULAR_EXTENSIONS = {"csv", "xlsx", "xls"}
SHARERESEARCH_REQUIRED_COLUMNS = ["公報番号(抄録リンク)", "公報種別"]
DI_PUBLICATION_COLUMNS = ["公報番号", "Publication Number"]
KIND_COLUMNS = ["公報種別", "Kind Code"]

patterns = [
    (r"特開平0|特表平0|特公平0|実開平0|実表平0|実公平0|特開昭|特公昭|特表昭|実開昭|実公昭|実表昭", "JP"),
    (r"特開平1|特表平1|実開平1|実表平1|実公平1", "JP1"),
    (r"特許|特表|特開|実登", "JP"),
]
paren_re = re.compile(r"\(([A-Za-z])([0-9*]?)\)")


def decode_text_file(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp932", "shift_jis", "utf-8"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def parse_jpnet_lines(text: str):
    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = re.split(r"\s+", line)
        if len(parts) < 2:
            continue
        kind = parts[0].upper()
        number = "".join(parts[1:]).strip()
        rows.append({"JP-NET種別": kind, "JP-NET番号": number, "元行": raw.rstrip("\n")})
    return pd.DataFrame(rows)


def read_tabular_file(uploaded_file, ext: str) -> pd.DataFrame:
    data = uploaded_file.getvalue()
    if ext == "csv":
        return pd.read_csv(StringIO(decode_text_file(data)), engine="python")
    return pd.read_excel(BytesIO(data))


def read_tabular_file_with_header(uploaded_file, ext: str, header_row: int) -> pd.DataFrame:
    data = uploaded_file.getvalue()
    if ext == "csv":
        return pd.read_csv(StringIO(decode_text_file(data)), engine="python", header=header_row)
    return pd.read_excel(BytesIO(data), header=header_row)


def normalize_label(value) -> str:
    if pd.isna(value):
        return ""
    return unicodedata.normalize("NFKC", str(value)).strip()


def find_header_row(uploaded_file, ext: str, candidates: list[str], max_rows: int = 3) -> int | None:
    data = uploaded_file.getvalue()
    if ext == "csv":
        probe_df = pd.read_csv(StringIO(decode_text_file(data)), engine="python", header=None, nrows=max_rows)
    else:
        probe_df = pd.read_excel(BytesIO(data), header=None, nrows=max_rows)

    normalized_candidates = {normalize_label(candidate) for candidate in candidates}
    for row_index in range(min(max_rows, len(probe_df.index))):
        row_labels = {normalize_label(value) for value in probe_df.iloc[row_index].tolist()}
        if normalized_candidates.intersection(row_labels):
            return row_index
    return None


def get_publication_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for column in candidates:
        if column in df.columns:
            return column
    return None


def get_kind_column(df: pd.DataFrame) -> str | None:
    for column in KIND_COLUMNS:
        if column in df.columns:
            return column
    return None


def has_shareresearch_columns(df: pd.DataFrame) -> bool:
    return all(column in df.columns for column in SHARERESEARCH_REQUIRED_COLUMNS)


def kind_suffix(kind: str) -> str:
    if not isinstance(kind, str):
        kind = str(kind)
    k = unicodedata.normalize("NFKC", kind).strip()
    if not k or k.lower() == "nan":
        return ""

    if k == "特許協力条約に基づいて公開された国際出願":
        return ""

    m = paren_re.search(k)
    if m:
        return m.group(1).upper() + m.group(2)

    k = k.upper().replace(" ", "")
    if re.fullmatch(r"[A-Z](?:[0-9]|\*)?", k):
        return k
    return ""


def shareresearch_to_di_value(publication_number: str, kind: str | None = None) -> str:
    if not isinstance(publication_number, str):
        publication_number = str(publication_number)

    raw = unicodedata.normalize("NFKC", publication_number).strip()
    if not raw or raw.lower() == "nan":
        return ""

    normalized = raw.upper().replace(" ", "")
    if normalized.startswith("WO"):
        normalized = normalized.replace("/", "").replace("-", "")
        if re.fullmatch(r"WO\d{8}", normalized):
            normalized = f"WO20{normalized[2:]}"
        return normalized

    suffix = kind_suffix(kind) if kind is not None else ""

    paren_match = paren_re.search(normalized)
    if paren_match:
        if not suffix:
            suffix = paren_match.group(1).upper() + paren_match.group(2)
        normalized = paren_re.sub("", normalized)

    for pat, repl in patterns:
        normalized = re.sub(pat, repl, normalized)

    normalized = normalized.replace("-", "").replace("/", "")

    if not suffix:
        tail_match = re.match(r"^(JP[A-Z0-9]+?)([A-Z](?:[0-9]|\*)?)$", normalized)
        if tail_match:
            normalized = tail_match.group(1)
            suffix = tail_match.group(2)

    return normalized + suffix


def normalize_di_value(value: str) -> str:
    if not isinstance(value, str):
        value = str(value)

    normalized = unicodedata.normalize("NFKC", value).strip().upper().replace(" ", "")
    if not normalized or normalized.lower() == "nan":
        return ""

    if normalized.startswith("WO"):
        return normalized.replace("/", "").replace("-", "")

    return normalized.replace("-", "").replace("/", "")


def jpnet_pub_to_di(kind: str, number: str) -> str:
    k = str(kind).strip().upper()
    raw_n = str(number).strip().upper().replace(" ", "")
    if not raw_n:
        return ""

    # WO公開番号はJP接頭辞・種別サフィックスを付けず、そのまま出力する。
    if raw_n.startswith("WO"):
        raw_n = raw_n.replace("/", "")  # "/"を削除
        return raw_n

    n = raw_n.replace("-", "").replace("/", "")

    # 例: H07-082290 -> H07082290 -> 07082290 -> 7082290
    if re.fullmatch(r"[A-Z]\d{2}\d+", n):
        n = n[1:]
        n = n.lstrip("0") or "0"

    suffix = k
    if k == "T":
        suffix = "A"
    elif k == "TU":
        suffix = "U"
    elif k == "B":
        suffix = "B*"
    elif k == "B9":
        suffix = "B*"
    elif k == "U9":
        suffix = "U*"
    elif k == "Y9":
        suffix = "Y*"
    elif k == "Y":
        suffix = "Y*"

    prefix = "JP0" if k in {"B9", "U9", "Y9"} else "JP"
    return f"{prefix}{n}{suffix}"


def jpnet_an_to_di(kind: str, number: str) -> str:
    # .AN は出願番号ファイル。P=特許(A)、U=実案(U)として DI公報番号に変換する。
    k = str(kind).strip().upper()
    n = str(number).strip().replace(" ", "").replace("-", "")
    if not n:
        return ""
    suffix = "A" if k == "P" else "U" if k == "U" else k
    return f"JP{n}{suffix}"


def di_to_jpnet_pub(di: str) -> str:
    s = str(di).strip().upper().replace(" ", "")
    m = re.match(r"^JP([A-Z0-9]+?)([A-Z](?:[0-9]|\*)?)$", s)
    if not m:
        return s
    num, kind = m.group(1), m.group(2)

    if kind == "B*":
        kind = "B"
    elif kind == "U*":
        kind = "U"
    elif kind == "B2":
        kind = "B9"
    elif kind == "B1":
        kind = "B9"
    elif kind == "A" and re.fullmatch(r"\d{10}", num) and num[4] == "5":
        kind = "T"

    # JP0で始まる数字の場合（B9/U9型）、先頭の0を削除する
    if num.startswith("0"):
        num = num.lstrip("0") or "0"

    # 西暦4桁+6桁なら JP-NET で YYYY-NNNNNN 形式に整形
    if re.fullmatch(r"\d{10}", num):
        num = f"{num[:4]}-{num[4:]}"
    return f"{kind:<2} {num}"


def shareresearch_to_di(df: pd.DataFrame, publication_column: str, kind_column: str | None) -> pd.DataFrame:
    if kind_column:
        di_series = df.apply(lambda row: shareresearch_to_di_value(row[publication_column], row[kind_column]), axis=1)
    else:
        di_series = df[publication_column].fillna("").map(shareresearch_to_di_value)

    result = df.copy()
    if "DI公報番号" in result.columns:
        result.drop(columns=["DI公報番号"], inplace=True)
    result.insert(0, "DI公報番号", di_series)
    return result


def shareresearch_to_jpnet(df: pd.DataFrame, publication_column: str, kind_column: str | None) -> pd.DataFrame:
    di_df = shareresearch_to_di(df, publication_column, kind_column)
    result = di_df.copy()
    if "JP-NET番号" in result.columns:
        result.drop(columns=["JP-NET番号"], inplace=True)
    result.insert(0, "JP-NET番号", result["DI公報番号"].map(di_to_jpnet_pub))
    return result


def di_table_to_di(df: pd.DataFrame, publication_column: str) -> pd.DataFrame:
    di_series = df[publication_column].fillna("").map(normalize_di_value)
    result = df.copy()
    if "DI公報番号" in result.columns:
        result.drop(columns=["DI公報番号"], inplace=True)
    result.insert(0, "DI公報番号", di_series)
    return result


def di_table_to_jpnet(df: pd.DataFrame, publication_column: str) -> pd.DataFrame:
    di_df = di_table_to_di(df, publication_column)
    result = di_df.copy()
    if "JP-NET番号" in result.columns:
        result.drop(columns=["JP-NET番号"], inplace=True)
    result.insert(0, "JP-NET番号", result["DI公報番号"].map(di_to_jpnet_pub))
    return result


def build_dno_bytes_from_jpnet(df: pd.DataFrame) -> bytes:
    if "JP-NET番号" not in df.columns:
        return b""

    work = df.copy()
    jpnet_series = work["JP-NET番号"].fillna("").astype(str).str.strip()

    if "DI公報番号" in work.columns:
        di_series = work["DI公報番号"].fillna("").astype(str).str.upper()
        mask = di_series.str.contains(r"JP|WO", regex=True)
    else:
        # DI列がない場合は JP-NET番号文字列から JP/WO を判定する。
        mask = jpnet_series.str.upper().str.contains(r"JP|WO", regex=True)

    selected = jpnet_series[mask]
    selected = selected[selected != ""]
    dno_text = "\n".join(selected.tolist())
    if dno_text:
        dno_text += "\n"
    return dno_text.encode("utf-8-sig")


def render_conversion_output(df_out: pd.DataFrame, out_name: str, success_message: str, conv_out: str):
    st.success(success_message)
    st.subheader("変換結果のプレビュー（先頭50件）")
    st.dataframe(df_out.head(50))

    csv_bytes = df_out.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="変換済みCSVをダウンロード",
        data=csv_bytes,
        file_name=out_name,
        mime="text/csv",
    )

    if conv_out == "JP-NET":
        dno_bytes = build_dno_bytes_from_jpnet(df_out)
        st.download_button(
            label="JP/WOのみ .DNO をダウンロード",
            data=dno_bytes,
            file_name="jp_wo_only.DNO",
            mime="text/plain",
        )


in_options = ["DI", "JP-NET", "Shareresearch"]
out_options = ["DI", "JP-NET"]

if "conv_in" not in st.session_state:
    st.session_state.conv_in = "JP-NET"
if "conv_out" not in st.session_state:
    st.session_state.conv_out = "DI"

if uploaded:
    ext = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ""
    if ext in JP_NET_EXTENSIONS:
        st.session_state.conv_in = "JP-NET"
        st.session_state.conv_out = "DI"
    elif ext in TABULAR_EXTENSIONS:
        probe_df = read_tabular_file(uploaded, ext)
        if has_shareresearch_columns(probe_df):
            st.session_state.conv_in = "Shareresearch"
        elif find_header_row(uploaded, ext, DI_PUBLICATION_COLUMNS) is not None:
            st.session_state.conv_in = "DI"
            st.session_state.conv_out = "JP-NET"

col1, col2 = st.columns(2)
with col1:
    conv_in = st.radio("入力形式", in_options, index=in_options.index(st.session_state.conv_in), horizontal=True)
with col2:
    conv_out = st.radio("出力形式", out_options, index=out_options.index(st.session_state.conv_out), horizontal=True)

st.session_state.conv_in = conv_in
st.session_state.conv_out = conv_out

current_file_sig = None
if uploaded:
    current_file_sig = (uploaded.name, len(uploaded.getvalue()))

convert_button = st.button("変換", use_container_width=True)

if uploaded and convert_button:
    ext = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ""

    if conv_in in {"DI", "Shareresearch"}:
        if ext not in TABULAR_EXTENSIONS:
            st.error(f"{conv_in}入力では CSV / Excel ファイルをアップロードしてください。")
            st.stop()

        df = read_tabular_file(uploaded, ext)
        if conv_in == "Shareresearch":
            if not has_shareresearch_columns(df):
                st.error("必要な列が不足しています: ['公報番号(抄録リンク)', '公報種別']")
                st.stop()

            publication_column = "公報番号(抄録リンク)"
            kind_column = "公報種別"
            if conv_out == "DI":
                df_out = shareresearch_to_di(df, publication_column, kind_column)
                out_name = "di_numbers.csv"
                success_message = "Shareresearchファイルを読み込み、DI公報番号へ変換しました。"
            else:
                df_out = shareresearch_to_jpnet(df, publication_column, kind_column)
                out_name = "jpnet_numbers.csv"
                success_message = "Shareresearchファイルを読み込み、JP-NET公報番号へ変換しました。"
        else:
            header_row = find_header_row(uploaded, ext, DI_PUBLICATION_COLUMNS)
            if header_row is None:
                st.error("必要な列が不足しています: ['公報番号', 'Publication Number']")
                st.stop()

            df = read_tabular_file_with_header(uploaded, ext, header_row)
            publication_column = get_publication_column(df, DI_PUBLICATION_COLUMNS)

            if conv_out == "DI":
                df_out = di_table_to_di(df, publication_column)
                out_name = "di_numbers.csv"
                success_message = "DIファイルを読み込み、DI公報番号を整形しました。"
            else:
                df_out = di_table_to_jpnet(df, publication_column)
                out_name = "jpnet_numbers.csv"
                success_message = "DIファイルを読み込み、JP-NET公報番号へ変換しました。"

        st.session_state.last_result = {
            "file_sig": current_file_sig,
            "conv_in": conv_in,
            "conv_out": conv_out,
            "df_out": df_out,
            "out_name": out_name,
            "success_message": success_message,
        }
        render_conversion_output(df_out, out_name, success_message, conv_out)

    elif conv_in == "JP-NET":
        if ext not in JP_NET_EXTENSIONS:
            st.error("JP-NET入力では .DNO / .JNV / .AN ファイルをアップロードしてください。")
            st.stop()

        text = decode_text_file(uploaded.getvalue())
        df_jp = parse_jpnet_lines(text)
        if df_jp.empty:
            st.error("JP-NETファイルの解析に失敗しました。行形式をご確認ください。")
            st.stop()

        df_out = df_jp.copy()
        if conv_out == "DI":
            if ext == "an":
                df_out.insert(0, "DI出願番号", df_out.apply(lambda r: jpnet_an_to_di(r["JP-NET種別"], r["JP-NET番号"]), axis=1))
            else:
                df_out.insert(0, "DI公報番号", df_out.apply(lambda r: jpnet_pub_to_di(r["JP-NET種別"], r["JP-NET番号"]), axis=1))
        else:
            st.info("JP-NET→JP-NET は入力内容をそのまま出力します。")

        out_name = "converted_jpnet.csv"
        success_message = "JP-NETファイルを読み込み、変換しました。"
        st.session_state.last_result = {
            "file_sig": current_file_sig,
            "conv_in": conv_in,
            "conv_out": conv_out,
            "df_out": df_out,
            "out_name": out_name,
            "success_message": success_message,
        }
        render_conversion_output(df_out, out_name, success_message, conv_out)
else:
    cached = st.session_state.get("last_result")
    if uploaded and cached:
        if (
            cached.get("file_sig") == current_file_sig
            and cached.get("conv_in") == conv_in
            and cached.get("conv_out") == conv_out
        ):
            render_conversion_output(
                cached["df_out"],
                cached["out_name"],
                cached["success_message"],
                cached["conv_out"],
            )
        else:
            st.info("変換ボタンを押すと結果を表示します。")
    else:
        st.info("ファイル（DI / Shareresearch の CSV / Excel、または JP-NET .DNO / .JNV / .AN）をアップロードしてください。")
