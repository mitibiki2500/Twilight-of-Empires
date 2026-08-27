# Twilight of Empires market update branch

このブランチは、最新版MODを基準に市場修正を管理するための作業ブランチです。

- MOD本体は最新版を維持
- ユーザー確認でニューフート以外のテーガール市場が生きていた378検証版の `map_data/` と `gfx/map/spline_network/` を採用
- New Foot (XBE) の国履歴・州所有・建築・人口・軍・従属関係・strategic region は最新版を維持
- `map_data/adjacencies.csv` のNew Foot暫定接続2本を維持
- アルティ、リイア土壌汚染基金、企業高級品、MAPI、グンマ従属、行政調整などの後期更新は最新版側を維持

## GitHub側の制限

GitHubコネクタからは `provinces.png` や `spline_network.splnet` などのバイナリを直接更新できないため、バイナリ地図統合は配布用完全版ZIP側で実施しています。ブランチ側にはテキスト変更と更新内容を記録します。

注: 接続修正のゲーム内最終確認は未実施。
