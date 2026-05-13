const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, Header, Footer, AlignmentType, HeadingLevel, BorderStyle,
  WidthType, ShadingType,
} = require("docx");

// =============================================================
// 武汉工程大学本科毕业论文格式
// =============================================================

// 页边距:上2.5cm 下2.0cm 左2.5cm 右2.0cm  (1cm≈567 DXA)
const MG_TOP = 1417, MG_BOTTOM = 1134, MG_LEFT = 1417, MG_RIGHT = 1134;
const PAGE_W = 11906, PAGE_H = 16838;    // A4
const CONTENT_W = PAGE_W - MG_LEFT - MG_RIGHT; // 9355

const FONT_BODY = "SimSun";      // 宋体
const FONT_HEADING = "SimHei";   // 黑体
const SIZE_BODY = 24;            // 小四 12pt (half-points)
const SIZE_CAPTION = 21;         // 五号 10.5pt
const SIZE_H1 = 28;              // 四号 14pt (一级标题)
const SIZE_H2 = 24;              // 小四 12pt (二级标题, 黑体加粗)

const LINE_SPACING = 360;        // 1.5倍行距
const FIRST_INDENT = 480;        // 首行缩进2字符 (12pt*2=24pt, 24pt*20twips=480)

// 三线表边框
const THICK = { style: BorderStyle.SINGLE, size: 6, color: "000000" };
const THIN  = { style: BorderStyle.SINGLE, size: 2, color: "000000" };
const NONE  = { style: BorderStyle.NONE };
const NOB   = { top: NONE, bottom: NONE, left: NONE, right: NONE };

function headerBorders(i, len, isHeader) {
  const topLine = isHeader ? THICK : NONE;   // 表头行顶粗线
  const botLine = isHeader ? THIN : NONE;    // 表头行底细线
  return { top: topLine, bottom: botLine, left: NONE, right: NONE };
}

function lastRowBorders(i, len) {
  return { top: NONE, bottom: THICK, left: NONE, right: NONE };  // 末行底粗线
}

// =============================================================
// 辅助函数
// =============================================================

function body(text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    indent: { firstLine: FIRST_INDENT },
    spacing: { line: LINE_SPACING, lineRule: "auto" },
    children: [new TextRun({ text, font: FONT_BODY, size: SIZE_BODY })],
  });
}

function bodyNoIndent(text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: LINE_SPACING, lineRule: "auto" },
    children: [new TextRun({ text, font: FONT_BODY, size: SIZE_BODY })],
  });
}

function bodyRich(runs) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    indent: { firstLine: FIRST_INDENT },
    spacing: { line: LINE_SPACING, lineRule: "auto" },
    children: runs,
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    alignment: AlignmentType.LEFT,
    spacing: { before: 300, after: 200, line: LINE_SPACING },
    children: [new TextRun({ text, font: FONT_HEADING, size: SIZE_H1, bold: true })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    alignment: AlignmentType.LEFT,
    spacing: { before: 240, after: 120, line: LINE_SPACING },
    children: [new TextRun({ text, font: FONT_HEADING, size: SIZE_H2, bold: true })],
  });
}

function subtitleBold(text) {
  // 替代三级标题: 黑体小四加粗, 无缩进, 作为段落前导
  return new Paragraph({
    alignment: AlignmentType.LEFT,
    indent: { firstLine: FIRST_INDENT },
    spacing: { before: 180, after: 60, line: LINE_SPACING },
    children: [new TextRun({ text, font: FONT_HEADING, size: SIZE_BODY, bold: true })],
  });
}

function figCaption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 60, after: 180, line: LINE_SPACING },
    children: [new TextRun({ text, font: FONT_BODY, size: SIZE_CAPTION })],
  });
}

function tblCaption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 200, after: 60, line: LINE_SPACING },
    children: [new TextRun({ text, font: FONT_BODY, size: SIZE_CAPTION, bold: true })],
  });
}

function monoRun(text) {
  return new TextRun({ text, font: "Consolas", size: SIZE_BODY });
}

// =============================================================
// 三线表生成
// =============================================================

