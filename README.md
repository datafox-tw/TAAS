# TAAS｜內科晨峰決策台

給臺北市政府與黑客松評審使用的決策型 dashboard：重播平日 07:00–09:30 內科 VD 車流，並比較分批上班、彈性工時、公私協力點對點接駁，以及組合方案。

## 目前完成

- 56 個內科／聯外走廊 VD、150 分鐘、8,400 筆離線代表日觀測。
- 車流點位圖、分鐘時間軸及 15 分鐘聚合 API。
- 分批上班、彈性工時、接駁、接駁優先通行與組合情境引擎。
- 成功轉搭率敏感性、班次／車隊與市府／企業／業者／乘客成本分攤。
- 單一 Docker 容器、healthcheck、資料契約與模型測試。

架構與公式請先讀 [Technical Design Document](docs/TDD.md)，資料口徑請讀 [公開資料清單](DATA_SOURCES.md)，展示與部署步驟見 [Demo Runbook](docs/DEMO_RUNBOOK.md)。

## 本機開發

需求：Python 3.10+、[uv](https://docs.astral.sh/uv/)。

```bash
uv sync
uv run pytest
uv run uvicorn taas.main:app --host 0.0.0.0 --port 8000 --reload
```

開啟 <http://127.0.0.1:8000>；API 文件位於 <http://127.0.0.1:8000/docs>。

## Docker demo

```bash
docker compose up --build -d
docker compose ps
curl --fail http://127.0.0.1:8000/api/health
uv run python scripts/smoke.py
```

停止服務：

```bash
docker compose down
```

容器只複製 `data/demo`，不會包含 `.env`、TDX 金鑰或 `data/raw`。

## 重要限制

- 現有車流是 2026-10-06 單一代表日，尚不能稱為典型平日。
- 多個 VD 加總是偵測器通過量，不是不重複車輛數。
- 轉搭率、車輛成本與優先通行效果是可調情境假設。
- 上線給評審使用前，仍需決定主機網域、TLS 與對外防火牆。
