# TAAS 兩日黑客松可行性與技術規劃

評估日期：2026-10-13（Asia/Taipei）

## 1. 結論

這個題目適合做成兩日黑客松作品，但 MVP 必須縮成「一條示範走廊、一個內科目的地聚落、三個政策情境、可調假設」。

兩日內可完成且有說服力的成果：

1. 用固定日期的 VD 快照重播 07:00–09:30 車流，顯示流量、速度、資料品質與來源。
2. 以一條路線（建議「公館／科技大樓一帶 → 瑞光路公司聚落」）示範班距、車數、載客率與成本。
3. 比較「無接駁、一般接駁、接駁優先通行」三種情境。
4. 讓使用者調整需求、轉搭意願、票價、保證座位、行車時間與班距，顯示敏感度區間。
5. 清楚區分觀測資料、衍生資料與情境假設。

兩日內不應承諾：

- 還原內科員工的真實居住地或個人通勤選擇。
- 建立經校準、可做政策預測的交通方式選擇模型。
- 模擬全臺北路網的壅塞傳播或公車專用道外部成本。
- 求出全域最佳的路線與車隊排班。

因此，產品定位應是「透明的情境設計器」，不是「已驗證的交通政策預測器」。

## 2. 資料來源實測

以下結果是在目前開發環境實際發出 HTTP 請求所得，不只是閱讀資料集頁面。

