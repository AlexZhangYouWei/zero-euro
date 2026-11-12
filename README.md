# 0 € 紀念鈔圖鑑

收錄世界各地 0 歐元紀念鈔（0 Euro Souvenir Banknote）的靜態圖鑑網站，介面為繁體中文。

- **2,323** 個地點代碼、**7,373** 個版本，涵蓋 **77** 個國家
- 資料來源：[0eurosouvenirs.com](https://0eurosouvenirs.com/) 與 [nulleuro.ch](https://www.nulleuro.ch/)，依「代碼＋版次」合併兩邊的資料

## 功能

- 關鍵字搜尋（名稱、代碼、城市）
- 依地區、國家、城市篩選
- 依名稱、最新年份、國家／城市、版本數排序
- 點開單張可切換各版次，查看發行量、序號等欄位，並連回原始來源頁面

## 瀏覽

純靜態網頁，沒有框架，也不需要建置工具。可以直接用瀏覽器開啟 `index.html`，或透過 GitHub Pages 瀏覽。

## 目錄結構

```
index.html        網頁（介面與渲染邏輯）
data.js           build.py 產生的合併資料，請勿手動修改
images/           鈔票圖片（osv/、nulleuro/）
data/
├── osv.json、nulleuro.json      各來源正規化後的資料
├── osv_raw/、nulleuro_raw/      爬蟲原始快取（可續爬）
├── names_zh.json、cities_zh.json 名稱與城市的中文對照
├── translate/、translate_city/  中文翻譯的批次檔
└── country_codes.json           國家代碼
scripts/
├── scrape_osv.py       爬取 0eurosouvenirs.com
├── scrape_nulleuro.py  爬取 nulleuro.ch（需要登入）
└── build.py            合併兩個來源，產生 data.js
```

## 更新資料

```bash
python3 -I scripts/scrape_osv.py        # 可加數量上限參數；有快取，可中斷續爬
python3 -I scripts/scrape_nulleuro.py   # 需要 nulleuro_cookie.txt（見下方）
python3 -I scripts/build.py             # 重新產生 data.js
```

`scrape_nulleuro.py` 需要登入 nulleuro.ch。請從瀏覽器複製 `sessionid=...`（或完整的 Cookie 標頭）存成專案根目錄的 `nulleuro_cookie.txt`。這個檔案已列入 `.gitignore`，不會被提交。

## 聲明

本專案為個人收藏整理用途。圖片與鈔票資料的權利屬於原始網站及各發行者。
