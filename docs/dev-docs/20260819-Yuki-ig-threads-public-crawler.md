# Instagram / Threads 公開貼文爬蟲

實作範圍對應 Story「實作 Instagram 與 Threads 公開貼文爬蟲」：

1. 輸入關鍵字，取得 n 則推薦貼文（Instagram：hashtag/topic 頁面；Threads：搜尋頁面）。
2. 指定 Instagram／Threads 公開帳號，擷取該帳號的公開貼文。

兩個平台都以獨立、匿名的 Playwright Chromium `BrowserContext`讀取頁面，並先實作
共用的 API 回應包裝（`APIResponse`），供之後所有 API 沿用。

---

## PR Description（可直接複製貼到 GitHub PR）

### Summary

實作 Instagram／Threads 公開貼文爬蟲（對應 Jira `YOUINDEXER-5`），並補上專案共用的
API Response Envelope。

- 新增 Instagram／Threads 匿名爬蟲：關鍵字搜尋＋帳號貼文擷取，走 Playwright 讀取
  頁面內嵌 JSON（Threads 搜尋頁因無內嵌 JSON，改用 DOM 啟發式解法）
- 新增 `POST /api/v1/instagram/crawl`、`POST /api/v1/threads/crawl`，service 函式
  為同步函式，可直接被 Celery worker 呼叫
- 新增共用 `APIResponse` 回應包裝＋全域 exception handler（`app/core/`），所有路由
  （含既有 YouTube API）的錯誤格式統一
- 新增已登入 session 產生工具（`scripts/save_login_session.py`），因部分冷門關鍵字
  會被導向登入頁
- 補齊對應單元測試，並更新兩支既有 YouTube 測試以配合新的錯誤回應格式

### Review 請留意

- 這個 PR 也改到 `app/main.py`、`app/config.py`、`tests/api/test_youtube.py` 這幾支
  develop 上你也動過的檔案——這是本機 rebase 到最新 develop 時處理衝突留下的結果，
  這裡看到的已經是 rebase 後的版本。
- 全域 exception handler 會讓 `/youtube/search`、`/youtube/keyword-suggestions` 的
  錯誤回應格式從 `{"detail": ...}` 變成 `{"success": false, "message": ...}`，這是
  有意的架構改動（對應 Jira memo 要求的共用 Response Model），已同步更新對應測試，
  詳見下方「對既有 YouTube API 的影響」一節。
- Instagram／Threads 目前都是匿名讀取，不需要登入即可用；已登入 session 是選配
  （`INSTAGRAM_STORAGE_STATE_PATH`／`THREADS_STORAGE_STATE_PATH`），未設定時行為
  不變。
- 兩個平台都只做「讀取第一批公開內容」，無法捲動載入更多，回傳數量可能少於
  `limit`。
- Alan 分支 merge 進來後，比照他的要求把 `alias`／`me`／`youtube`／`auth` 幾支
  路由能包的都包上 `APIResponse`，2 支 SSE ＋ 1 支 204 端點刻意先不動，細節與
  待討論項目見下方「補上 Alan 分支（YOUINDEXER-6 merge 後）的 envelope」一節。

### Testing

- `uv run pytest` 全數通過
- 手動打 `POST /api/v1/instagram/crawl`（`{"mode": "keyword", "keyword": "cats",
  "limit": 5}`）驗證實際能抓到資料、回應格式正確

### 詳細設計

見本文件其餘章節（資料來源與擷取方式、登入牆處理、正式環境注意事項）。

---

## APIResponse 回應包裝

`app/core/response.py` 提供類似 Spring Boot `ApiResponse<T>` 的通用包裝：

```json
{
  "success": true,
  "code": 200,
  "message": "OK",
  "data": { ... },
  "errors": null,
  "timestamp": "2026-08-19T00:00:00Z"
}
```

`app/core/exception_handlers.py` 註冊了全域的 `HTTPException` 與
`RequestValidationError` handler，因此任何路由（包含既有的 `/youtube/search`）
主動 `raise HTTPException(...)` 或參數驗證失敗時，都會回傳同樣結構的錯誤內容，
`success=false`、`errors` 帶有詳細訊息陣列。`/health` 也已套用此包裝；健康檢查
失敗時維持 HTTP 503，且 envelope 的 `code` 同樣為 503。

