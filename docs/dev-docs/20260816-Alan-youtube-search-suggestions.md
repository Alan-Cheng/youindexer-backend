# YouTube 搜尋框下拉建議

此功能以 Playwright 實際開啟 YouTube 首頁，在搜尋框輸入文字，並讀取頁面顯示的
autocomplete 下拉選項。

## CLI

```powershell
uv run youtube-suggestions "Python" -n 10 --headless
```

參數：

- `query`：要輸入搜尋框的部分關鍵字。
- `-n`、`--limit`：最多取得的建議數量，預設為 10，上限為 20。
- `--headless`：使用無介面的 Chromium。
- `--timeout-ms`：等待頁面及下拉選項的逾時毫秒數，預設為 30,000。
- `--locale`：瀏覽器語系，預設為 `zh-TW`。

## API

啟動服務：

```powershell
uv run uvicorn app.main:app --reload
```

請求：

```text
GET /api/v1/youtube/suggestions?q=Python&limit=10&locale=zh-TW&timeout_ms=30000
```

PowerShell 範例：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/v1/youtube/suggestions?q=Python&limit=10"
```

回應範例：

```json
{
  "query": "Python",
  "count": 2,
  "items": ["python 教學", "python 入門"]
}
```

參數錯誤時回傳 HTTP 422；Playwright、YouTube 頁面或網路發生問題時回傳 HTTP
502。

## 程式位置

- Playwright 邏輯：`app/youtube/suggestions.py`
- CLI：`app/youtube/suggestions_cli.py`
- API route：`app/api/v1/youtube.py`
- 測試：`tests/youtube/test_suggestions.py`、`tests/api/test_youtube.py`
