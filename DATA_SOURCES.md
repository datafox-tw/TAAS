# TAAS 公開資料清單與下載紀錄

盤點日期：2026-10-13（Asia/Taipei）

## 1. 可直接用於黑客松的資料

| 類別 | 本地檔案 | 下載／內容檢查 | MVP 用途 | 主要限制 |
|---|---|---|---|---|
| TDX VD 歷史動態 | `data/raw/tdx/history/taipei_vd_live_2026-10-06.jsonl.gz` | 96,510,910 bytes；934,562 筆；650 個 VD；2026-10-06 代表平日 | 晨尖峰流量、速度、佔有率與資料品質基準 | 一天不能代表典型平日；原始時間是 UTC，使用時轉 Asia/Taipei |
| TDX VD 靜態／即時 | `data/raw/tdx/taipei_vd_*.json` | 靜態 641 個、即時 647 個，638 個 ID 可對接 | VD 位置、道路名、即時狀態 | 部分站點狀態異常；不能把缺值當 0 |
| TDX 道路路段 | `data/raw/tdx/road/*.json` | 818 個路段及其 shape、link、live 資料 | 候選路線與路況背景 | 路段資料與 VD 需用 LinkID／空間方式核對 |
| TDX 北捷站點 | `data/raw/tdx/rail/*.json` | 122 個站點、439 個出口、22 筆路線資料 | 上車點、轉乘點及步行接駁設計 | 站點不是通勤者住址 |
| 北捷分時 OD | `data/raw/metro/trtc_od_202608.csv` | 312,474,694 bytes；8,515,081 行；2026-08 | 推估「搭捷運到西湖／港墘」的來源站分布 | 只代表捷運旅次，不能當全體內科員工 OD |
| 2026 行政機關辦公日曆 | `data/raw/calendar/taiwan_work_calendar_2026.csv` | 2026 年日期、星期、是否放假、備註 | 篩選工作日 | 企業輪班日可能不同 |
| 大內科通勤估算 | `data/raw/neihu_commute/neihu_pop.geojson` | 5,945 個 polygon feature；含 `pop_work_min`、大眾運輸及私人運具估算 | 需求熱區與通勤模式的先驗分布 | 臺北大數據中心研究使用 2019 年資料，適合當先驗而非現在真值 |
| 最新園區調查 | `data/raw/reports/taipei_industrial_parks_survey_2025.pdf` | 252 頁；資料標準日為 2024-12-31 | 校準需求總量上限 | 場所員工數不是每日進入園區的通勤人次，也沒有住址 OD |
| 行政區／里界 | `data/raw/boundaries/*.zip` | ZIP 完整性通過 | 地圖分區、需求聚合 | 需確認座標系統再與 WGS84 疊圖 |
| 土地使用 | `data/raw/landuse/taipei_landuse_detailed_20260409.zip` | ZIP 完整性通過 | 辨識辦公／產業目的地區塊 | 細分區資料不是建物實際員工數 |
| 臺北交通調查索引 | `data/raw/reports/taipei_traffic_survey_index.csv` | Big5 CSV，內含 113 年官方交通調查報告 URL | 後續補充路口人工調查 | 索引本身只有一筆連結；大 PDF 尚未下載 |

原始檔合計約 412 MiB，已由 `.gitignore` 排除。檔案雜湊在 `data/CHECKSUMS.sha256`；正式展示應使用小型衍生檔，不要讓前端直接掃描完整原始資料。

## 2. 已產生的可提交 demo 資料

| 檔案 | 內容 | 建議用法 |
|---|---|---|
| `data/demo/neihu_vd_stations.csv` | 56 個道路名含內湖、瑞光、堤頂、民權、成美、南京東、舊宗或港墘的 VD | 地圖點位與篩選清單 |
| `data/demo/neihu_vd_2026-10-06_0700-0930.csv.gz` | 56 個 VD、07:00–09:30（不含 09:30）共 8,400 筆一分鐘觀測 | Demo 的時間軸與 15 分鐘聚合來源 |
| `data/demo/metro_od_to_neihu_weekday_am_202608.csv.gz` | 2026-08 工作日 07、08、09 時，所有進站到西湖／港墘的 15,120 筆 OD | 捷運來源站分布與需求旁證 |
| `data/demo/metro_od_to_neihu_weekday_am_202608_origin_summary.csv` | 240 組來源站—目的站，含月總量與 21 個工作日平均 | 直接畫排行榜或來源站熱點 |

VD demo 的 `volume_total` 為各 link、lane、vehicle type 的流量加總，`speed_weighted_kph` 為依有效車流量加權的速度；無車流時保留空值。它尚未做 15 分鐘聚合，避免把原始時間解析度不可逆地丟掉。

## 3. 官方來源與取得方式

### TDX

