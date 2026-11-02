# SteamFrame (ハッカー)

VR ヘッドセット Steam Frame まわり (SSH での操作, 常駐サービス, マイクやアイトラッキングの調整など) を担当する bot のディレクトリ.

このディレクトリにスクリプトは置いていない. 作ったものはそれぞれ独立した GitHub リポジトリにある.

## 作ったもの

入口ページは [frame-tools](https://github.com/cympfh/frame-tools).

### 使っているもの

| リポジトリ | 動く場所 | 内容 |
|---|---|---|
| [frame-steamvr-remote](https://github.com/cympfh/frame-steamvr-remote) | Frame + Windows | Frame の SteamVR ダッシュボードのパネルから, PC の SteamVR を終了・再起動する. PC 側はトレイ常駐. 終了・再起動は 5 秒以内に 2 回押したときだけ効く. exe はリリースに添付 |
| [vrc-companion](https://github.com/cympfh/vrc-companion) | Windows + SteamVR オーバーレイ | VRChat の補助. 音声の書き起こしと Eliza の返答をオーバーレイに出す (長文はスクロール), OSC パラメータのトグルボタンなど. ログは全文をファイルに残す |
| [vrc-wrist-notifier](https://github.com/cympfh/vrc-wrist-notifier) | Windows | VRChat のログから参加・退出・招待などを拾ってオーバーレイに通知. 履歴は自前の history.jsonl に残すので, VRChat 本体のログを消しても残る |
| [frame-doctor](https://github.com/cympfh/frame-doctor) | Frame | 温度・電池・空き容量・SteamVR・ツールの状態を 1 コマンドで見る. 読むだけで何も変えない |
| [frame-shot-sync](https://github.com/cympfh/frame-shot-sync) | Windows (PowerShell) | Frame のスクリーンショットを PC の `Pictures\Steam Frame\YYYY-MM` にコピー. 手動で起動 |
| [frame-gaze-gestures](https://github.com/cympfh/frame-gaze-gestures) | Frame | 長いまばたき・ウインク・上を見る動きで VRChat の OSC やコマンドを動かす. frameeyeosc の状態を読むので, frameeyeosc をやめた今は動かない. 自動起動はオフ |
| [frame-vitals-osc](https://github.com/cympfh/frame-vitals-osc) | Frame | 電池・温度・充電状態を OSC で VRChat に送る. 入れてあるが自動起動はオフ |

### やめたもの

| リポジトリ | 理由 |
|---|---|
| [frame-care](https://github.com/cympfh/frame-care) | 休憩・電池・温度のリマインダー. 要らなくなったので Frame からアンインストール済み |

## 他の人のツール (Frame に入れて設定したもの)

自作ではないが, Frame に入れて調整したもの.

- [FrameMover](https://github.com/NotZoeyDev/FrameMover): プレイスペースの移動. OVR Advanced Settings の代わりに使っている
- frame-aux-shortcuts, frame-perf-overlay (sasaken さん作)
- 使わなくなったもの: frameeyeosc (アイトラッキング), frame-mic-tuner (マイク調整), OVR Advanced Settings. frameeyeosc と frame-mic-tuner は自動起動を止めてある (2026-11-02). アンインストールはしていない

## メモ

- Frame に入れたツールの一覧 (入れ方, 自動起動の止め方, アンインストール方法) は, Frame の `~/AGENTS.md` (英語) にまとめてある.
- Windows 用の exe は PC の WSL で `cargo build --release --target x86_64-pc-windows-gnu` でビルドしている.
- 毎朝 8 時ごろ, Steam Frame 関連のニュース (SteamVR, Frame 用 SteamOS, 使っているツールの更新など) をチャットに届けている.
