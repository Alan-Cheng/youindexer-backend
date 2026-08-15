# YouTube 關鍵字搜尋

此搜尋功能使用獨立且匿名的 Playwright Chromium BrowserContext。它會開啟
YouTube 公開搜尋結果頁面、解析一般影片結果、移除重複的影片 ID，並持續捲動頁面，
直到取得指定數量的結果，或 YouTube 不再回傳更多結果為止。

## 安裝

```powershell
uv sync
uv run playwright install chromium
```

Playwright 瀏覽器只需在每台機器或容器中安裝一次。部署 Celery worker 時，也應將
瀏覽器安裝指令加入容器映像的建置流程。

## 使用 CLI 測試

預設會顯示 Chromium 瀏覽器視窗：

```powershell
uv run youtube-search "Python Playwright" -n 10
```

若不希望顯示瀏覽器視窗，可以啟用 headless 模式。Celery worker 或容器環境通常建議
使用此模式：

```powershell
uv run youtube-search "Python Playwright" -n 10 --headless
```

指令會將 UTF-8 編碼的 JSON 陣列輸出至標準輸出。若要查看其他參數，請執行：

```powershell
uv run youtube-search --help
```

主要參數：

- `query`：要搜尋的 YouTube 關鍵字。
- `-n`／`--limit`：需要取得的結果數量，預設為 10，範圍為 1 至 500。
- `--headless`：不顯示瀏覽器視窗。
- `--no-headless`：顯示瀏覽器視窗，此為預設行為。
- `--timeout-ms`：等待 YouTube 頁面的逾時毫秒數，預設為 30,000。
- `--locale`：瀏覽器語系，預設為 `zh-TW`。

## HTTP API

啟動 FastAPI：

```powershell
uv run uvicorn app.main:app --reload
```

匿名搜尋 API 固定使用 headless Chromium：

```http
GET /api/v1/youtube/search?q=Python%20Playwright&limit=10&locale=zh-TW&timeout_ms=30000
```

PowerShell 範例：

```powershell
$params = @{
    q = "Python Playwright"
    limit = 10
    locale = "zh-TW"
    timeout_ms = 30000
}

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/api/v1/youtube/search" `
    -Body $params
```

API 參數限制：

- `q`：必填，去除前後空白後不可為空，最多 200 個字元。
- `limit`：選填，預設 10，範圍為 1 至 100。
- `locale`：選填，預設 `zh-TW`。
- `timeout_ms`：選填，預設 30,000，範圍為 5,000 至 120,000。

成功時回傳 HTTP 200。參數錯誤時回傳 HTTP 422；Playwright 或 YouTube 搜尋失敗時
回傳 HTTP 502。

## Python 呼叫方式

### Celery worker

搜尋函式是同步函式，因此 Celery task 可以直接呼叫：

```python
from app.youtube import search_youtube

results = search_youtube("Python Playwright", 10, headless=True)
payload = [result.as_dict() for result in results]
```

每次呼叫都會建立新的 BrowserContext，不會與其他工作共用 Cookie 或瀏覽器狀態，
適合由不同 Celery 工作獨立執行。

### FastAPI

Playwright 的同步搜尋會占用目前執行緒。FastAPI 的非同步 handler 應使用
`asyncio.to_thread()`，避免阻塞 event loop：

```python
import asyncio

from app.youtube import search_youtube

results = await asyncio.to_thread(
    search_youtube,
    "Python Playwright",
    10,
    headless=True,
)
```

## 回傳資料

每筆 `YouTubeSearchResult` 包含：

- `video_id`：YouTube 影片 ID。
- `title`：影片標題。
- `url`：正規化後的影片網址。
- `channel_name`：頻道名稱。
- `channel_url`：頻道網址。
- `thumbnail_url`：縮圖網址。
- `duration`：影片長度文字。
- `published_text`：發布時間文字，例如「5 年前」。
- `view_count_text`：觀看次數文字。
- `description`：搜尋結果中的影片說明摘要。

YouTube 搜尋頁面不一定有足夠的結果，因此回傳數量最多為指定的 `limit`，有可能少於
要求的數量。

## 正式環境注意事項

- 建議限制同時啟動的 Chromium 數量，避免 Celery worker 耗用過多記憶體與 CPU。
- 建議快取相同關鍵字的搜尋結果，減少重複請求。
- 高頻率或大量自動化請求可能被 YouTube 限流。
- YouTube 搜尋頁面不是穩定的公開 API，頁面結構可能調整，因此應建立定期的整合測試，
  監控 selector 是否仍能正常解析。
- 正式部署前應自行評估 YouTube 服務條款及資料使用規範。