### 對既有 YouTube API 的影響（review 時請留意）

這個 handler 是註冊在 `main.py` 最外層，對全站生效，不只是 Instagram／Threads
的路由。上線後 `app/api/v1/youtube.py` 既有端點的錯誤回應格式也會從 FastAPI
預設的 `{"detail": ...}` 變成上面這個 `APIResponse` 格式，因此同步更新了
`tests/api/test_youtube.py` 裡兩個原本斷言 `{"detail": ...}` 的測試
（`test_youtube_search_maps_playwright_failure_to_bad_gateway`、
`test_youtube_suggestions_maps_failure_to_bad_gateway`），改成斷言新格式。
這不是 YouTube 功能邏輯的改動，純粹是回應格式統一後的斷言跟著更新。

### 補上 Alan 分支（YOUINDEXER-6 merge 後）的 envelope（review 請留意）

Alan merge 進來的 `app/api/v1/{alias,me,youtube,auth}.py` 這幾支路由原本沒有套用
`APIResponse`，他要求比照辦理。這個 PR 已經把「可以直接改」的端點都補上了：

- `alias.py`：`POST /aliases`（1/1）
- `me.py`：`GET /me/search-history`、`DELETE /me/search-history/{task_id}`（2/3）
- `youtube.py`：`keyword-suggestions`、`search-metadata`、`POST search-jobs`、
  `GET search-jobs/{task_id}`、`POST videos/{video_id}/index`、
  `GET videos/{video_id}/index`、`subtitles/search`（7/8）
- `auth.py`：`google/login`、`google/callback`、`refresh`、`GET /me`、
  `auth/verify`（5/5）

對應改動 `response_model=APIResponse[X]`、回傳值改成 `APIResponse.ok(...)`，並同步
更新 `tests/alias/test_api.py`、`tests/api/test_me.py`、`tests/api/test_auth.py`、
`tests/api/test_youtube.py` 裡對應斷言（`response.json()["data"]`／
`response.data.xxx`）。

**刻意維持非 envelope 格式：**

- `GET /me/search-history/events`、`GET /youtube/search-jobs/{task_id}/events`
  （SSE）：兩支都是用 `text/event-stream` 直接串原始 JSON snapshot，套 envelope
  等於改動前端已經在吃的 SSE payload 格式，屬於破壞性改動，這次先不動。
- `DELETE /me/search-history/{task_id}`：已改為 HTTP 200，回傳成功 envelope，`data` 為
  `null`；找不到項目時仍由全域 handler 回傳錯誤 envelope。
- 附帶發現：`GET /youtube/search-jobs/{task_id}`（已包 envelope）跟它的 SSE 版本
  `.../events`（未包）現在回傳的 body 形狀不一樣了——原本
  `test_job_api_and_sse_snapshot_share_response_body` 這支測試斷言兩者「完全一致」，
  已經改成只比對 envelope 內層的 `data`，但這代表 API 回應格式上兩者已經不對稱，
  需要跟 Alan／前端確認 SSE 之後要不要也改格式，或是维持現狀、由前端各自處理。

## 資料來源與擷取方式

Instagram 與 Threads 的登出頁面雖然畫面上疊了一層「請登入」的彈窗，但畫面背後
仍然渲染了第一批公開貼文，因此兩個服務都**不需要登入**即可取得資料，但都只能
取得該次頁面載入時的第一批內容，無法透過捲動取得更多（捲動需要已登入的
GraphQL 請求）。回傳數量因此可能少於呼叫時指定的 `limit`。

### Instagram（`app/instagram/`）

Instagram 的個人檔案頁與 hashtag／topic 頁面，都會把貼文資料以
`<script type="application/json">` 內嵌在 HTML 中（Meta 的 Relay
`ScheduledServerJS` payload），而不是只能從畫面 DOM 解析。`client.py` 會：