- 服務目錄：<https://tdx.transportdata.tw/webapi/serviceCategory/ForSwagger>
- 路況 API 文件：<https://tdx.transportdata.tw/api-service/swagger/basic/7f07d940-91a4-495d-9465-1c9df89d709c>
- 歷史路況服務 ID：`4b4708cc-ab49-4037-a896-e24544d51609`
- 使用的歷史端點：`/v2/Historical/Road/Traffic/Live/VD/City/Taipei`
- 歷史日期範圍：官方規格列為 2021-07 起至前一日；單次最多七天。
- 驗證：`TAAS/.env` 的 `CLIENT_ID`／`CLIENT_SECRET` 已實測可取得 token 及下載歷史資料。金鑰沒有寫入檔案或終端輸出。

### 臺北捷運

- 資料集頁：<https://data.taipei/dataset/detail?id=63f31c7e-7fc3-418b-bd82-b95158755b4d>
- `trtc_od_index.csv` 提供各月份下載 URL；目前已下載最新可見月份 2026-08。

### 需求與空間資料

- 臺北大數據中心「從數據看內湖科學園區通勤模式」：<https://tuic.gov.taipei/neihu_traffic/>
- 網頁公開資料資產：<https://tuic.gov.taipei/neihu_traffic/data/neihu_pop.geojson>
- 114 年度臺北市產業園區調查頁：<https://doed.gov.taipei/News.aspx?n=C568C7A97D6A724E&sms=CE25DF0D313A68D2>
- 2026 行政機關辦公日曆：<https://data.gov.tw/dataset/14718>
- 臺北市行政區界：<https://data.gov.tw/dataset/121199>
- 臺北市里界：<https://data.taipei/dataset/detail?id=6d864ede-c482-4f33-bb89-5be19dc772e1>
- 臺北市土地使用分區：<https://data.taipei/dataset/detail?id=3bab0a01-7936-4218-8cb5-f74dfcb43dda>
- 臺北市交通流量及特性調查索引：<https://data.taipei/dataset/detail?id=68767aa4-6703-4760-8a0e-74c641d66b90>

大內科最新園區調查的 2024 年底數字為 7,462 個場所、228,905 名場所從業員工。此數字只適合限制情境需求的合理上限；不能直接代入「每日 228,905 人通勤」或「全部在晨尖峰進入」。

臺北大數據中心的公開 GeoJSON 是網站資料資產，沒有在檔內附獨立授權欄位；若作品要公開再散布原始檔，應保留來源標示並再次確認網站授權。政府開放資料檔則依各資料集頁標示的政府資料開放授權條款使用。

TUIC 網站在本機 `curl` 驗證時回報不完整的 TLS 憑證鏈，因此該公開、無帳密的 GeoJSON 是在確認網域與路徑後以 `--insecure` 下載。這個例外不可套用到 TDX token、任何帶憑證的請求或其他網域；正式重跑時優先以瀏覽器下載，或等待網站修復憑證鏈。

## 4. 目前需要人工補的資料

以下不阻擋兩日 MVP，但若要讓成本與轉搭預測可用於真實決策，就不能只靠公開資料：

1. **現行包車報價**：向 2–3 家合法業者詢問同一規格（平日晨間、26／43 人座、起終點、單程或來回、等待與回送、稅、過路費）。公開統計只能做成本先驗，不能取代現在的正式報價。
2. **員工需求與偏好**：合作企業的匿名郵遞區號／捷運站級起點、實際到班時段、目前運具、可接受步行與候車、票價與企業補助、保證座位偏好。公開資料無法識別「誰是內科員工」。
3. **交通部遊覽車原始調查 ZIP**：官方下載端點在此 Linux 環境連續回 HTTP 502。可在瀏覽器下載後放到 `data/raw/tour_bus/TourBus_11406_upload.zip`：<https://www.motc.gov.tw/201506260001/uploaddowndoc?file=datagov%2F1382609415093358592.zip&filedisplay=TourBus_11406_upload.zip&flag=doc>。這是加分資料，不是 MVP blocker。

交通部資料集說明頁：<https://data.gov.tw/dataset/6253>。最新可線上閱讀的 112 年調查報告包含平均年里程、營收、維修／燃料成本與載客數等統計，但仍不是指定路線的市場報價。

## 5. 資料使用邊界

- `observed`：TDX、捷運 OD、園區統計等直接觀測或官方統計。
- `derived`：15 分鐘聚合、加權速度、工作日平均、候選熱點等可重算結果。
- `assumed`：轉搭率、平均乘載率、包車成本、票價、可靠度改善、優先通行效果。

任何 KPI 都應保留這三類標籤。特別是捷運 OD、TUIC 2019 通勤估算與 2024 年底園區員工數，三者口徑不同，不可直接相加。
