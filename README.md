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
- [預計任務](#預計任務)
- [審核流程](#審核流程)
- [資料集健康度](#資料集健康度)
- [匯入與匯出](#匯入與匯出)
- [設定](#設定)
- [從原版升級](#從原版升級)
- [常見問題](#常見問題)
- [開發](#開發)

## 主要功能

- **多種標註方式：** 邊界框（BBox）、旋轉框、多邊形、筆刷、橡皮擦、魔術棒、關鍵點
- **旋轉物件框：** 三下點擊畫出任意角度的框，可旋轉、縮放、移動；可直接匯出 YOLO-OBB，或轉成 DOTA 格式訓練
- **Segment Anything（SAM 2.1）：** 點一下物體就自動切出輪廓
- **用自己訓練的 YOLO 模型預標註：** 支援 detect、OBB、segment、pose，可以標單張圖或整個資料集
- **多人共同標註與審核：** 分享資料集、平均指派圖片給成員；標註完送審，審核者通過或退回（附原因）；進度一目了然
- **整張圖分類標籤：** 標註畫面一鍵設定整張圖的類別，做圖片分類資料集
- **資料集健康度：** 類別分布、物件大小與位置、自動找出漏標、重複框、超出邊界等問題
- **影片匯入：** 一次上傳多支影片，顯示總長與總幀數，可以設定每支的開始與結束，每隔幾秒或每隔幾幀自動擷取一張影格
- **COCO / YOLO 格式匯入、匯出：** 兩種格式互轉，YOLO 支援 detect、segment、OBB、pose
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

`download_sam.sh` 預設下載 SAM 2.1 base（約 320 MB）。只有 CPU 時可改下載較快的 tiny 版：`./models/download_sam.sh sam2.1_t`，並在 `.env` 加上 `SAM_CHECKPOINT=/models/sam2.1_t.pt`。其他選項：`sam2.1_s`、`sam2.1_l`（最準、約 900 MB），以及第一代的 `vit_b`、`vit_l`、`vit_h`。

**從第一代 SAM 升級：** 執行 `./models/download_sam.sh` 下載 SAM 2.1 後重新啟動即可。還沒下載前，伺服器會自動沿用 `models` 資料夾裡的第一代 SAM 檔案，功能不受影響。SAM 工具面板會顯示目前用的是哪個模型。

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
| `C` | 複製上一張圖片的全部標註（`Ctrl+Z` 可以復原） |
| `M` | 圖片置中 |
| `D` | 清除這張圖片的全部標註（不用確認，`Ctrl+Z` 可以復原） |

**點已有的形狀自動換工具：** 用邊界框或多邊形工具時，第一下點在已經畫好的形狀上，會自動換成畫那個形狀的工具（點矩形框→邊界框、點旋轉框→旋轉框、點多邊形→多邊形），不會開始畫新的。已經畫到一半時不會換。

左側工具列還有：
- **用模型標註**（火箭圖示）
- **全部顯示 / 全部隱藏**
- **清除這張圖片的標註**（⊗ 圖示，或按 `D`）：不用確認，直接清除；按 `Ctrl+Z` 馬上復原，或之後到「活動紀錄」的垃圾桶救回。

## 上層類別

類別可以有上層類別（父類別），而且**一個類別可以屬於多個上層類別**，例如 `car` 同時在「交通工具」和「陸地」下。在類別頁面新增或編輯類別時，直接點選已有的上層類別（可多選）；清單裡沒有的才在下方輸入名稱新增。

- **類別頁面**每個上層類別一個分頁（另有「沒有上層類別」和「全部」），每頁 16 個類別、不用上下捲動；可以搜尋，也能直接在目前的上層類別下新增類別，會記住上次看的分頁。
- **資料集頁面**也依上層類別分頁：資料集的類別屬於哪些上層類別，就出現在那些分頁（管理員看得到全部資料集，一樣分類）；另有「全部」和「沒有上層類別」，可以搜尋名稱，每頁 8 個。
- **建立資料集**的「預設類別」和**匯出**的類別清單上方有「依上層類別帶入」：點一下就勾選該上層類別下的全部類別，再點一次取消。
- **標註畫面**右側的類別清單也依上層類別分段顯示（以第一個上層類別為準）。
- 匯出 COCO 時第一個上層類別寫在 `supercategory`，全部寫在 `supercategories`；匯入 COCO 時新建的類別會帶入這兩個欄位。

## 活動紀錄與垃圾桶

上方選單的「活動紀錄」記下每個人做的每個動作，最新的在最上面、按日期分段：

- **標註**：同一個人在同一張圖連續標註會合成一筆，例如「在 a.jpg 新增 3 個標註、修改 2 個標註」，附上標出那些形狀的縮圖，按「開啟」直接進標註畫面。也包含整張圖類別、複製標註、用模型自動標註。
- **匯入匯出**：COCO / YOLO 匯入、影片匯入、上傳圖片、掃描資料夾、匯出。匯入（以及整個資料集的模型自動標註）可以按「**撤銷匯入**」，把那次建立的標註（影片則是畫格）一次移到垃圾桶。
- **刪除與還原**：每次刪除算一筆，例如「清除這張圖片的標註」刪掉的 5 個標註會合成一筆並列出各類別數量；可以直接在那一筆按「還原」或「永久刪除」，也能展開逐個還原。還原標註時，如果它所屬的圖片或資料集也被刪了，會詢問是否一起還原。
- 刪除資料集後想用**同一個名稱**再建立：建立視窗會提示垃圾桶裡有同名資料集，可以直接「還原原本的資料集」，或「用這個名稱建立新的資料集」（舊的標註紀錄永久刪除，資料夾裡的圖片保留並自動加入新資料集）。同名的類別在垃圾桶裡時，再建立一次會直接把它還原。
- **垃圾桶**分頁只列出還沒還原、還沒永久刪除的項目，可以勾選多筆一起處理，或「清空垃圾桶」。永久刪除圖片時，伺服器上的圖片檔也會一起刪除。
- **資料集與類別**、**審核**：建立 / 修改資料集、成員、類別改名，以及送審、核准、退回（含退回原因）、分配圖片。
- 可以依資料集、操作者篩選，或搜尋檔名、類別名稱。
- 紀錄和垃圾桶裡的項目保留 **90 天**後自動清除（可用 `TRASH_DAYS` 調整，`0` 表示永久保留）。這個版本之前做的動作沒有紀錄；之前刪除的項目會出現在垃圾桶，操作者顯示「未記錄」。
- 一般使用者看得到自己資料集裡的紀錄，管理員看得到全部。

## AI 輔助標註

需要先[啟用 AI 功能](#啟用-ai-功能sam-與-yolo-預標註)。

### Segment Anything（SAM 2.1）

選取一個標註，按 `A` 切到 SAM 工具（面板會顯示目前的模型，例如「SAM 2.1 b」）：

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

## 預計任務

建立資料集時可以選「預計任務」：未指定、物件偵測、實例分割、旋轉框、姿態 / 關鍵點、圖片分類、語意分割（從首頁「匯入」建立新資料集時也能選，之後可在資料集「設定」修改）。它會：

- 第一次打開標註畫面時，預先選好對應的工具（框、多邊形、旋轉框、關鍵點）；
- 匯出時預設選好 YOLO 和對應的標註類型；
- 只在「圖片分類」（或未指定）時顯示「整張圖類別」；
- 讓健康度多檢查不符合任務的標註，例如旋轉框任務裡的水平框、姿態任務裡沒有關鍵點的標註、分類任務裡還沒設類別的圖。

所有工具仍然都能用，已有的標註也不受影響。

## 審核流程

每張圖有四種狀態：**未標註 → 待審核 → 已審核**，或被**退回**。

1. **指派：** 資料集頁面的「進度與審核」分頁，勾選成員後按「平均分給 N 人」，依檔名順序把圖片切成連續的區段，每人一段。可以只分配還沒指派的、未完成的，或全部重新分配。
2. **標註：** 成員按「標註我的圖」直接開始；標完按右側的「標註完成，送審」，可以設定自動跳到自己的下一張。擁有者和審核者自己標的圖不用送審：他們的按鈕是「標註完成（直接核准）」，按下就是已核准。習慣直接按 `N` 換下一張的人，可以打開右側的「按 N 或 → 換下一張時，自動送審有標註的圖」開關（每個人自己設定，預設關閉）：有標註、還沒送審（或被退回）的圖會在換頁時自動送審，空白的圖不送。
3. **審核：** 審核者按「開始審核」，逐張「通過」或「退回」（填寫原因，標註者會在圖上看到）。
4. **匯出：** 匯出第 3 步勾「只匯出已審核的圖片」。

審核者是資料集擁有者、管理員，以及擁有者在「進度與審核」分頁勾選的成員。圖片頁左側可以依「狀態」「負責人」篩選，圖片卡片上也會顯示狀態。

**整張圖類別（圖片分類）：** 標註畫面右側的「整張圖類別」點一下類別即可設定，再點一次取消；可開「選好後自動跳下一張」快速標。匯出 YOLO classify 時以這個為準。

## 資料集健康度

資料集頁面的「健康度」分頁會自動檢查：沒有標註的圖、沒有或太少標註的類別、類別數量差距過大、疑似重複的框、超出圖片邊界或過小的框，並列出例子（點檔名直接開啟）。也有類別分布、每張圖物件數、物件大小（COCO 小 / 中 / 大）、長寬比、物件位置熱度圖和圖片尺寸。

## 匯入與匯出

- **匯出：** 資料集頁面的「匯出 COCO / YOLO」，選格式後匯出，完成後在「匯出紀錄」分頁下載。
  - **COCO：** 一個 json 檔。
  - **YOLO：** 一個 zip，最上層是 `data.yaml`、`classes.txt` 和一個由匯出者命名的資料夾（預設為資料集名稱），資料夾裡是 `train/labels/*.txt`（可勾選連圖片一起打包到 `train/images/`），解壓後就能用 `yolo train data=data.yaml` 訓練。標註類型：

    | 類型 | 輸出 | 說明 |
    |---|---|---|
    | detect | `class xc yc w h` | 每個標註的外接水平框 |
    | segment | `class x1 y1 … xn yn` | 多邊形；分成好幾塊的會接成一個多邊形 |
    | obb | `class x1 y1 … x4 y4` | 旋轉框照原本的 4 個角；其他標註用最小外接旋轉矩形 |
    | pose | `class xc yc w h px py v …` | 只輸出有關鍵點的標註，`data.yaml` 含 `kpt_shape`、`flip_idx` |
    | classify | `資料夾/train/<類別>/圖片` | 整張圖一個類別：以標註畫面設定的「整張圖類別」為準，沒設的圖看標註（只有一種類別才會匯出）；一定附圖片；不切分時 Ultralytics 會自動切 80/20；類別編號依資料夾名稱字母排序 |
    | semantic | `資料夾/train/masks/*.png` | 把框和多邊形畫成遮罩（像素值＝類別編號），0 是 background，你的類別從 1 開始；data.yaml 含 `masks_dir: masks` |

  - **檔名含資料集名稱：** YOLO 匯出的圖片和標註檔一律命名為「資料集名稱_原檔名」（例如 `ships_IMG_0001.jpg`、`ships_IMG_0001.txt`），合併多個資料集訓練時不會撞名；匯入回本系統時一樣對得到原圖。
  - **切分訓練 / 驗證 / 測試集：** 匯出時勾選「切分成訓練 / 驗證 / 測試集」，設定比例（例如 70 / 20 / 10，有常用比例可點）和亂數種子。以圖片為單位隨機分配，同樣的種子每次切出來都一樣。YOLO 的自訂資料夾裡會是 `train/images`、`train/labels`、`val/images`、`val/labels`、`test/…`，沒分到圖片的組不會寫進 data.yaml，`data.yaml` 自動指到各組；COCO 會變成內含 `train.json`、`val.json`、`test.json` 的 zip。不切分時，YOLO 全部放在 `資料夾/train/`，data.yaml 的 train 和 val 都指向它。
- **匯出紀錄：** 列出每次匯出的序號、格式（含切分比例與張數）、類別、時間，可以下載或刪除（伺服器上的檔案會一起刪掉）。
- **從首頁匯入：** 首頁的「匯入」可以把圖片、影片和標註檔（COCO json 或 YOLO zip）一起匯入到既有或新的資料集。
- **影片：** 在「匯入」選影片（mp4、mov、avi、mkv、webm…），可以一次選多支。每支選好就先上傳，顯示長度、fps、總幀數和解析度，上方也會加總所有影片的總長和總幀數；每支可以拖曳滑桿或輸入時間（分:秒）設定擷取的開始與結束，瀏覽器能播放的格式還能用預覽畫面的目前時間當開始 / 結束。再設定每隔幾秒或每隔幾幀取一張（用幀數時不受影片 fps 影響），以及每支最多幾張，會即時顯示預計擷取幾張。上傳了但沒匯入的影片 24 小時後自動清掉。影格存成 JPG，放在以影片命名的子資料夾（例如 `cam1/cam1_000m01s000.jpg`，檔名是時間點），影片本身擷取完就刪除。影片會切成每塊 8 MB 分段上傳，網路斷掉的那一塊會自動重送，也不受反向代理單次上傳大小（例如 100 MB）的限制；單支上限 20 GB（`MAX_VIDEO_SIZE`）。直接選一個 YOLO 資料集資料夾（例如 `train/images`、`train/labels`、`data.yaml`，或 `images/`、`labels/` 的結構都可以）也可以，圖片和標註會一起匯入。
- **匯入 COCO：** 資料集頁面的「匯入 COCO / YOLO」上傳 COCO 格式的 json。圖片要先放好並掃描，會依檔名對應圖片（`file_name` 裡的資料夾會被忽略）。支援只有框的標註（例如 Roboflow、YOLO 轉出的 COCO）、多邊形、RLE 遮罩、關鍵點和旋轉框。匯入完成會跳出提示，有找不到的圖片等問題時，詳情在「任務」頁面。
- **匯入 YOLO：** 同一個按鈕上傳 zip，裡面放 YOLO 標註 `.txt`（資料夾結構不拘，例如 `labels/train/*.txt`）和 `data.yaml` 或 `classes.txt`（沒有的話類別會叫 `class_0`、`class_1`…）。依檔名（不含副檔名）對應資料集裡的圖片，所以圖片要先在資料集裡。標註類型預設自動判斷，也可以手動指定；detect 會變成框、segment 變成多邊形、obb 變成旋轉框、pose 變成框 + 關鍵點。

### 不經過網頁的轉檔

```bash
# COCO -> YOLO（--images 會順便把圖片複製到 out/train/images）
python scripts/coco_yolo.py coco2yolo coco-export.json out/ --task segment --images /path/to/images

# YOLO -> COCO（圖片尺寸從圖檔讀取）
python scripts/coco_yolo.py yolo2coco path/to/labels path/to/images coco.json --names data.yaml
```

需要 numpy、Pillow、PyYAML（obb 從多邊形轉換時需要 opencv）。

旋轉框在 COCO json 中的格式：

```json
"isrbbox": true,
"rbbox": [cx, cy, w, h, angle],
"segmentation": [[x1, y1, x2, y2, x3, y3, x4, y4]]
```

`angle` 的單位是度，在影像座標（y 軸向下）中順時針為正。`segmentation` 依序存 4 個角點，所以只認一般多邊形的工具也讀得懂。

YOLO-OBB 直接用上面的 YOLO 匯出（類型選 obb）。轉成 DOTA 格式：

```bash
python scripts/export_obb.py coco-export.json labels/ --format dota
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
| `SAM_CHECKPOINT` | `/models/sam2.1_b.pt` | SAM 權重檔；找不到時自動使用 `models` 資料夾裡最好的 SAM 檔案 |
| `COMPOSE_FILE` | — | 使用 GPU 時設為 `docker-compose.yml:docker-compose.gpu.yml` |
| `LOG_LEVEL` | `info` | 伺服器紀錄的詳細程度，除錯時可設 `debug` |
| `WEB_THREADS` | `300` | 同時連線數上限，每個開著的頁面佔用一個 |
| `SAM_CACHE_SIZE` | `64` | SAM 快取幾張圖的特徵 |
| `TRASH_DAYS` | `90` | 活動紀錄與垃圾桶保留天數，`0` 表示永久保留 |

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