function makeThreeLineTable(caption, head, widths, rows) {
  const elems = [];
  elems.push(tblCaption(caption));

  // 表头行: 顶粗 + 底细
  elems.push(new TableRow({
    children: head.map((h, i) => new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      margins: { top: 40, bottom: 40, left: 80, right: 80 },
      borders: { top: THICK, bottom: THIN, left: NONE, right: NONE },
      children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { line: 300 },
        children: [new TextRun({ text: h, font: FONT_BODY, size: SIZE_CAPTION, bold: true })],
      })],
    })),
  }));

  // 数据行
  rows.forEach((row, ri) => {
    const isLast = ri === rows.length - 1;
    elems.push(new TableRow({
      children: row.map((cell, ci) => new TableCell({
        width: { size: widths[ci], type: WidthType.DXA },
        margins: { top: 40, bottom: 40, left: 80, right: 80 },
        borders: isLast
          ? { top: NONE, bottom: THICK, left: NONE, right: NONE }
          : NOB,
        children: [new Paragraph({
          alignment: ci === 0 ? AlignmentType.CENTER : AlignmentType.LEFT,
          spacing: { line: 280 },
          children: [new TextRun({ text: String(cell), font: FONT_BODY, size: SIZE_CAPTION, color: ci === 0 ? "2C3E50" : "000000", bold: ci === 0 })],
        })],
      })),
    }));
  });

  return elems;
}

// =============================================================
// 表数据定义
// =============================================================

const W = [1800, 1400, 2600, 3555]; // 字段 | 类型 | 约束 | 说明

const TABLE1 = {
  caption: "表 1  users 用户表结构",
  head: ["字段", "类型", "约束", "说明"],
  widths: W,
  rows: [
    ["id", "TEXT", "PRIMARY KEY", "用户唯一标识 (如 demo_user)"],
    ["username", "TEXT", "NOT NULL, UNIQUE", "登录用户名"],
    ["password_hash", "TEXT", "NULL", "PBKDF2-SHA256 密码哈希值"],
    ["role", "TEXT", "NOT NULL", "角色: student / admin, 默认 student"],
    ["created_at", "DATETIME", "NOT NULL", "账户创建时间"],
    ["updated_at", "DATETIME", "NOT NULL", "最后更新时间"],
  ],
};

const TABLE2 = {
  caption: "表 2  user_sessions 会话表结构",
  head: ["字段", "类型", "约束", "说明"],
  widths: W,
  rows: [
    ["token", "TEXT", "PRIMARY KEY", "Bearer 认证令牌"],
    ["user_id", "TEXT", "NOT NULL, FK", "关联 users.id"],
    ["created_at", "DATETIME", "NOT NULL", "会话创建时间"],
    ["expired_at", "DATETIME", "NULL", "过期时间 (创建后 30 天)"],
    ["is_revoked", "INTEGER", "NOT NULL", "撤销标记: 0=有效 1=已撤销"],
  ],
};

const TABLE3 = {
  caption: "表 3  questions 题目表结构",
  head: ["字段", "类型", "约束", "说明"],
  widths: [1700, 1400, 2400, 3855],
  rows: [
    ["id", "TEXT", "PRIMARY KEY", "题目唯一标识 (q_xxx)"],
    ["user_id", "TEXT", "NOT NULL, FK", "关联 users.id"],
    ["stem", "TEXT", "NOT NULL", "题干文本内容"],
    ["options_json", "TEXT", "NULL", "选项列表的 JSON 字符串"],
    ["correct_answer", "TEXT", "NULL", "正确答案"],
    ["analysis", "TEXT", "NULL", "AI 自动生成的解析文本"],
    ["ai_label", "TEXT", "NULL", "模型预测的初始学科标签"],
    ["final_label", "TEXT", "NOT NULL", "用户确认/修正后的最终标签"],
    ["confidence", "REAL", "NULL", "预测置信度 (0.0~1.0)"],
    ["mastery_status", "TEXT", "NOT NULL", "状态: unreviewed/reviewed/mastered/careless"],
    ["source_type", "TEXT", "NOT NULL", "来源: manual/import/ocr"],
    ["is_deleted", "INTEGER", "NOT NULL", "软删除标记: 0=活跃 1=已删除"],
    ["created_at", "DATETIME", "NOT NULL", "创建时间"],
    ["updated_at", "DATETIME", "NOT NULL", "最后更新时间"],
  ],
};