1. 用正規表達式抓出所有 `application/json` 的 script 內容並 `json.loads`。
2. 遞迴尋找符合「貼文節點」特徵的 dict（帶有 `code`，且有 `caption` 或
   `display_uri`），忽略其餘的巢狀包裝結構。
3. 依 `code`（貼文 shortcode）去重。

這個作法比直接解析畫面 DOM 穩定，因為 DOM 使用的是 Meta 自動產生、沒有語意的
atomic CSS class（例如 `x1i10hfl xjbqb8w ...`），完全不能作為穩定的 selector；
內嵌 JSON 的欄位名稱（`code`、`caption.text`、`display_uri`、`user.username`）
相對穩定，因為它們對應到 GraphQL schema。

- `search_instagram_posts(keyword, limit)`：把關鍵字正規化成 hashtag
  （移除非文字字元），呼叫 `/explore/tags/<tag>/`（會被導向
  `/popular/<tag>/`），回傳該 hashtag 目前代表性的貼文。**這不是全文搜尋**，
  是 Instagram 官方認定的熱門貼文，且結果不保證全部與關鍵字語意相關。
- `fetch_instagram_profile_posts(username, limit)`：讀取 `/<username>/`
  個人檔案頁的貼文格。

### Threads（`app/threads/`）

Threads 個人檔案頁一樣有內嵌 JSON（`__typename: "XDTThreadItem"`），欄位包含
`post.code`、`post.caption.text`、`post.user.username`、`post.taken_at`
（Unix timestamp）、`post.like_count`、`post.image_versions2.candidates`。
`fetch_threads_profile_posts` 直接複用同樣的 JSON 擷取策略。

Threads 的搜尋結果頁（`/search?q=...`）**沒有**內嵌 JSON，內容是在瀏覽器端
以 XHR 動態渲染，因此 `search_threads_posts` 改用 `page.evaluate()` 直接讀取
畫面 DOM：找出所有貼文永久連結 `a[href^="/@user/post/"]`（內含
`<time datetime>`），再從該連結往上找最近一個含有貼文內文 `span[dir="auto"]`
的祖先容器，排除作者名稱、時間文字、按讚/留言數字、以及「Translate／更多」等
UI 控制文字後取第一個符合的文字當作內文。**這是啟發式解法**，比 JSON 擷取更
容易因為 Threads 前端調整而失準（例如可能誤取到頻道標籤而非貼文內容），需要
持續以整合測試監控。

## 登入牆與已登入模式

實測發現 Instagram 的匿名登入牆並非全有全無：常見／Instagram 官方整理過的
hashtag（如 `cats`）有公開的 `popular` 彙整頁，但冷門或特定品牌／產品名稱的
hashtag 常常會直接導向 `/accounts/login/`，回傳 `InstagramLoginRequiredError`
（HTTP 502）。這種情況下唯一的解法是改用已登入的 session。

兩個服務模組的 `open_page()` 都支援 `storage_state_path` 參數，API 層
（`app/api/v1/instagram.py`、`app/api/v1/threads.py`）會自動帶入
`settings.instagram_storage_state_path` / `settings.threads_storage_state_path`，
分別讀取環境變數 `INSTAGRAM_STORAGE_STATE_PATH` / `THREADS_STORAGE_STATE_PATH`
（見 `app/config.py`、`.env.example`）。**未設定時預設維持匿名模式**，行為與
之前完全相同。

### 產生已登入 session

```bash
uv run python scripts/save_login_session.py instagram out/instagram_state.json
uv run python scripts/save_login_session.py threads out/threads_state.json
```

這會開一個真的（非 headless）Chromium 視窗，停在該平台的登入頁，讓你自己在
視窗裡手動輸入帳密登入——腳本本身完全不經手、不儲存帳號密碼。登入完成、看到
自己的 feed／個人檔案後，回到終端機按 Enter，就會把該次登入的 session
（cookies）存成指定路徑的 JSON 檔。

### 重要安全事項

- **務必使用專門申請的拋棄式帳號**，不要用主帳號。用自動化程式操作已登入帳號
  違反 Instagram／Threads 服務條款，帳號有被要求二次驗證（checkpoint）或停權
  的風險；用拋棄式帳號可以把風險隔離在該帳號上。
