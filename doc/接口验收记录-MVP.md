# 接口验收记录（MVP）

## 1. 验收环境

- 日期：2026-04-12
- 服务地址：http://127.0.0.1:8000
- 回归脚本：Tools/api_smoke_test.ps1
- 结果：通过

回归关键输出：

- question_id=q_636dbd636bf8446484e5dce31d54c707
- feedback_id=fb_6a74462508d641d1abfe5c658f5e5183
- dashboard_total=9

## 2. 认证与用户隔离

### 2.1 登录

请求：

```http
POST /api/v1/auth/login
Content-Type: application/json

{"username":"demo_user"}
```

响应样例：

```json
{
  "code": 0,
  "message": "登录成功",
  "data": {
    "token_type": "Bearer",
    "access_token": "demo-token",
    "user": {"id": "demo_user", "role": "student"}
  }
}
```

## 3. 错题管理闭环接口

### 3.1 创建题目

请求：

```http
POST /api/v1/questions
Authorization: Bearer demo-token
Content-Type: application/json

{
  "stem": "smoke_20260412_xxx",
  "analysis": "api smoke test",
  "ai_label": "operating_system",
  "final_label": "operating_system",
  "confidence": 0.97,
  "source_type": "manual"
}
```

响应样例：

```json
{"code":0,"message":"保存成功","data":{"id":"q_xxx"}}
```

### 3.2 查询题目详情（新增）

请求：

```http
GET /api/v1/questions/q_xxx
Authorization: Bearer demo-token
```

响应样例：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "q_xxx",
    "stem": "smoke_20260412_xxx",
    "analysis": "api smoke test",
    "final_label": "operating_system",
    "mastery_status": "unreviewed"
  }
}
```

### 3.3 编辑题目（新增）

请求：

```http
PATCH /api/v1/questions/q_xxx
Authorization: Bearer demo-token
Content-Type: application/json

{"analysis":"patched by smoke","final_label":"operating_system"}
```

响应样例：

```json
{"code":0,"message":"题目更新成功","data":{"id":"q_xxx"}}
```

### 3.4 软删除题目（新增）

请求：

```http
DELETE /api/v1/questions/q_xxx
Authorization: Bearer demo-token
```

响应样例：

```json
{"code":0,"message":"题目已删除","data":{"id":"q_xxx"}}
```

删除后验证：

```http
GET /api/v1/questions/q_xxx
Authorization: Bearer demo-token
```

返回 404（符合预期）。

## 4. 增量语料落盘任务

### 4.1 提交反馈

请求：

```http
POST /api/v1/ai/feedback
Authorization: Bearer demo-token
Content-Type: application/json

{
  "question_id":"q_xxx",
  "question_text":"smoke_20260412_xxx",
  "predicted_label":"computer_network",
  "corrected_label":"operating_system"
}
```

### 4.2 管理员触发落盘

请求：

```http
POST /api/v1/admin/corpus/flush
Authorization: Bearer admin-token
```

状态查询：

```http
GET /api/v1/admin/corpus/flush/status
Authorization: Bearer admin-token
```

验收点：

- pending 记录会被消费
- 成功写入标记 written
- 失败记录标记 failed，并保存失败原因

## 5. 模型运维最小能力

### 5.1 分类返回生效版本

请求：

```http
POST /api/v1/ai/classify
Content-Type: application/json

{"text":"process and thread difference"}
```

响应样例：

```json
{"code":0,"message":"ok","data":{"label":"operating_system","confidence":0.97,"model_version":"textcnn-v1"}}
```

### 5.2 版本列表与切换

请求：

```http
GET /api/v1/admin/models/versions
Authorization: Bearer admin-token
```

```http
PATCH /api/v1/admin/models/active
Authorization: Bearer admin-token
Content-Type: application/json

{"version_name":"textcnn-v1"}
```

## 6. 前端联调结论

- 录入页：已实现 classify -> 可改类 -> 保存。
- 列表页：已实现筛选 + 分页 + 状态修改 + 删除。
- 看板页：已实现学科分布图。
- 用户流程：登录后可完成端到端闭环，无断点。

## 7. 截图留存说明

- 本次在终端完成自动化回归并通过。
- 若需答辩材料中的截图，建议截取：
  - smoke 脚本 12/12 全通过终端画面
  - 浏览器录入页保存成功画面
  - 看板页分布图画面