const TABLE4 = {
  caption: "表 4  question_feedback 反馈表结构",
  head: ["字段", "类型", "约束", "说明"],
  widths: W,
  rows: [
    ["id", "TEXT", "PRIMARY KEY", "反馈唯一标识 (fb_xxx)"],
    ["question_id", "TEXT", "NOT NULL, FK", "关联 questions.id"],
    ["user_id", "TEXT", "NOT NULL, FK", "关联 users.id"],
    ["question_text", "TEXT", "NOT NULL", "题目文本快照 (防止原题被修改)"],
    ["predicted_label", "TEXT", "NOT NULL", "模型原始预测标签"],
    ["corrected_label", "TEXT", "NOT NULL", "用户纠正后的标签"],
    ["is_corrected", "INTEGER", "NOT NULL", "是否被纠正: 0=一致 1=已纠正"],
    ["created_at", "DATETIME", "NOT NULL", "反馈提交时间"],
  ],
};

const TABLE5 = {
  caption: "表 5  incremental_corpus 增量语料表结构",
  head: ["字段", "类型", "约束", "说明"],
  widths: W,
  rows: [
    ["id", "TEXT", "PRIMARY KEY", "语料唯一标识 (corpus_xxx)"],
    ["question_text", "TEXT", "NOT NULL", "待加入训练集的文本"],
    ["label", "TEXT", "NOT NULL", "对应的正确标签"],
    ["source_feedback_id", "TEXT", "NOT NULL, FK", "关联 question_feedback.id"],
    ["write_status", "TEXT", "NOT NULL", "状态: pending/written/failed"],
    ["write_error", "TEXT", "NULL", "写入物理文件失败时的错误信息"],
    ["written_at", "DATETIME", "NULL", "成功写入 train.txt 的时间"],
    ["created_at", "DATETIME", "NOT NULL", "语料创建时间"],
  ],
};

const TABLE6 = {
  caption: "表 6  model_versions 模型版本表结构",
  head: ["字段", "类型", "约束", "说明"],
  widths: W,
  rows: [
    ["id", "TEXT", "PRIMARY KEY", "版本唯一标识"],
    ["version_name", "TEXT", "NOT NULL, UNIQUE", "版本名 (如 textcnn-v1.0)"],
    ["model_path", "TEXT", "NOT NULL", "模型文件 .pth 的存储路径"],
    ["is_active", "INTEGER", "NOT NULL", "是否为当前系统在线推理版本"],
    ["is_deleted", "INTEGER", "NOT NULL", "软删除标记"],
    ["created_at", "DATETIME", "NOT NULL", "创建时间"],
  ],
};

const TABLE7 = {
  caption: "表 7  question_review_logs 复习日志表结构",
  head: ["字段", "类型", "约束", "说明"],
  widths: W,
  rows: [
    ["id", "TEXT", "PRIMARY KEY", "日志唯一标识 (log_xxx)"],
    ["question_id", "TEXT", "NOT NULL, FK", "关联 questions.id"],
    ["user_id", "TEXT", "NOT NULL, FK", "关联 users.id"],
    ["from_status", "TEXT", "NULL", "变更前状态"],
    ["to_status", "TEXT", "NOT NULL", "变更后状态"],
    ["created_at", "DATETIME", "NOT NULL", "状态变更执行时间"],
  ],
};

// =============================================================
// ER 图
// =============================================================

const ER_PNG = path.resolve(__dirname, "fig_er_diagram.png");
let imgData = null;
try { imgData = fs.readFileSync(ER_PNG); } catch (_) {}

// =============================================================
// 构建文档正文
// =============================================================

const C = [];

// ==== 章标题 ====
C.push(h1("数据库设计"));

