# 基于TextCNN的智能错题分类系统
# 数据库与业务 API 设计 v1

## 1. 目标与边界

- 目标：支撑 MVP 闭环，完成“录入 -> 自动分类 -> 人工修正 -> 保存 -> 查询 -> 统计”。
- 版本：v1（优先落地 P0/P1，P2 先预留字段）。
- 统一响应：`code/message/data`。

## 2. 数据库设计（建议 SQLite/MySQL 通用）

## 2.1 表结构总览

- `users`：用户信息。
- `questions`：题目主表。
- `question_feedback`：AI 预测与人工修正反馈。
- `incremental_corpus`：增量训练语料。
- `question_review_logs`：掌握状态流转日志。
- `model_versions`：模型版本与指标（P1）。

## 2.2 字段设计

### 表：users

- `id` TEXT PRIMARY KEY
- `username` TEXT NOT NULL UNIQUE
- `password_hash` TEXT NULL
- `role` TEXT NOT NULL DEFAULT 'student'
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

索引建议：

- `idx_users_role (role)`

### 表：questions

- `id` TEXT PRIMARY KEY
- `user_id` TEXT NOT NULL
- `stem` TEXT NOT NULL
- `options_json` TEXT NULL
- `correct_answer` TEXT NULL
- `analysis` TEXT NULL
- `ai_label` TEXT NULL
- `final_label` TEXT NOT NULL
- `confidence` REAL NULL
- `mastery_status` TEXT NOT NULL DEFAULT 'unreviewed'
- `source_type` TEXT NOT NULL DEFAULT 'manual'
- `is_deleted` INTEGER NOT NULL DEFAULT 0
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

外键建议：

- `user_id -> users.id`

索引建议：

- `idx_questions_user_created (user_id, created_at DESC)`
- `idx_questions_final_label (final_label)`
- `idx_questions_mastery_status (mastery_status)`
- `idx_questions_deleted (is_deleted)`

### 表：question_feedback

- `id` TEXT PRIMARY KEY
- `question_id` TEXT NOT NULL
- `user_id` TEXT NOT NULL
- `question_text` TEXT NOT NULL
- `predicted_label` TEXT NOT NULL
- `corrected_label` TEXT NOT NULL
- `is_corrected` INTEGER NOT NULL
- `created_at` DATETIME NOT NULL

外键建议：

- `question_id -> questions.id`
- `user_id -> users.id`

索引建议：

- `idx_feedback_question (question_id)`
- `idx_feedback_created (created_at DESC)`
- `idx_feedback_corrected (is_corrected)`

### 表：incremental_corpus

- `id` TEXT PRIMARY KEY
- `question_text` TEXT NOT NULL
- `label` TEXT NOT NULL
- `source_feedback_id` TEXT NOT NULL
- `write_status` TEXT NOT NULL DEFAULT 'pending'
- `created_at` DATETIME NOT NULL

外键建议：

- `source_feedback_id -> question_feedback.id`

索引建议：

- `idx_corpus_status (write_status)`
- `idx_corpus_created (created_at DESC)`

### 表：question_review_logs

- `id` TEXT PRIMARY KEY
- `question_id` TEXT NOT NULL
- `user_id` TEXT NOT NULL
- `from_status` TEXT NULL
- `to_status` TEXT NOT NULL
- `created_at` DATETIME NOT NULL

外键建议：

- `question_id -> questions.id`
- `user_id -> users.id`

索引建议：

- `idx_review_question (question_id)`
- `idx_review_user_created (user_id, created_at DESC)`

### 表：model_versions（P1）

- `id` TEXT PRIMARY KEY
- `version` TEXT NOT NULL UNIQUE
- `model_path` TEXT NOT NULL
- `metrics_json` TEXT NULL
- `is_active` INTEGER NOT NULL DEFAULT 0
- `created_at` DATETIME NOT NULL

索引建议：

- `idx_model_active (is_active)`

## 2.3 枚举约定

- `role`: `student` | `admin`
- `mastery_status`: `unreviewed` | `reviewed` | `mastered` | `careless`
- `source_type`: `manual` | `import` | `ocr`
- `write_status`: `pending` | `written` | `failed`

## 3. 业务 API 清单 v1

说明：除页面入口外，业务接口统一前缀 `/api/v1`。

## 3.1 AI 与分类

### POST /api/v1/ai/classify

- 作用：仅预测，不落库。
- 请求：

```json
{
  "text": "简述进程与线程的区别"
}
```

- 成功响应：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "label": "operating_system",
    "confidence": 0.97,
    "model_version": "textcnn-v1"
  }
}
```

### POST /api/v1/ai/feedback

- 作用：记录人工修正并写入增量语料任务。
- 请求：

```json
{
  "question_id": "q_xxx",
  "question_text": "简述进程与线程的区别",
  "predicted_label": "computer_network",
  "corrected_label": "operating_system"
}
```

## 3.2 错题录入与管理

### POST /api/v1/questions

- 作用：保存错题（含 AI 标签与最终标签）。
- 请求：

```json
{
  "stem": "简述进程与线程的区别",
  "options": ["A...", "B..."],
  "correct_answer": "A",
  "analysis": "线程共享进程资源...",
  "ai_label": "operating_system",
  "final_label": "operating_system",
  "confidence": 0.97,
  "source_type": "manual"
}
```

### GET /api/v1/questions

- 作用：分页检索。
- 查询参数：
- `page` `size`
- `final_label`
- `mastery_status`
- `keyword`
- `start_date` `end_date`

### GET /api/v1/questions/{id}

- 作用：查看错题详情。

### PATCH /api/v1/questions/{id}

- 作用：编辑题目正文、解析、最终分类。

### PATCH /api/v1/questions/{id}/status

- 作用：更新掌握状态并写入状态日志。
- 请求：

```json
{
  "to_status": "reviewed"
}
```

### DELETE /api/v1/questions/{id}

- 作用：软删除（`is_deleted=1`）。

## 3.3 看板统计

### GET /api/v1/dashboard/subject-distribution

- 作用：各学科错题占比。

### GET /api/v1/dashboard/mastery-overview

- 作用：掌握状态分布。

## 3.4 元数据

### GET /api/v1/labels

- 作用：可选分类标签列表（当前已实现）。

## 4. 实现优先级（建议 1 周内）

- D1-D2：建表与 ORM 模型、迁移脚本。
- D3：`POST /api/v1/ai/classify`、`POST /api/v1/questions`。
- D4：`GET /api/v1/questions`、`PATCH /status`、`GET /questions/{id}`。
- D5：`POST /api/v1/ai/feedback` + `incremental_corpus` 写入。
- D6：看板统计两个接口。
- D7：联调与验收。

## 5. 验收清单

- 录入页可以拿到 AI 预测并保存记录。
- 人工改类会写入 `question_feedback` 与 `incremental_corpus`。
- 列表支持按分类、状态、关键词筛选。
- 看板统计结果与数据库聚合一致。
- 所有接口返回结构一致：`code/message/data`。
