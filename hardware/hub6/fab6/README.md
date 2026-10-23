# fab6

基板 A (rev C) の、JLCPCB にアップロードするファイル。`/usr/bin/python3 fab.py` が `build/fab/` に作り、ここへ写す。

- `hub6-gerbers.zip`: ガーバーとドリル (2 層、五角形の外形、結束バンド用の長穴 10 個)
- `hub6-bom.csv`: 部品表 (LCSC の部品番号つき。U1、C2、C3)
- `hub6-cpl.csv`: 部品の配置 (上面のみ)。ケーブル用の穴 (J1〜J6) と、手はんだの J7 (基板 B へのピンヘッダー) は載らない

見積もりの画面での確認は `../README.md` の「発注の前に確かめること」を参照。
