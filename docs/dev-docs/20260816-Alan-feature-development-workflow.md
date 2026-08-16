# 功能開發建立規則

所有功能開發皆須綁定 Jira Ticket，並依照以下流程進行。

## 開發流程

1. 從 Jira Ticket 建立功能分支。
2. 在功能分支完成開發後，合併至 `develop` 分支進行整合測試。
3. `develop` 測試完成後，建立由 `develop` 合併至 `master` 的 Pull Request。
4. Pull Request 審查通過並合併至 `master`，功能才視為完成。

不得跳過 `develop` 的整合測試，或直接將功能分支合併至 `master`。

## Jira 自動狀態管理

Jira 會依 Git 操作自動更新 Ticket 狀態，不需要手動調整：

| Git 操作 | Jira Ticket 狀態 |
| --- | --- |
| 從 Jira Ticket 建立分支 | `IN PROGRESS` |
| 建立 Pull Request | `IN REVIEW` |
| Pull Request 合併完成 | `DONE` |

為確保 Jira 能正確關聯分支與 Pull Request，分支名稱、commit 與 Pull Request 標題應包含 Jira Ticket 編號。

## 流程摘要

```text
Jira Ticket
  → 建立功能分支（IN PROGRESS）
  → 完成功能開發
  → 合併至 develop 並測試
  → develop 對 master 建立 PR（IN REVIEW）
  → PR 審查及合併（DONE）
```
