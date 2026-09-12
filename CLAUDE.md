# YouIndexer Backend — CLAUDE.md

## About Me
- Role: solo/pair developer (with Alan, GitHub: Alan-Cheng)
- Working here part-time alongside job search; not full-time on this project
- Preferred response language: Traditional Chinese for conversation, English/code comments as needed

## What this is

搜一個產品或主題，找出 YouTube／IG／Threads 上哪些貼文提過、實際講了什麼——不只是標題比對，是內容語意搜尋，並能跳到影片講那句話的那一秒。

## Deeper context lives in the vault, not here

這個 repo 只放程式碼本身需要的東西。更完整的專案脈絡（會議紀錄、產品簡報、決策討論）存在另一個路徑，**新的 Claude session 在這裡開工前建議先讀**：

- `E:/yuki/vault/projects/youindexer/project-brief.md` — 專案簡介（現況、架構、開發流程；2026-08-30 起以這份為準，本檔 Tech stack 只是摘要）
- `E:/yuki/vault/projects/youindexer/meeting-2026-08-16.md` — 與 Alan 的架構討論會議紀錄
- `E:/yuki/vault/projects/youindexer/jira-and-alembic.md` — Jira／Alembic 上手筆記
- `E:/yuki/vault/projects/youindexer/new-version-deck.html` — 對外/對同事的產品簡報

## ⚠️ 開工前先確認在對的 repo／路徑

本機曾經混著一套完全無關的舊版 v1 sandbox（`E:/yuki/projects/youindexer/`，Java Spring + vue-cli，接 MariaDB/Elasticsearch），曾經有 session 誤把它當成正式專案動工、還開錯 5 張 Jira 卡。**這個 repo（`youindexer-backend`）才是正式在開發的專案**，remote 指向 `Alan-Cheng/youindexer-backend`；舊版已封存到 `E:/yuki/projects/_archive/`。正式前端另在 `E:/yuki/projects/youindexer-frontend/`（remote: `Alan-Cheng/youindexer-frontend`）。`roce59427/*` 開頭的 GitHub repo 是舊版 v1 的個人 repo，跟正式功能無關，不要往那邊 push。

## Tech stack（2026-08-30 核對，非規劃）

- Python `>=3.14`，套件與虛擬環境用 **uv** 管理（不是 pip/venv）
- FastAPI + PostgreSQL + Redis，另加 **MinIO**（存逐字稿 JSON）、**OpenSearch**（搜尋索引，取代原計畫的 pgvector）
- Alembic：已在用，schema 由它管理
- Celery：**已串起且在跑**（`transcription-worker`、`index-worker`）
- Playwright：因 IG 專用帳號呼叫 API 被擋，改走瀏覽器自動化
- 已完成：YouTube 逐字稿抓取＋索引管線（含 `start_ms`/`end_ms` 跳轉）、YouTube 搜尋 API（含 SSE）、LLM 產品名/暱稱標準化（`app/alias/service.py`，Gemini）、Auth/OAuth（`app/auth/`）
- Instagram／Threads：有爬蟲（`app/instagram/`、`app/threads/`），但**還沒進 OpenSearch、還不能搜**（YOUINDEXER-22）
- 尚未開始：跨來源統一搜尋（YOUINDEXER-23）、IG/Threads 深連結、AI 摘要功能（YOUINDEXER-24）、公開部署
- **pgvector：2026-08-30 確認暫不做**——alias 服務＋OpenSearch 關鍵字/jieba 分詞已涵蓋核心痛點

## Dev workflow

- 看板：**Jira**，票號格式 `YOUINDEXER-N`
- Git：`master` / `develop`，**禁止直接 push master**，一律開 PR 給 Alan review
- 分支命名對應 Jira 票號（如 `YOUINDEXER-5-ig-threads-public-crawler`）
- Commit message：**Commitizen**（Conventional Commits），有 pre-commit hook 自動檢查，建議用 `uv run cz commit` 互動式輸入
- 首次安裝／日常啟動指令見 `README.md`

## Known landmines（踩過的，別重踩）

- IG 專用帳號直接呼叫 API 會被擋 → 已改走 Playwright 方向
- YouTube 音檔下載：純音訊格式會遇到 403，要抓 `18/best[ext=mp4]` 再用 ffmpeg 抽音軌（Yuki 的另一個專案 Umi 已有現成實作，`E:/yuki/projects/umi/services/youtube_service.py`、`transcription_service.py`，可直接參考搬過來）
- Alembic：autogenerate 把「改欄位名」誤判成「刪除＋新增」會導致資料遺失，產出的 migration 一定要人工檢查再 commit（pgvector 相關的 `CREATE EXTENSION vector` 手動加入 migration 這條已不適用，因為 pgvector 目前不用）
