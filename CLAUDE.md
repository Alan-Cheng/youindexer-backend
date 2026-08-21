# YouIndexer Backend — CLAUDE.md

## About Me
- Role: solo/pair developer (with Alan, GitHub: Alan-Cheng)
- Working here part-time alongside job search; not full-time on this project
- Preferred response language: Traditional Chinese for conversation, English/code comments as needed

## What this is

搜一個產品或主題，找出 YouTube／IG／Threads 上哪些貼文提過、實際講了什麼——不只是標題比對，是內容語意搜尋，並能跳到影片講那句話的那一秒。

## Deeper context lives in the vault, not here

這個 repo 只放程式碼本身需要的東西。更完整的專案脈絡（會議紀錄、產品簡報、決策討論）存在另一個路徑，**新的 Claude session 在這裡開工前建議先讀**：

- `E:/yuki/vault/projects/youindexer/project-brief.md` — 專案簡介（現況、架構、開發流程，最新核對過的版本）
- `E:/yuki/vault/projects/youindexer/meeting-2026-08-16.md` — 與 Alan 的架構討論會議紀錄
- `E:/yuki/vault/projects/youindexer/jira-and-alembic.md` — Jira／Alembic 上手筆記，含這個 repo 用 pgvector 時的已知地雷
- `E:/yuki/vault/projects/youindexer/new-version-deck.html` — 對外/對同事的產品簡報

## Tech stack（實際狀態，非規劃）

- Python `>=3.14`，套件與虛擬環境用 **uv** 管理（不是 pip/venv）
- FastAPI + PostgreSQL + Redis
- 依賴已包含：Alembic（migration，尚未初始化）、Celery（背景任務，尚未串起）、Playwright（因 IG 專用帳號呼叫 API 被擋，改走瀏覽器自動化）
- 目前已有：`app/youtube/`（搜尋＋CLI）、`app/instagram/`、`app/threads/`（client／keyword_search／profile／models／API 路由）
- 尚未開始：DB 持久層（尚無 SQLAlchemy models）、pgvector 語意搜尋、LLM 產品名標準化、前端

## Dev workflow

- 看板：**Jira**，票號格式 `YOUINDEXER-N`
- Git：`master` / `develop`，**禁止直接 push master**，一律開 PR 給 Alan review
- 分支命名對應 Jira 票號（如 `YOUINDEXER-5-ig-threads-public-crawler`）
- Commit message：**Commitizen**（Conventional Commits），有 pre-commit hook 自動檢查，建議用 `uv run cz commit` 互動式輸入
- 首次安裝／日常啟動指令見 `README.md`

## Known landmines（踩過的，別重踩）

- IG 專用帳號直接呼叫 API 會被擋 → 已改走 Playwright 方向
- YouTube 音檔下載：純音訊格式會遇到 403，要抓 `18/best[ext=mp4]` 再用 ffmpeg 抽音軌（Yuki 的另一個專案 Umi 已有現成實作，`E:/yuki/projects/umi/services/youtube_service.py`、`transcription_service.py`，可直接參考搬過來）
- Alembic + pgvector：`CREATE EXTENSION vector` 不會被 autogenerate 自動產生，第一支 migration 要手動加；autogenerate 把「改欄位名」誤判成「刪除＋新增」會導致資料遺失，產出的 migration 一定要人工檢查再 commit
