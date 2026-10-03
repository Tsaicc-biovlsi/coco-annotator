# coco-annotator 升級說明（繁體中文）

完整英文版見 [UPGRADE.md](UPGRADE.md)。

## 升級了什麼

| 項目 | 原本 | 現在 |
|---|---|---|
| 前端 | Vue 2.5 + Vue CLI 3（webpack 4）、Node 10 | **Vue 3.5 + Vite 7**、Node 22 |
| 後端 | Python 3.6、Flask 1.0、flask-restplus（已停止維護） | **Python 3.12、Flask 3.1、flask-restx** |
| 即時通訊 | Flask-SocketIO 3 + eventlet | Flask-SocketIO 5（threading 模式） |
| 背景任務 | Celery 4.2 | Celery 5.5 |
| 資料庫 | MongoDB 4.0 | **MongoDB 7.0**（需要遷移，見下方） |
| AI 輔助 | DEXTR + Mask R-CNN（TensorFlow 1.14） | **Segment Anything（PyTorch）** |
| 介面框架 | Bootstrap 4 + jQuery | **Bootstrap 5.3**（不再使用 jQuery） |

## 新功能

### 旋轉物件框（快捷鍵 `O`）

先選取一個標註，切到「Rotated BBox」工具（↻ 圖示），用三下點擊畫框：

1. 點第一個角
2. 點第二個角：這兩點就是框的一條邊，決定方向和長度（也可以從第一點直接拖到第二點；按住 **Shift** 會吸附到 15° 的倍數）
3. 移動滑鼠拉出寬度，再點一下完成（按 **Esc** 取消）

畫好的框可以這樣編輯：拖曳圓形把手旋轉（按住 **Shift** 吸附角度）、拖曳角落縮放（對角固定不動）、在框內拖曳移動。

也可以像 BBox 一樣用**選取工具**（`S`）編輯：在框內拖曳移動、拖曳角落縮放（維持角度與矩形），點邊線不會新增點。用旋轉框工具時，方向鍵可微調位置（1 px，Shift 為 10 px）。

使用旋轉框或 SAM 工具時，點到畫面上既有的標註不會切換選取，方便在密集物體上連續畫框。要選其他標註，請點右側清單或按 `S` 切到選取工具。

較粗的那條邊代表框的「朝向」（第一條邊）。

匯出格式：

```json
"isrbbox": true,
"rbbox": [cx, cy, w, h, angle],
"segmentation": [[x1, y1, x2, y2, x3, y3, x4, y4]]
```

`angle` 單位為度，在影像座標（y 向下）中順時針為正，沿第一條邊（角點 1→2）量測。
`segmentation` 依序存 4 個角點，所以只認一般 COCO 多邊形的工具也能讀。

轉成訓練格式：

```bash
python scripts/export_obb.py coco-export.json labels/ --format dota       # DOTA
python scripts/export_obb.py coco-export.json labels/ --format yolo-obb   # Ultralytics YOLO-OBB
```

### Segment Anything（快捷鍵 `A`）

先選取一個標註，切到「SAM」工具（◎ 圖示）：

- 點物體（綠點），**Shift**+點擊排除背景（紅點），或拖曳框住物體
- 按 **Enter**（或面板上的 Apply）把預覽加入標註

切換到 SAM 工具時伺服器就會先算好該圖的 embedding，之後每次點擊約 50 ms。

啟用方式：

```bash
./models/download_sam.sh                       # 下載 vit_b 權重到 ./models
SAM=cpu docker compose up -d --build           # CPU 版
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build   # NVIDIA GPU 版
```

沒裝 PyTorch 或沒有權重檔時，SAM 工具會自動停用，不影響其他功能。

## 從舊版升級：一定要做的事

**MongoDB 資料遷移**：MongoDB 7 無法直接開啟 4.0 的資料卷（不處理的話會像是資料不見了）。

```bash
docker compose down
docker volume ls | grep mongodb_data      # 找到舊的資料卷名稱
OLD_VOLUME=舊資料卷名稱 NEW_VOLUME=coco-annotator_mongodb7 ./scripts/migrate_mongo.sh
```

完成後把 `docker-compose.yml` 裡 `database` 服務的 volume 改成新的資料卷。舊資料卷只會被讀取，不會被修改。

其他注意事項：

- 舊帳號密碼照常可登入，第一次登入時會自動轉成新的雜湊格式
- 已移除的環境變數：`MASK_RCNN_FILE`、`MASK_RCNN_CLASSES`、`DEXTR_FILE`
- 已移除的功能：Google 圖片自動下載（該套件多年前就已失效）
- 「Annotate Image」按鈕（串接外部模型伺服器）仍保留

## 順便修掉的原專案 bug

- 多執行緒下 Celery 任務會被送到錯誤的 broker（掃描、匯入、匯出都會失效）
- 檔案監看器遇到寫到一半的圖片就整個停止
- 標註畫面按 Esc 會報錯
- `FILE_WATCHER=false` 實際上會被當成開啟
- 匯出檔名出現 `b'...'`
- 幾個參照不存在變數或 model 的錯誤

## 關鍵點

選取的標註必須先有 BBox 或旋轉框，關鍵點工具才會啟用：先畫出物件的框，再標關鍵點。

## Bootstrap 5

介面已從 Bootstrap 4 + jQuery 升級為 Bootstrap 5.3，不再使用 jQuery。`client/src/assets/bootstrap-compat.css` 讓畫面維持和原本一樣的外觀。如果你自己改過模板，`data-toggle` 等屬性要改成 `data-bs-*`，部分 class 名稱也有改變（例如 `mr-2` → `me-2`、`btn-block` → `w-100`）。
