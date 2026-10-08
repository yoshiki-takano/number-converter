# 公報番号変換ツール

DPS、Shareresearch、JP-NET形式の公報番号を相互変換するStreamlitアプリです。変換結果はプレビューで確認し、CSVとしてダウンロードできます。

## 必要環境

- Python 3.10以降
- pip

## セットアップと起動

プロジェクトフォルダーでPowerShellを開き、次を実行します。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run number_converter.py
```

表示されたローカルURLをブラウザーで開きます。仮想環境を有効化できない場合は、PowerShellの実行ポリシーを確認するか、仮想環境のPythonを直接使ってください。

## 入力ファイル

| 入力形式 | 対応ファイル | 必須の列・形式 |
| --- | --- | --- |
| DPS | CSV、XLS、XLSX | `公報番号` または `Publication Number`。ヘッダーは先頭3行以内から検出します。 |
| Shareresearch | CSV、XLS、XLSX | `公報番号(抄録リンク)` と `公報種別` |
| JP-NET | `.DNO`、`.JNV`、`.AN` | 1行1件。各行は種別と番号を含む形式です。 |

CSVはUTF-8系またはCP932の文字コードで読み込みます。Excel形式の読み込みには `openpyxl` と `xlrd` を使用します。

## 変換

- DPSからは、番号の整形結果またはJP-NET形式を出力できます。
- Shareresearchからは、DPS公報番号またはJP-NET形式を出力できます。
- JP-NETからDPSを出力する場合、`.AN` はDPS出願番号、`.DNO` / `.JNV` はDPS公報番号に変換します。
- JP-NETをJP-NETとして出力するときは、入力内容をそのままCSVに出力します。

JP-NET形式への変換では、主に次の規則を適用します。

- 7桁・8桁の特許公開番号は、年数から平成（`H`）または昭和（`S`）を判定し、`H09-09XXXX` のような形式にします。
- 7桁・8桁番号の連番が `5xxxxx` の場合、種別を `T` にします。
- 10桁番号は年次と連番をハイフンで区切ります。特定の番号は種別を `T` に変換します。
- 種別 `B2` / `B1` は `B9`、`B*` は `B`、`U*` は `U` に変換します。
- `WO`番号はJP番号の接頭辞を付けずに出力します。

変換例:

| DPS番号 | JP-NET番号 |
| --- | --- |
| `JP909XXXXA` | `A  H09-09XXXX` |
| `JP2020123456A` | `A  2020-123456` |

## 出力

- 変換結果は画面に先頭50件を表示します。
- CSVはUTF-8 BOM付きでダウンロードします。
- JP-NET出力を選んだ場合、JP/WO番号を含む `.DNO` ファイルもダウンロードできます。

## 依存パッケージ

依存関係は [`requirements.txt`](requirements.txt) に定義されています。