// 概述
C.push(body("本系统使用 SQLite 作为后端数据库，数据库文件存储于 data/app.db。系统具备自初始化能力，服务启动时将自动调用 init_db() 函数完成建表与初始化。数据库包含七张核心表，分别为用户表 (users)、会话表 (user_sessions)、题目表 (questions)、反馈表 (question_feedback)、增量语料表 (incremental_corpus)、模型版本表 (model_versions) 和复习日志表 (question_review_logs)，其逻辑关系紧密围绕\u2018用户-题目-反馈-模型\u2019的闭环流程设计。各表之间的关系如图 1 所示。"));

// ER 图
if (imgData) {
  C.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 180, after: 40 },
    children: [new ImageRun({
      type: "png", data: imgData,
      transformation: { width: 490, height: 368 },
      altText: { title: "ER图", description: "数据库E-R图", name: "er_diagram" },
    })],
  }));
  C.push(figCaption("图 1  系统数据库 E-R 图"));
}

// ====== 1. 用户与会话管理 ======
C.push(h2("1.  用户与会话管理"));

C.push(body("系统采用严密的认证机制：用户密码使用 PBKDF2-SHA256 哈希方案，经过 120,000 轮迭代并加盐处理后存储，确保密码原文不落库。登录令牌 (Token) 通过 user_sessions 表进行黑名单式管理，有效期为 30 天。"));

C.push(subtitleBold("1.1 users 用户表"));
C.push(bodyRich([
  new TextRun({ text: "users 表", font: FONT_BODY, size: SIZE_BODY }),
  new TextRun({ text: " 存储系统账户信息，每条记录对应一个注册用户。用户唯一标识采用预设 ID（如 demo_user 和 admin_user），用户名全局唯一。角色字段 role 取 student 或 admin 值，用于权限控制——只有 admin 用户可以执行语料洗入 (/admin/corpus/flush) 和模型版本切换 (/admin/models/active) 等管理操作。", font: FONT_BODY, size: SIZE_BODY }),
]));
C.push(...makeThreeLineTable(TABLE1.caption, TABLE1.head, TABLE1.widths, TABLE1.rows));

C.push(subtitleBold("1.2 user_sessions 会话表"));
C.push(bodyRich([
  new TextRun({ text: "user_sessions 表", font: FONT_BODY, size: SIZE_BODY }),
  new TextRun({ text: " 管理 Bearer Token 登录态。用户登录成功后，服务端生成全局唯一令牌写入该表，同时设定过期时间为当前时间加 30 天。每次 API 请求通过 get_current_user 依赖函数从 Authorization 头中提取令牌，查询 user_sessions 表进行验证：token 必须存在、未被撤销 (is_revoked=0) 且未过期。验证失败返回 401 Unauthorized。", font: FONT_BODY, size: SIZE_BODY }),
]));
C.push(...makeThreeLineTable(TABLE2.caption, TABLE2.head, TABLE2.widths, TABLE2.rows));

// ====== 2. 题目数据核心 ======
C.push(h2("2.  题目数据核心"));

C.push(bodyRich([
  new TextRun({ text: "questions 表", font: FONT_BODY, size: SIZE_BODY }),
  new TextRun({ text: " 是业务逻辑的中枢，记录了从录入到掌握的全生命周期数据。系统支持手动录入 (manual)、文件导入 (import) 和 OCR 识别 (ocr) 三种渠道。题目选项以 JSON 字符串存储于 options_json 字段，支持 A/B/C/D 等多选项格式。模型预测标签 ai_label 记录分类器对题目的原始判断，最终标签 final_label 为用户确认或手动修正后的标签。掌握状态 mastery_status 支持四档流转：未复习 (unreviewed)、已复习 (reviewed)、已掌握 (mastered) 和粗心错误 (careless)，用户可在前端界面手动切换状态。删除操作采用软删除机制，is_deleted 标记而非物理删除数据，保留数据恢复与审计能力。", font: FONT_BODY, size: SIZE_BODY }),
]));

C.push(subtitleBold("2.1 questions 题目表"));
C.push(...makeThreeLineTable(TABLE3.caption, TABLE3.head, TABLE3.widths, TABLE3.rows));

