# ito (IoT操作)

家のエアコン・灯り・温湿度計を扱うスクリプト。このディレクトリで直接動かす（`/workspace/bot/workspace/ito`）。初回は `uv venv venv && uv pip install -p venv -r requirements.txt`。

- `main.py`: FastAPI サーバ（127.0.0.1:9094）。SwitchBot API でエアコン・灯り・センサーを操作する。`static/index.html` はダッシュボード。
- `switchbot.py` / `switchbot_launcher.py`: SwitchBot API クライアントと、認証情報を環境変数に読み込んで起動するランチャ。トークン類はレポジトリに置かない。
- `acctl.py <厳しめ|標準|ゆるめ>`: 5分おきに温湿度を読み、ルールに従ってエアコンに信号を送る。ログは `aclog/log.csv`。
- `acgraph.py [hours]`: ログから温湿度グラフ `aclog/graph.png` を作る。
- `acstart.sh <ルール>`: acctl.py を止めて指定ルールで起動し直す。

`venv/`、`aclog/`、`last_aircon.json` は実行時に作られるので管理しない。
