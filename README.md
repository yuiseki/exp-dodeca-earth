# exp-dodeca-earth

正十二面体の地球儀。12 の面それぞれに 1.28 インチの丸型 LCD (Waveshare 1.28inch LCD Module、GC9A01) を置き、その面から見た地球を映す。正十二面体は、面 6 枚ずつの同じお椀 2 個に分けて 3D プリントし、磁石で合わせる。お椀 1 個ぶんの LCD 6 枚を、XIAO ESP32-S3 1 枚と 74HC138 で駆動する。

## 中身

- `3d/pentagon/`: お椀と面の板の形 (版ごと)。`build.py` が STEP と STL を書く。いまの版は `v0.0.5` (同じお椀を 2 個印刷する)
- `simulate/`: 板と LCD を組み上げたときの当たり、磁石の極、ケーブルの取り回しを確かめるスクリプト
- `hardware/hub6_one/`: お椀 1 個ぶんの LCD 6 枚を駆動する基板 (1 枚、2 層)。`fab6/` が JLCPCB に出したファイル
- `hardware/hub6/`: 同じ役目の基板の、使わなかった案
- `firmware/hub6_bench/`: ブレッドボードで 6 枚を駆動するスケッチと、地球の画像を面ごとに切り出すスクリプト

## LCD モジュールの 3D 図面

`simulate/` のスクリプトは、Waveshare が配っている LCD モジュールの 3D 図面を読む。再配布の条件が書かれていないので、このリポジトリには入れていない。[Waveshare の wiki](https://www.waveshare.com/wiki/1.28inch_LCD_Module) の 3D Drawing (`1.28inch_LCD_Module_3D_Drawing.zip`) を取ってきて、`3d/display/` に展開する:

```sh
mkdir -p 3d/display && cd 3d/display
curl -LO https://files.waveshare.com/upload/4/49/1.28inch_LCD_Module_3D_Drawing.zip
unzip 1.28inch_LCD_Module_3D_Drawing.zip -d 1.28inch_LCD_Module_3D_Drawing
```

`3d/display/1.28inch_LCD_Module_3D_Drawing/1.28inch LCD Module 3D Drawing/0508.stp` ができればよい。LCD を含むメッシュ (`simulate/*/overlay.stl`、`overlay.3mf`、`dodecahedron*.3mf`) も同じ理由で入れていない。スクリプトを動かすと作られる。

## ライセンス

MIT (`LICENSE`)。