// ====== 3. 反馈与增量学习流水线 ======
C.push(h2("3.  反馈与增量学习流水线"));

C.push(body("当用户纠正模型预测时，系统启动增量学习流程。反馈数据首先存入 question_feedback 表，随后由管理员在后台触发任务将语料刷入 incremental_corpus 表，最终追加至物理训练文件 data/train.txt，再通过重新运行词表构建和训练脚本完成模型更新。"));

C.push(subtitleBold("3.1 question_feedback 反馈表"));
C.push(bodyRich([
  new TextRun({ text: "question_feedback 表", font: FONT_BODY, size: SIZE_BODY }),
  new TextRun({ text: " 记录用户对模型预测结果的每一次纠错操作。当用户认为模型预测的学科标签不正确时，通过前端的反馈功能提交纠正后的标签。系统在同一个数据库事务中执行两项写入：(1) 向 question_feedback 表插入反馈记录，包含原始预测标签 predicted_label、纠正后标签 corrected_label，以及 question_text 文本快照（防止原题被后续修改）；(2) 向 incremental_corpus 表写入一条 write_status=pending 的增量语料记录，以 source_feedback_id 外键关联本次反馈。is_corrected 字段标识该条反馈是否实际改变了标签（predicted_label ≠ corrected_label 时为 1）。", font: FONT_BODY, size: SIZE_BODY }),
]));
C.push(...makeThreeLineTable(TABLE4.caption, TABLE4.head, TABLE4.widths, TABLE4.rows));

C.push(subtitleBold("3.2 incremental_corpus 增量语料表"));
C.push(bodyRich([
  new TextRun({ text: "incremental_corpus 表", font: FONT_BODY, size: SIZE_BODY }),
  new TextRun({ text: " 是连接用户反馈与模型训练的关键纽带。每条语料记录包含待加入训练集的题目文本 question_text 和对应正确标签 label，以及写入状态 write_status（pending/written/failed）。管理员通过 /api/v1/admin/corpus/flush 接口触发后台任务，在 CORPUS_FLUSH_LOCK 线程锁的保护下逐条处理 pending 语料：将 question_text 与 label 按 \"label<TAB>text\" 格式追加写入 data/train.txt 文件，写入成功后将 write_status 更新为 written 并记录 written_at 时间，写入失败则标记为 failed 并在 write_error 字段记录错误原因。语料写入 train.txt 后，需依次重新运行 vocab_built.py（重建词表）和 train.py（重新训练）两个脚本，才能将增量数据纳入模型的词表和训练过程。", font: FONT_BODY, size: SIZE_BODY }),
]));
C.push(...makeThreeLineTable(TABLE5.caption, TABLE5.head, TABLE5.widths, TABLE5.rows));

// ====== 4. 模型管理与行为日志 ======
C.push(h2("4.  模型管理与行为日志"));

C.push(bodyRich([
  new TextRun({ text: "model_versions 表", font: FONT_BODY, size: SIZE_BODY }),
  new TextRun({ text: " 支持多模型版本的并存管理和在线切换。系统通过 is_active 字段标记当前生效的推理版本，同一时刻只有一个版本处于激活状态。分类接口 /api/v1/ai/classify 在每次请求时调用 _get_active_model_version 函数查询 is_active=1 的版本名，并将 model_version 字段随预测结果一同返回。管理员通过 /api/v1/admin/models/active 接口进行版本切换，切换操作在单个数据库事务中完成：先将所有版本的 is_active 置 0，再将目标版本置 1，保证切换的原子性。该设计允许在不停止在线服务的情况下完成模型升级。", font: FONT_BODY, size: SIZE_BODY }),
]));

C.push(subtitleBold("4.1 model_versions 模型版本表"));
C.push(...makeThreeLineTable(TABLE6.caption, TABLE6.head, TABLE6.widths, TABLE6.rows));

