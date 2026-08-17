# YouIndexer Backend

YouIndexer 後端服務，使用 FastAPI、PostgreSQL、Redis、MinIO 與 OpenSearch。Python 套件及虛擬環境由 [uv](https://docs.astral.sh/uv/) 管理。

## 本地開發需求

- uv
- Docker Desktop（需包含 Docker Compose）
- Git

專案目前指定 Python `>=3.14`；執行 `uv sync` 時，uv 會使用或下載相容的 Python 版本。

## 首次安裝開發環境

Clone 專案後，進入專案根目錄並依序執行以下指令。

### PowerShell

```powershell
# 1. 建立虛擬環境並安裝鎖定的依賴
uv sync

# 2. 建立本地環境變數檔
Copy-Item .env.example .env

# 3. 安裝 commit message 檢查 hook（每個 clone 只需執行一次）
uv run pre-commit install --hook-type commit-msg

# 4. 啟動所有基礎服務，並等待服務就緒
docker compose up -d --wait
```

### Bash

```bash
# 1. 建立虛擬環境並安裝鎖定的依賴
uv sync

# 2. 建立本地環境變數檔
cp .env.example .env

# 3. 安裝 commit message 檢查 hook（每個 clone 只需執行一次）
uv run pre-commit install --hook-type commit-msg

# 4. 啟動所有基礎服務，並等待服務就緒
docker compose up -d --wait
```

預設 `.env.example` 可直接連到 Docker Compose 服務。如本機的預設連接埠已被占用，請修改 `.env` 中對應的對外連接埠與連線 URL。

最後啟動 FastAPI 開發伺服器：

```bash
uv run uvicorn app.main:app --reload
```

## 日常開發啟動

完成首次安裝後，日常開發只需執行：

```bash
docker compose up -d --wait
uv run uvicorn app.main:app --reload
```

`uvicorn` 會持續佔用目前的終端；也可以開兩個終端，分別查看基礎服務與 FastAPI 的執行狀態。

## 確認服務

- Health API：<http://127.0.0.1:8000/api/v1/health>
- Swagger UI：<http://127.0.0.1:8000/docs>
- ReDoc：<http://127.0.0.1:8000/redoc>
- OpenAPI JSON：<http://127.0.0.1:8000/openapi.json>
- MinIO S3 API：<http://127.0.0.1:9000>
- MinIO Console：<http://127.0.0.1:9001> (`minioadmin` / `minioadmin`)
- OpenSearch REST API：<http://127.0.0.1:9200>
- OpenSearch Dashboards：<http://127.0.0.1:5601>

MinIO 使用 Docker named volume `minio_storage` 保留物件資料。預設 bucket 為 `youindexer`，字幕 Worker 在第一次儲存物件時會自動建立。

OpenSearch 與 OpenSearch Dashboards 為單節點本地開發設定，已停用安全外掛，不應直接用於生產環境。為避免佔用過多本機資源，OpenSearch 預設限制為 1 CPU 與 1 GiB 記憶體，Dashboards 限制為 0.5 CPU 與 512 MiB 記憶體；可在 `.env` 中調整對應的 `OPENSEARCH_*` 變數。

## YouTube 字幕 Worker

`transcription-worker` 會從 Celery `transcription` queue 取得任務，只擷取繁體中文（`zh-TW` / `zh-Hant`）與英文字幕。它會優先使用影片作者提供的字幕，其次使用 YouTube 自動字幕或翻譯軌，不會下載影片。

可用以下指令發送單筆測試任務：

```bash
uv run celery -A app.worker.celery_app:celery_app call \
  app.worker.tasks.store_youtube_subtitles \
  --args='["https://www.youtube.com/watch?v=cjdIkl8T7Vc"]'
```

字幕會正規化為毫秒時間軸 JSON，並寫入：

```text
youindexer/transcripts/{video_id}/zh-TW.json
youindexer/transcripts/{video_id}/en.json
```

沒有任何可用字幕時，任務會正常完成並回傳 `subtitle_unavailable`，不會重試或執行 STT。若 YouTube 要求登入，可在 `.env` 設定 Netscape 格式的 `YOUTUBE_COOKIES_FILE`；此路徑還需額外映射到 Worker container。

當 FastAPI、PostgreSQL 與 Redis 都正常時，health API 會回傳 HTTP 200：

```json
{
  "status": "healthy",
  "postgres": { "status": "up", "detail": null },
  "redis": { "status": "up", "detail": null }
}
```

若 PostgreSQL 或 Redis 無法連線，health API 會回傳 HTTP 503，並將對應服務標記為 `down`。

## Commit message 格式

專案使用 Commitizen 檢查 [Conventional Commits](https://www.conventionalcommits.org/) 格式。完成首次安裝後，每次 `git commit` 都會自動檢查訊息。建議使用互動式指令，不需要背格式：

```bash
uv run cz commit
```

手動輸入時使用：

```text
<type>(<scope>): <description>
```

- `type`：變更種類，必填。
- `scope`：影響範圍，選填，例如 `api`、`health`、`redis`。
- `description`：簡短說明，必填。

常用 type：

| Type | 使用時機 |
| --- | --- |
| `feat` | 新功能。 |
| `fix` | 修正錯誤。 |
| `docs` | 只修改文件。 |
| `refactor` | 不改變外部行為的程式重構。 |
| `test` | 新增或修改測試。 |
| `chore` | 依賴、設定或其他維護工作。 |
| `perf` | 效能改善。 |
| `ci` | CI/CD 設定。 |
| `build` | 建置系統或外部依賴變更。 |

範例：

```text
feat(health): add database connectivity check
fix(redis): handle connection timeout
docs(readme): add local setup guide
chore(deps): add commitizen
```

提交前也可手動檢查最近一筆 commit：

```bash
uv run cz check --rev-range HEAD
```

## 停止本地服務

先在 FastAPI 的終端按 `Ctrl+C`，再停止基礎服務：

PowerShell：

```powershell
docker compose down
```

Bash：

```bash
docker compose down
```

上述指令會保留 PostgreSQL、Redis、MinIO 與 OpenSearch 的 named volumes。若確定要一併刪除本地資料，才使用：

PowerShell：

```powershell
docker compose down -v
```

Bash：

```bash
docker compose down -v
```

## 開發文件

- [專案初始化紀錄](docs/dev-docs/20260815-Alan-init.md)
