# fab6

hub6_one の、JLCPCB にアップロードするファイル。`/usr/bin/python3 fab.py` が `build/fab/` に作り、ここへ写す。

- `hub6_one-gerbers.zip`: ガーバーとドリル (2 層、辺まで 26 mm の正五角形の外形、結束バンド用の長穴 10 個)
- `hub6_one-bom.csv`: 部品表 (LCSC の部品番号つき。U1 74HC138 C2674688、C2 10uF C15850、C3 100nF C14663、J7 と J8 の XIAO 用 1x7 メスのピンソケット C2832270。どれも cubic-earth の hub3 と同じ部品)
- `hub6_one-cpl.csv`: 部品の配置。U1、C2、C3 は上面、J7、J8 は下面 (XIAO を基板の下に吊るすため)

載らないもの: ケーブル用の穴 (J1〜J6、ケーブルを手ではんだ付けする)、XIAO ESP32-S3 本体 (手で挿す。XIAO 側のピンヘッダーは XIAO に付属のもの)。

発注の前に確かめること:

- 部品配置の確認画面で、U1 の向き (1 番ピンの印の位置)。SOIC-16 の JLCPCB 上の向きは、cubic-earth の hub3 で確かめた補正 (`fab.py` の `JLC_ROTATION_OFFSET`、-90 度) を使っているが、この基板では未確認
- J7、J8 は下面の挿入部品。下面の組み立てを頼める組み立ての種類 (Economic か Standard か) と、その費用。下面での向き (CPL の回転) もこの基板では未確認
- U1 (C2674688) と J7、J8 (C2832270) の在庫と値段。手元の部品の DB は 7 月の版
- 五角形の外形と、長穴 (1.3 x 2.9 mm、メッキなし) が見積もりで通るか
