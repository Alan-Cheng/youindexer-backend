# YouIndexer Backend

YouIndexer 後端服務，使用 FastAPI、PostgreSQL 與 Redis。Python 套件及虛擬環境由 [uv](https://docs.astral.sh/uv/) 管理。

## 本地開發需求

- uv
- Docker Desktop（需包含 Docker Compose）
- Git

專案目前指定 Python `>=3.14`；執行 `uv sync` 時，uv 會使用或下載相容的 Python 版本。

## 啟動方式

1. 安裝並同步 Python 依賴：

   PowerShell：

   ```powershell
   uv sync
   ```

   Bash：

   ```bash
   uv sync
   ```

2. 建立本地環境變數檔：

   PowerShell：

   ```powershell
   Copy-Item .env.example .env
   ```

   Bash：

   ```bash
   cp .env.example .env
   ```

   預設設定已可直接連到本機 Docker Compose 服務；如本機的 `5432` 或 `6379` 已被占用，可在 `.env` 修改對外連接埠及連線 URL。

3. 啟動 PostgreSQL 與 Redis：

   PowerShell：

   ```powershell
   docker compose up -d --wait
   ```

   Bash：

   ```bash
   docker compose up -d --wait
   ```

4. 啟動 FastAPI 開發伺服器：

   PowerShell：

   ```powershell
   uv run uvicorn app.main:app --reload
   ```

   Bash：

   ```bash
   uv run uvicorn app.main:app --reload
   ```

5. 確認服務：

   - Health API：<http://127.0.0.1:8000/api/v1/health>
   - Swagger UI：<http://127.0.0.1:8000/docs>
   - ReDoc：<http://127.0.0.1:8000/redoc>
   - OpenAPI JSON：<http://127.0.0.1:8000/openapi.json>

當 FastAPI、PostgreSQL 與 Redis 都正常時，health API 會回傳 HTTP 200：

```json
{
  "status": "healthy",
  "postgres": { "status": "up", "detail": null },
  "redis": { "status": "up", "detail": null }
}
```

若 PostgreSQL 或 Redis 無法連線，health API 會回傳 HTTP 503，並將對應服務標記為 `down`。

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

上述指令會保留 PostgreSQL 與 Redis 的 named volumes。若確定要一併刪除本地資料，才使用：

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