C.push(subtitleBold("4.2 question_review_logs 复习日志表"));
C.push(bodyRich([
  new TextRun({ text: "question_review_logs 表", font: FONT_BODY, size: SIZE_BODY }),
  new TextRun({ text: " 完整记录每次掌握状态变更的历史信息。当用户通过前端界面修改某道题目的 mastery_status 时，系统在更新 questions 表的同时向该表写入一条日志记录，包含变更前状态 from_status 和变更后状态 to_status。日志表与题目表、用户表之间存在外键关联，所有复习日志限定在用户本人范围内查询。日志数据为两个仪表盘接口提供支撑：/dashboard/study-trend 统计每日的新增题目量和复习活动量，/dashboard/weak-topics 按 final_label 聚合各学科的未复习与粗心错题数量，识别薄弱知识点。", font: FONT_BODY, size: SIZE_BODY }),
]));
C.push(...makeThreeLineTable(TABLE7.caption, TABLE7.head, TABLE7.widths, TABLE7.rows));

// ====== 5. 索引与性能优化 ======
C.push(h2("5.  索引与性能优化"));

C.push(body("为了确保在数据量增长后仍能维持秒级响应，系统针对高频查询场景设计了如下索引："));

// 索引列表 (使用 numbering 的 bullet 列表)
const idxItems = [
  ["questions(user_id, created_at DESC)", "提升个人中心按时间排序的查询速度 (错题列表检索)"],
  ["questions(final_label)", "加速仪表盘各学科分布统计 (状态统计分析)"],
  ["questions(mastery_status)", "按掌握状态快速筛选题目"],
  ["questions(is_deleted)", "快速排除已删除的无效数据"],
  ["question_feedback(question_id)", "按题目查询关联反馈记录"],
  ["question_feedback(created_at DESC)", "按时间排序查询反馈记录"],
  ["question_feedback(is_corrected)", "按是否被纠正筛选反馈"],
  ["incremental_corpus(write_status)", "方便管理员快速筛选 pending 状态的语料 (批量刷入任务)"],
  ["incremental_corpus(created_at DESC)", "按时间排序查询增量语料"],
  ["model_versions(is_active)", "查询当前激活模型版本"],
  ["user_sessions(token)", "确保鉴权中间件在每次 API 请求时能快速验证身份 (会话验证)"],
  ["user_sessions(is_revoked)", "按撤销状态过滤会话 (安全过滤)"],
  ["user_sessions(user_id, created_at DESC)", "按用户和时间查询会话记录"],
  ["question_review_logs(question_id)", "按题目查询复习日志"],
  ["question_review_logs(user_id, created_at DESC)", "按用户和时间查询复习日志"],
  ["users(role)", "按角色筛选用户列表"],
];

idxItems.forEach(([col, desc]) => {
  C.push(new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    indent: { firstLine: 480 },
    spacing: { line: 320, lineRule: "auto" },
    children: [
      new TextRun({ text: "•  ", font: FONT_BODY, size: SIZE_BODY }),
      new TextRun({ text: col, font: "Consolas", size: SIZE_BODY, color: "2C3E50", bold: true }),
      new TextRun({ text: `  —— ${desc}`, font: FONT_BODY, size: SIZE_BODY }),
    ],
  }));
});

// =============================================================
// 打包文档
// =============================================================

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: FONT_BODY, size: SIZE_BODY } },
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: SIZE_H1, bold: true, font: FONT_HEADING, color: "000000" },
        paragraph: { spacing: { before: 300, after: 200 }, outlineLevel: 0 },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: SIZE_H2, bold: true, font: FONT_HEADING, color: "000000" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 },
      },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: PAGE_H },
        margin: { top: MG_TOP, bottom: MG_BOTTOM, left: MG_LEFT, right: MG_RIGHT },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: "武汉工程大学本科毕业论文（设计）", font: FONT_BODY, size: 21 })],
        })],
      }),
    },
    children: C,
  }],
});

const OUT_DIR = path.resolve(__dirname, "..", "doc");
if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });
const OUT = path.join(OUT_DIR, "数据库设计_格式化.docx");

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log(`OK  ${OUT}  (${(buf.length / 1024).toFixed(1)} KB)`);
}).catch((e) => { console.error(e); process.exit(1); });