- 產生出來的 `storage_state*.json` **等同該帳號的登入憑證**，任何拿到這個檔案
  的人都能直接以該帳號登入。已加入 `.gitignore`（`*storage_state*.json`、
  `/out/`），絕對不要手動加回 git，也不要烤進 Docker image。
- 部署到雲端伺服器時，應透過該平台的 secret／環境變數注入機制，在部署當下把
  檔案放到伺服器上，並設定 `INSTAGRAM_STORAGE_STATE_PATH` /
  `THREADS_STORAGE_STATE_PATH` 指向該路徑，而不是把檔案打包進程式碼庫或映像檔。
- 這不是「登入一次、永久有效」：session 可能過期，或因為改從雲端伺服器的 IP
  使用（跟登入當下的裝置/地點不同）而被判定為可疑並要求重新驗證，屆時就需要
  重新執行上面的腳本產生新的 session 檔。
- 目前的自動化測試都只驗證匿名模式；已登入模式尚未寫自動化測試（需要真實帳號
  才能測試，不適合放進 CI）。

## HTTP API

啟動 FastAPI：

```powershell
uv run uvicorn app.main:app --reload
```

兩個平台都只有一個「觸發單次擷取」的 POST 端點，body 用 `mode` 區分關鵼字或
帳號模式，方便未來 Cron Job／worker 直接呼叫背後的 Service 函式，不用透過 HTTP：

```http
POST /api/v1/instagram/crawl
POST /api/v1/threads/crawl
```

關鍵字模式：

```json
{ "mode": "keyword", "keyword": "cats", "limit": 10 }
```

帳號模式：

```json
{ "mode": "profile", "username": "instagram", "limit": 10 }
```

PowerShell 範例：

```powershell
$body = @{ mode = "keyword"; keyword = "cats"; limit = 5 } | ConvertTo-Json
Invoke-RestMethod -Method Post `
    -Uri "http://127.0.0.1:8000/api/v1/instagram/crawl" `
    -ContentType "application/json" -Body $body
```

成功時回傳 HTTP 200，`data` 內容為：

```json
{
  "mode": "keyword",
  "query": "cats",
  "count": 3,
  "items": [
    {
      "post_id": "...",
      "url": "...",
      "username": "...",
      "caption": "...",
      "thumbnail_url": "...",
      "is_video": true
    }
  ]
}
```

參數錯誤（例如空白關鍵字、帳號格式不合法、`limit` 超出 1–50）回傳 HTTP 422；
Playwright 或平台端擷取失敗（包含判定為需要登入）回傳 HTTP 502。所有回應都是
`APIResponse` 包裝格式（見上）。

## Python 呼叫方式（Celery worker）

服務函式是同步函式，可以直接在 Celery task 中呼叫：

```python
from app.instagram import search_instagram_posts
from app.threads import fetch_threads_profile_posts

ig_posts = search_instagram_posts("cats", 10)
threads_posts = fetch_threads_profile_posts("zuck", 10)
```

FastAPI 的 async handler 一律透過 `asyncio.to_thread()` 呼叫，避免阻塞
event loop（見 `app/api/v1/instagram.py`、`app/api/v1/threads.py`）。

## 正式環境注意事項

- 建議限制同時啟動的 Chromium 數量，避免 worker 耗用過多記憶體與 CPU。
- 建議快取相同關鍵字/帳號的擷取結果，減少重複請求。
- 高頻率或大量自動化請求可能觸發 Instagram／Threads 的風控或登入牆。
- 兩個平台的網頁都不是穩定的公開 API，內嵌 JSON 結構與畫面 DOM 都可能隨時調整，
  應建立定期的整合測試監控是否仍能正常解析（尤其 Threads 搜尋頁的 DOM 啟發式
  解法最容易失準）。
- `InstagramLoginRequiredError` / `ThreadsLoginRequiredError` 目前是以「完全
  抓不到任何貼文」為判斷依據，無法區分「真的被要求登入」與「該帳號本來就沒有
  公開貼文」，如需更精確判斷可再補上頁面文案偵測。
- 正式部署前應自行評估 Instagram／Threads 服務條款及資料使用規範。
