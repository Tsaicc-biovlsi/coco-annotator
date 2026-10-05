# COCO Annotator（2026 升級版）

繁體中文 ｜ [English](README.en.md)

> 修改：**TsaiCC × Claude**

COCO Annotator 是一套網頁版的影像標註工具，用來製作物件偵測、實例分割、關鍵點等模型的訓練資料，標註結果以通用的 [COCO 格式](https://cocodataset.org/#format-data) 匯出。

這個版本是從 [jsbroks/coco-annotator](https://github.com/jsbroks/coco-annotator) fork 出來的，除了把整套技術升級到目前仍有維護的版本，也加上了旋轉物件框、Segment Anything、用自己的 YOLO 模型預標註等功能。

## 目錄

- [主要功能](#主要功能)
- [安裝](#安裝)
- [第一次使用](#第一次使用)
- [標註工具與快捷鍵](#標註工具與快捷鍵)
- [AI 輔助標註](#ai-輔助標註)
- [帳號、權限與共同標註](#帳號權限與共同標註)
- [匯入與匯出](#匯入與匯出)
- [設定](#設定)
- [從原版升級](#從原版升級)
- [常見問題](#常見問題)
- [開發](#開發)

## 主要功能

- **多種標註方式：** 邊界框（BBox）、旋轉框、多邊形、筆刷、橡皮擦、魔術棒、關鍵點
- **旋轉物件框：** 三下點擊畫出任意角度的框，可旋轉、縮放、移動；可轉成 DOTA 或 YOLO-OBB 格式訓練
- **Segment Anything（SAM）：** 點一下物體就自動切出輪廓
- **用自己訓練的 YOLO 模型預標註：** 支援 detect、OBB、segment、pose，可以標單張圖或整個資料集
- **多人共同標註：** 把資料集分享給成員，大家一起標；管理員管理帳號與權限
- **COCO 格式匯入、匯出**
- **介面語言：** English、繁體中文

## 安裝

需要一台裝好 [Docker](https://docs.docker.com/engine/install/)（含 Docker Compose）的 Linux 主機。

```bash
git clone -b upgrade-2026 https://github.com/Tsaicc-biovlsi/coco-annotator.git
cd coco-annotator
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env
sudo docker compose up -d --build
```

完成後用瀏覽器打開 `http://伺服器IP:5000`。第一次開啟時會要求註冊，**第一個註冊的帳號會自動成為管理員**。

### 啟用 AI 功能（SAM 與 YOLO 預標註）

AI 功能需要 PyTorch，預設不安裝，讓映像檔保持精簡。

**有 NVIDIA 顯示卡（建議）：**

1. 安裝 [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)，並確認以下指令會印出顯示卡資訊：
   ```bash
   sudo docker run --rm --gpus all ubuntu nvidia-smi
   ```
2. 下載 SAM 模型，並讓 Docker Compose 每次都帶上 GPU 設定：
   ```bash
   ./models/download_sam.sh
   echo "COMPOSE_FILE=docker-compose.yml:docker-compose.gpu.yml" >> .env
   sudo docker compose up -d --build
   ```

**只有 CPU：**

```bash
./models/download_sam.sh
echo "SAM=cpu" >> .env
sudo docker compose up -d --build
```

用 CPU 也能運作，只是每張圖第一次使用 SAM 時要等幾秒，模型預標註也比較慢。

## 第一次使用

**最簡單的方式：** 在首頁按「匯入」，選「建立新資料集」並輸入名稱，再選圖片（或整個資料夾），有 COCO 標註檔的話一併選上，按「匯入」就完成了。圖片會上傳到伺服器，同名的檔案會略過。

**圖片很多時**（例如上萬張），直接放到伺服器上比較快：

1. **放圖片：** 在伺服器的 `datasets/` 底下建一個資料夾，把圖片放進去，例如 `datasets/baseball/0001.jpg`。
2. **建立資料集：** 在網頁「資料集」頁面按「建立資料集」，名稱填資料夾名稱（例如 `baseball`），並加入要用的類別。
3. **掃描：** 進入資料集，按左側的「掃描」，圖片就會出現。之後再放新圖片進資料夾，再按一次掃描即可。
4. **開始標註：** 點任一張圖片進入標註畫面：
   1. 在右側選一個類別，按 `+` 新增一個標註（或按空白鍵）。
   2. 從左側工具列選工具開始畫。
   3. 修改會**自動儲存**：停下來約 2 秒後就會存到伺服器，關閉或重新整理頁面前也會先存。也可以隨時按 `Ctrl+S` 手動儲存。

## 標註工具與快捷鍵

### 工具

| 工具 | 快捷鍵 | 用途 |
|---|---|---|
| 選取 | `S` | 選取、移動、調整既有的標註（BBox 和旋轉框可直接拖曳移動、縮放） |
| 邊界框 | `R` | 拖曳畫出矩形框 |
| 旋轉框 | `O` | 畫任意角度的框（見下方說明） |
| 多邊形 | `V` | 逐點畫出輪廓 |
| 魔術棒 | `W` | 依顏色相近程度自動選取區域 |
| 筆刷 / 橡皮擦 | `B` / `E` | 塗抹增加或擦除區域（`[` `]` 調整大小） |
| 關鍵點 | `K` | 在已有框的標註上標關鍵點 |
| SAM | `A` | AI 自動分割（見 [AI 輔助標註](#ai-輔助標註)） |

### 旋轉框怎麼畫

1. 點第一個角。
2. 點第二個角，這兩點就是框的一條邊。按住 `Shift` 可以讓角度吸附到 15° 的倍數。
3. 移動滑鼠拉出寬度，再點一下完成。按 `Esc` 取消。

畫好後可以拖曳圓形把手旋轉、拖曳角落縮放、在框內拖曳移動，也可以用方向鍵微調位置（`Shift` 加方向鍵一次移動 10 px）。

在畫面上點另一個旋轉框會選取它，就能調整它的角度和位置。要在既有的框裡面畫新框（例如物體重疊時），按住 `Ctrl` 再點第一個角。

### 關鍵點

關鍵點必須依附在框上：先為標註畫出 BBox 或旋轉框，關鍵點工具才會啟用。類別的關鍵點名稱與連線，在類別設定（齒輪）裡定義。

### 其他快捷鍵

| 快捷鍵 | 動作 |
|---|---|
| `空白鍵` | 新增標註 |
| `Backspace` | 刪除目前的標註 |
| `Ctrl+Z` | 復原（包含刪除標註、清除整張圖片的標註） |
| `Ctrl+S` | 儲存 |
| `N` / `P` | 下一張 / 上一張圖片 |
| `↑` `↓` | 在標註之間切換 |
| `→` `←` | 展開 / 收合類別 |
| `C` | 圖片置中 |

左側工具列還有：
- **用模型標註**（火箭圖示）
- **全部顯示 / 全部隱藏**
- **清除這張圖片的標註**（⊗ 圖示）：刪除的標註可以在「復原」頁面救回。

## AI 輔助標註

需要先[啟用 AI 功能](#啟用-ai-功能sam-與-yolo-預標註)。

### Segment Anything（SAM）

選取一個標註，按 `A` 切到 SAM 工具：

- 點物體（綠點）：自動切出輪廓。
- `Shift` + 點擊（紅點）：排除不要的部分。
- 也可以直接拖一個框把物體框起來。
- 按 `Enter` 套用。

### 用自己訓練的 YOLO 模型預標註

支援 Ultralytics YOLO（YOLOv8、YOLO11 以後的版本）的四種模型：

| 模型類型 | 產生的標註 |
|---|---|
| detect | 物件框 |
| obb | 旋轉框 |
| segment | 多邊形 |
| pose | 物件框 + 關鍵點 |

**放入模型（二選一）：**
- 管理員在「用模型標註」視窗下方直接上傳 `.pt` 檔。
- 把 `.pt` 檔複製到伺服器的 `models/` 資料夾，不需要重啟。

建議把檔名改成好認的名稱，例如把 `best.pt` 改成 `baseball_det.pt`，因為選單上顯示的就是檔名。

**使用：**
- **單張圖：** 標註畫面左側的火箭圖示 → 選模型、調整最低信心分數 → 執行。
- **整個資料集：** 資料集頁面左側的「用模型預標註」，在背景執行，進度顯示在「任務」頁面；可以選擇略過已經有標註的圖片。

模型的類別會依名稱（不分大小寫）對應到資料集的類別，缺少的類別可以選擇自動建立。預測結果是一般的標註，可以再人工修正。

> ⚠️ 載入 `.pt` 檔時會執行檔案裡的程式碼，只放你信任來源的模型。這也是為什麼只有管理員能上傳。

## 帳號、權限與共同標註

- **管理員：** 可以看到所有資料集，並在「管理」頁面建立、編輯、刪除帳號（改名稱、重設密碼、設定管理員身分）。
- **一般使用者：** 只看得到自己建立的資料集，以及別人分享給他的資料集。
- **分享資料集：** 在資料集卡片右下角的 **⋮** 選單選「分享」，輸入成員的使用者名稱，再按「儲存」。
- **關閉公開註冊：** 在 `.env` 加上 `ALLOW_REGISTRATION=false`，再執行 `sudo docker compose up -d`。之後只能由管理員建立帳號。

**附加資訊：** 每個標註、圖片都可以加上自訂的「名稱 → 值」欄位，例如 `occluded: true`、`note: 被遮擋`。匯出時會跟著輸出，方便之後篩選資料。資料集設定裡可以設定每個新標註預設帶有的欄位。

## 課堂使用（多人同時標註）

在本機模擬 50 位學生、每人開 3 個分頁同時標註，沒有出現錯誤。

1. **建立學生帳號：** 「管理」頁面的「批次建立帳號」，貼上學號和姓名（可以直接從 Excel 複製兩欄），可以順便把作業的資料集分享給所有人。建好後下載帳號密碼的 CSV 發給學生。學號格式為 1 個英文字母加 8 位數字（例如 B11223344）。
2. **事先準備好圖片：** 上課前先放好圖片並按「掃描」，伺服器會在背景產生縮圖。不要等大家都進來才掃描。
3. **分配工作，不要多人同時改同一張圖：** 兩個人同時編輯同一張圖時，後存檔的會蓋掉先存的。建議每人或每組一個資料集，或明確分配圖片範圍。
4. **AI 功能排隊處理：** SAM 和模型預標註在 GPU 上一次處理一個請求，很多人同時用時會稍微等一下；整個資料集的模型預標註建議由助教先跑好。

相關設定（`.env`）：`WEB_THREADS`（預設 300，每個開著的頁面佔用一個，約可容納 100 人）、`SAM_CACHE_SIZE`（預設 64 張圖）。

## 匯入與匯出

- **匯出：** 資料集頁面的「匯出 COCO」，完成後在「匯出紀錄」分頁下載。
- **從首頁匯入：** 首頁的「匯入」可以把圖片和 COCO 標註檔一起匯入到既有或新的資料集。
- **匯入 COCO：** 資料集頁面的「匯入 COCO」上傳 COCO 格式的 json。圖片要先放好並掃描，會依檔名對應圖片（`file_name` 裡的資料夾會被忽略）。支援只有框的標註（例如 Roboflow、YOLO 轉出的 COCO）、多邊形、RLE 遮罩、關鍵點和旋轉框。匯入完成會跳出提示，有找不到的圖片等問題時，詳情在「任務」頁面。

旋轉框在 COCO json 中的格式：

```json
"isrbbox": true,
"rbbox": [cx, cy, w, h, angle],
"segmentation": [[x1, y1, x2, y2, x3, y3, x4, y4]]
```

`angle` 的單位是度，在影像座標（y 軸向下）中順時針為正。`segmentation` 依序存 4 個角點，所以只認一般多邊形的工具也讀得懂。

轉成旋轉框模型的訓練格式：

```bash
python scripts/export_obb.py coco-export.json labels/ --format yolo-obb   # Ultralytics YOLO-OBB
python scripts/export_obb.py coco-export.json labels/ --format dota       # DOTA
```

## 設定

設定寫在專案資料夾的 `.env`（參考 `.env.example`），修改後執行 `sudo docker compose up -d` 生效。

| 變數 | 預設值 | 說明 |
|---|---|---|
| `SECRET_KEY` | — | 登入用的加密金鑰，**請務必設定一組隨機值** |
| `ALLOW_REGISTRATION` | `true` | 是否開放任何人註冊 |
| `DATASETS_DIR` | `./datasets` | 圖片放在主機的哪個資料夾 |
| `MODELS_DIR` | `./models` | SAM 和 YOLO 模型放在主機的哪個資料夾 |
| `SAM` | `none` | 建置時是否安裝 AI 功能：`none`、`cpu`、`cuda` |
| `COMPOSE_FILE` | — | 使用 GPU 時設為 `docker-compose.yml:docker-compose.gpu.yml` |
| `LOG_LEVEL` | `info` | 伺服器紀錄的詳細程度，除錯時可設 `debug` |

## 從原版升級

原版使用 MongoDB 4.0，新版使用 MongoDB 7.0，資料庫需要一次性的遷移。請先看 [UPGRADE.zh-TW.md](UPGRADE.zh-TW.md)，步驟摘要：

```bash
cd coco-annotator                        # 原本執行 docker compose 的資料夾
sudo docker compose down                 # 停止舊版
git fetch && git checkout upgrade-2026
sudo ./scripts/migrate_mongo.sh          # 舊資料在 ./db 資料夾的話：sudo OLD_DIR=$PWD/db ./scripts/migrate_mongo.sh
sudo docker compose up -d --build
```

舊的資料庫完全不會被修改，隨時可以切回 `master` 退回舊版。舊帳號、密碼照常可以登入。

## 常見問題

**縮圖或圖片顯示「圖片不存在」**
資料庫裡有這張圖，但伺服器的 `datasets/` 資料夾找不到檔案（被刪除、搬走，或資料夾掛載路徑不對）。

**升級後打開網站叫我註冊，像是沒有任何帳號**
通常是 MongoDB 被強制關閉後統計數字沒更新。執行以下指令修正（只會檢查、更正統計，不會改資料）：
```bash
sudo docker exec annotator_mongodb mongosh flask --quiet --eval 'db.getCollectionNames().forEach(c => db.getCollection(c).validate({full: true}))'
```

**更新後畫面怪怪的，或紀錄裡出現 `unsupported version of the Socket.IO`**
瀏覽器還在用舊版網頁，按 `Ctrl+Shift+R` 強制重新整理。

**`git pull`、`docker compose build` 出現 `Could not resolve host`**
主機的 DNS 沒設定好。檢查 `/etc/resolv.conf` 裡有沒有 `nameserver`，有些校園網路只允許使用學校的 DNS。

**AI 工具是灰色的，或模型視窗顯示「沒有安裝模型支援」**
映像檔是用預設的 `SAM=none` 建置的，請參考[啟用 AI 功能](#啟用-ai-功能sam-與-yolo-預標註)重新建置。

**查看伺服器紀錄**
```bash
sudo docker logs annotator_webclient --tail 50
sudo docker logs annotator_workers --tail 50
```

**備份**
資料庫備份（產生一個檔案，連同 `datasets/` 資料夾一起保存即可）：
```bash
sudo docker exec annotator_mongodb mongodump --db flask --archive --gzip > coco-backup-$(date +%F).archive.gz
```

## 開發

```bash
# 後端測試（不需要 MongoDB、RabbitMQ）
cd backend && pip install -r requirements.txt mongomock pytest pytest-order && pytest

# 前端開發伺服器（熱重載）與測試
cd client && npm ci && npm run dev
npm test
```

或用 `docker compose -f docker-compose.dev.yml up --build`，開啟 `http://localhost:8080`。

| 部分 | 技術 |
|---|---|
| 後端 | Python 3.12、Flask 3、Flask-RESTX、Flask-SocketIO 5、Celery 5、MongoDB 7（MongoEngine）、RabbitMQ 4 |
| 前端 | Vue 3、Vite、Vuex 4、vue-i18n、Paper.js、Bootstrap 5 |
| AI | PyTorch、Segment Anything、Ultralytics YOLO（選用） |

介面翻譯檔在 `client/src/i18n/locales/`。

## 授權

[MIT](LICENSE.md)：可以自由使用、修改與轉發（包含商業用途），但須保留授權檔中的著作權聲明。

- 原專案：[Justin Brooks](https://github.com/jsbroks/coco-annotator)
- 2026 升級與新功能：**TsaiCC × Claude**
