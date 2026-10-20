# fab6

JLCPCB にアップロードするファイル (`fab.py` が `build/fab/` に作ったものの写し)。基板を変えたら `/usr/bin/python3 fab.py` を流して、ここへ写し直す。

- `hub6-gerbers.zip`: ガーバーとドリル (4 層、六角形の外形)
- `hub6-bom.csv`: 部品表 (LCSC の部品番号つき)
- `hub6-cpl.csv`: 部品の配置 (上面のみ。U1、C2、C3 が対象。J1〜J8 はスルーホールなので手はんだ)

見積もりの画面での確認は `../README.md` の「発注の前に確かめること」を参照。