| 資料 | 可直接下載 | 金鑰 | 實測結果 | MVP 用法 |
|---|---|---|---|---|
| [臺北市 VD 靜態 XML](https://tcgbusfs.blob.core.windows.net/blobtisv/VD.xml) | 是 | 不需要 | HTTP 200；約 722 KB；檔內更新日為 2026-10-13 | VD 位置、道路、方向、LinkID |
| [臺北市舊版 VD 動態 XML](https://tcgbusfs.blob.core.windows.net/blobtisv/GetVDDATA.xml) | 技術上可以 | 不需要 | HTTP 200；約 503 KB，但最後更新與檔內資料時間停在 2024-11-14 | 不可當即時來源；最多作格式參考或明確標示的舊快照 |
| [TDX 路況資訊 API](https://tdx.transportdata.tw/api-service/swagger/basic/7f07d940-91a4-495d-9465-1c9df89d709c) | 可以 | 需要 | 未帶金鑰為 HTTP 401；使用 `.env` 憑證後靜態／即時 API 均為 HTTP 200 | 正式的臺北 VD 靜態／即時來源；賽前累積快照 |
| TDX 歷史路況 API | 可以 | 需要 | 已成功下載 2026-10-06 臺北市 VD 歷史資料，共 934,562 筆、650 個 VD，壓縮後約 96.5 MB | 直接建立代表日，不必等待自行累積；再補抓 5–10 個工作日形成典型值 |
| [data.gov.tw 縣市即時路況資料集 166031](https://data.gov.tw/dataset/166031) | 否 | — | 資料集已下架，只保留歷史頁面 | PRD 應改連到 TDX 路況資訊 API，不再依賴此頁下載 |
| [高速公路局 VD 一分鐘動態 XML](https://tisvcloud.freeway.gov.tw/history/motc20/VDLive.xml) | 是 | 不需要 | HTTP 200；約 5.6 MB；每分鐘更新 | 只有路線會用到國道時才納入；內科市區 MVP 可先排除 |
| [臺北捷運分時 OD 索引](https://data.taipei/dataset/detail?id=63f31c7e-7fc3-418b-bd82-b95158755b4d) | 是 | 不需要 | 索引 CSV 約 25 KB，列出 2017-01 至 2026-08 月檔 | 找到指定月份檔案 |
| 捷運 2026-08 月 OD CSV | 是 | 不需要 | HTTP 200；約 312 MB；欄位為日期、時段、進站、出站、人次 | 只串流擷取文湖線、07–10 時與指定站，不把整檔載入前端 |

TDX 建議使用的路徑為：

```text
GET /api/basic/v2/Road/Traffic/VD/City/Taipei
GET /api/basic/v2/Road/Traffic/Live/VD/City/Taipei
```

金鑰只放在 `.env` 或 CI secret，不可提交到 Git。賽前用排程每五分鐘抓一次 VDLive；比賽展示一律讀本地快照，線上 API 只作「更新資料」按鈕的可選功能。

### 下載能力判斷

目前環境可直接下載上述無金鑰檔案，也可在提供 TDX Client ID／Client Secret 後呼叫 TDX。實際下載時應加入逾時、重試、更新時間檢查與原始檔留存，不能只因 HTTP 200 就認定資料新鮮。

2026-10-13 已用 `TAAS/.env` 完成實測並保存第一組快照到 `data/raw/tdx/`：靜態資料 641 個 VD、即時資料 647 個 VD，其中 638 個 ID 可直接對接；即時資料的 `DataCollectTime` 為 17:02。狀態分布為正常 636、其餘狀態 11。原始資料目錄已由 `.gitignore` 排除。

原 PRD 所寫「歷史 15 分鐘 VD 序列需自行累積」已不再成立。TDX 歷史服務可用日期參數下載 2021-07 起至前一日的 JSONL／CSV，單次最多七天；本環境已用現有金鑰完成一天的完整下載。仍建議展示讀本地快照，避免現場受到 API 限流影響。

另已下載最新官方園區調查。資料標準日 2024-12-31 的大內湖科技園區共有 7,462 個場所、228,905 名場所從業員工。這是需求上限與量級檢查，不是每日晨尖峰通勤人次。完整檔案、來源與限制見 `DATA_SOURCES.md`。

## 3. MVP 的資料邊界

### 3.1 觀測資料

- `vd_station`：VD ID、LinkID、經緯度、道路名、方向、車道數。
- `vd_observation_5m`：時間、VD、車道、車種、流量、平均速度、佔有率、狀態。
- `metro_od_hourly`：日期、時段、進站、出站、人次；只作區域需求的旁證，不能當作內科員工 OD。

### 3.2 情境假設

- 各出發區域的潛在員工數。
- 現況汽車、機車、大眾運輸占比。
- 平均乘載率。
- 各運具全程時間、費用、步行、候車、轉乘與可靠度。
- 保證座位的偏好加分。
- 接駁車單班固定成本、每公里成本、容量。
- 優先通行情境的接駁時間節省，以及其他道路使用者的影響區間。

### 3.3 衍生資料

- 15 分鐘流量：五分鐘流量加總。
- 15 分鐘速度：以有效車流量加權平均；無車流時保留缺值，不補成 0 km/h。
- 壅塞指標：`1 - observed_speed / reference_speed`，限制在 0–1；`reference_speed` 必須標示來源或為情境假設。
- 自駕減量：`轉搭接駁的原自駕人數 / 平均乘載率`。
- 道路淨車輛變化：`移除的小客車數 - 新增的接駁班次數`。

這個淨車輛變化只能稱為「入口走廊的等效車輛變化」，不能直接換算成整體路網速度提升。

## 4. 最小資料模型

MVP 使用 Parquet 作交換格式、DuckDB 作查詢，不需要 PostgreSQL。

| 表／檔案 | 主鍵 | 重要欄位 |
|---|---|---|
| `dim_vd.parquet` | `vd_id, link_id` | `road_name, direction, lon, lat, lane_count, source_updated_at` |
| `fact_vd_5m.parquet` | `observed_at, vd_id, lane_id, vehicle_type` | `volume, speed_kph, occupancy_pct, status, source` |
| `fact_vd_15m.parquet` | `bucket_at, vd_id` | `volume_total, speed_weighted, occupancy_mean, missing_ratio, quality_flag` |
| `dim_zone.csv` | `zone_id` | `name, role, lon, lat, walk_minutes` |
| `route_option.geojson` | `route_id` | `origin_zone, destination_zone, geometry, distance_km, base_minutes` |
| `demand_segment.csv` | `segment_id` | `origin_zone, persons, baseline_mode, current_minutes, current_cost` |
| `scenario.yaml` | `scenario_id` | 車型、容量、班距、票價、補助、座位、優先通行、偏好參數 |
| `scenario_result.parquet` | `scenario_id, route_id, departure_at` | `riders, switched_from_car, load_factor, cost, travel_minutes` |

每筆顯示結果都應能追到：

```text
value_type = observed | derived | assumed
source_id
source_updated_at
calculation_version
```

## 5. 模型設計

### 5.1 轉搭意願

使用透明、可調參數的二元 Logit 或 sigmoid，不在沒有調查資料時宣稱已校準：

```text
utility_delta =
    beta_time * (shuttle_minutes - current_minutes)
  + beta_cost * (shuttle_cost - current_cost)
  + beta_walk * walk_minutes
  + beta_wait * wait_minutes
  + beta_transfer * transfer_count
  + seat_bonus * guaranteed_seat
  + reliability_bonus * reliability_gain

p_switch = sigmoid(intercept + utility_delta)
```

介面顯示低／中／高三組係數或轉搭率，輸出區間而非單點預測。

### 5.2 班次與車數

兩日 MVP 不需要 OR-Tools。對每個候選班距：

1. 將預估乘客分配到最接近的發車時間。
2. `班次需求 = ceil(該時段乘客 / 座位數)`。
3. 以單程時間、回送時間和緩衝時間計算同時在途車數。
4. 淘汰載客率過低、滿載溢出或超過車隊上限的方案。
5. 保留三個 Pareto 式方案：最低成本、最高自駕減量、服務品質較高。

### 5.3 優先通行情境

不要做假的微觀交通模擬。MVP 將下列數值設成明確假設：

- 接駁行車時間下降百分比。
- 準點率／時間變異改善。
- 對一般車流的時間增加範圍。

同一畫面同時顯示接駁乘客受益與一般道路使用者可能的損失。

## 6. 建議環境

目前主機有 Python 3.10、`uv` 和 Docker，沒有 Node.js，也未安裝資料套件。最省時間的技術棧是：

```text
UI                 Streamlit
圖表               Plotly
地圖               PyDeck/GeoJSON；準備無底圖的離線 fallback
資料整理           Polars 或 Pandas + PyArrow
查詢               DuckDB
XML/HTTP            lxml + httpx
設定與驗證         Pydantic + YAML
測試               pytest
封裝               uv + Docker
```

不建議兩日內加入 React、PostGIS、Kafka、Airflow、SUMO 或 GPU。這些元件會增加部署與整合成本，對 demo 的決策價值有限。

### 建議目錄

```text
TAAS/
├── app.py
├── pyproject.toml
├── uv.lock
├── .env.example
├── src/taas/
│   ├── ingest/
│   │   ├── taipei_vd.py
│   │   ├── tdx.py
│   │   └── metro_od.py
│   ├── transform/vd.py
│   ├── model/
│   │   ├── mode_choice.py
│   │   ├── fleet.py
│   │   └── scenarios.py
│   └── ui/
├── configs/scenarios/
├── data/
│   ├── raw/          # 不提交大型原始檔
│   ├── interim/
│   └── demo/         # 提交小型、可重播、附來源的樣本
└── tests/
```

## 7. 賽前可準備的內容

### 必做

- 申請 TDX 帳號與 API 金鑰，先測過 token／API 流程。
- 連續累積至少 5–10 個正常平日 07:00–09:30 的臺北 VD 快照。
- 固定 10–30 個內科與聯外走廊 VD，不在前端載入全市資料。
- 建立一個完整 demo 日期；保留原始檔、清理後 Parquet 與品質報告。
- 下載一個代表月份的捷運 OD，事先串流過濾成小檔。
- 準備離線地圖 fallback，避免現場網路或圖磚服務失敗。
- 決定一組基準假設與低／中／高敏感度情境。

### 可做但次要

- 事先畫好 1–3 條候選路線 GeoJSON。
- 查詢遊覽車容量與成本，並將來源、日期和不確定區間記錄在設定檔。
- 準備一頁「資料限制與倫理」說明。

## 8. 兩日切割

### Day 1：可重播的資料故事

- 上午：接通 demo Parquet、完成 VD 地圖與 07:00–09:30 時間軸。
- 下午：完成需求假設、轉搭模型、班次／車數計算。
- 晚上前：三情境可跑通，先凍結資料 schema。

### Day 2：決策介面與敘事

- 上午：完成方案並排、敏感度圖、成本與資料血統標籤。
- 下午：處理空值、錯誤狀態、離線展示與效能。
- 最後：用固定劇本彩排，保留錄影或截圖備援。

## 9. Go / No-Go 檢查點

比賽開始前應滿足：

- 至少一個平日早尖峰 demo 快照可離線重播。
- VD 靜態與動態能以 `vd_id`／`link_id` 正確對上，方向也已人工抽查。
- 所有主畫面不依賴現場即時 API 才能開啟。
- 每個 KPI 都標記 observed、derived 或 assumed。
- 優先通行情境不把假設包裝成觀測結果。

若無法取得足夠的歷史 VD，仍可參賽，但首頁必須改稱「代表日快照＋情境模擬」，不可稱為平日典型尖峰或政策成效預測。

目前已有一個完整代表日，以及 56 個內科／聯外走廊 VD 的 8,400 筆晨尖峰 demo 資料。要使用「典型平日」這個說法，仍應再補抓至少 5–10 個正常工作日並排除颱風、事故與特殊活動日。

## 10. 建議的展示句

> 在這組需求與服務假設下，公館到瑞光路的接駁方案需要 X 輛車、Y 個班次；預估可替代 Z–W 輛自駕車。Z–W 是敏感度區間，不是已驗證的實際成效。改變票價、班距、保證座位或時間可靠度時，使用者可以直接看到結論何時反轉。

