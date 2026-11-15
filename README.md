# img-trim

Windows 向けの画像トリミング・画面キャプチャツールです。画像をまとめて余白調整する機能と、ページ送りしながら指定範囲を連番 PNG として保存する機能をひとつのフォルダーにまとめています。

## 機能

- 画像の上下左右を指定して一括トリミング
- サブフォルダーを含めた画像の処理
- 画面上の指定範囲をページ送りに合わせて連番キャプチャ
- キャプチャした画像をトリミング画面へ引き継ぎ
- ウィンドウ相対または画面座標でのキャプチャ範囲指定

## 動作環境

- Windows
- Python 3.10 以降
- Tkinter（通常の Windows 版 Python に付属）

## セットアップ

py -m pip install -r requirements.txt

## 起動

画像の一括トリミング: py img-trim.py

連番キャプチャ: py seq_capture.py

同梱の start_img-trim.bat と start_seq_capture.py.bat からも起動できます。

## 設定と保存先

各アプリの設定は初回起動後、このフォルダーに trim_settings.ini と seq_capture.ini として保存されます。設定ファイルには入力・出力フォルダーや画面座標が含まれるため、Git 管理対象外です。出力先は画面で選択してください。

## 構成

- img-trim.py: 一括トリミング画面
- seq_capture.py: 連番キャプチャ画面
- imgtrim_gui.py: キャプチャ画面からトリミング画面を開く連携部
- imgtrim_core/: トリミング、画面キャプチャ、ページ操作、Windows DPI 対応の内部処理
