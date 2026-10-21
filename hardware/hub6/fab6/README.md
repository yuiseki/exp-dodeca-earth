# fab6

JLCPCB にアップロードするファイル。`/usr/bin/python3 fab.py` が `build/fab/` に作り、ここへ写す。

- `hub6-gerbers.zip`: ガーバーとドリル (4 層、五角形の外形、結束バンド用の長穴 10 個)
- `hub6-bom.csv`: 部品表 (LCSC の部品番号つき。U1、C2、C3、J7、J8)
- `hub6-cpl.csv`: 部品の配置 (上面のみ)。ケーブル用の穴の列 (J1〜J6) は部品がないので載らない

見積もりの画面での確認は `../README.md` の「発注の前に確かめること」を参照。
