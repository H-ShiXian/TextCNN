const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, Header, Footer, AlignmentType, HeadingLevel, BorderStyle,
  WidthType, ShadingType, LevelFormat,
} = require("docx");

// =============================================================
// 格式常量 (按武汉工程大学本科毕业论文要求)
// =============================================================

// 页边距:上2.5cm 下2.0cm 左2.5cm 右2.0cm  (1cm≈567 DXA)
const MG_TOP = 1417, MG_BOTTOM = 1134, MG_LEFT = 1417, MG_RIGHT = 1134;
// A4: 11906 x 16838 DXA
const PAGE_W = 11906, PAGE_H = 16838;
// 内容区宽度
const CONTENT_W = PAGE_W - MG_LEFT - MG_RIGHT; // 9355
// 页眉页脚距边界 1.5cm ≈ 850 DXA
const HDR_MARGIN = 850, FTR_MARGIN = 850;

// 字体: 宋体=SimSun, 黑体=SimHei (中文Windows自带)
const FONT_BODY = "SimSun";     // 正文宋体
const FONT_HEADING = "SimHei";   // 标题黑体
// 字号(half-points): 五号=10.5pt→21, 小四=12pt→24, 四号=14pt→28
const SIZE_BODY = 24;       // 小四 12pt
const SIZE_TABLE_CAPTION = 21; // 五号 10.5pt
const SIZE_TABLE_BODY = 21;    // 五号 10.5pt
const SIZE_H1 = 28;         // 四号 14pt (一级标题, 黑体)
const SIZE_H2 = 24;         // 小四 12pt (二级标题, 黑体)
const SIZE_H3 = 24;         // 小四 12pt (三级...但按要求只能用两级)

// 行距: 1.5倍 -> 360 (240分之1行)
const LINE_SPACING = 360;
// 首行缩进两个字符: 小四12pt * 2 = 24pt = 480 DXA (1pt=20twips)
const FIRST_LINE_INDENT = 480;

// 三线表边框
const THICK_BORDER = { style: BorderStyle.SINGLE, size: 6, color: "000000" };
const THIN_BORDER  = { style: BorderStyle.SINGLE, size: 2, color: "000000" };
const NO_BORDER    = { style: BorderStyle.NONE };
const NO_BORDERS   = { top: NO_BORDER, bottom: NO_BORDER, left: NO_BORDER, right: NO_BORDER };

// 三线表专用边框 (顶线 + 表头底线 + 底线)
const BORDER_TOP_ONLY    = { top: THICK_BORDER, bottom: NO_BORDER, left: NO_BORDER, right: NO_BORDER };
const BORDER_BOTTOM_ONLY = { top: NO_BORDER, bottom: THICK_BORDER, left: NO_BORDER, right: NO_BORDER };
const BORDER_MID_ONLY    = { top: NO_BORDER, bottom: THIN_BORDER, left: NO_BORDER, right: NO_BORDER };
const BORDER_TOP_BOTTOM  = { top: THICK_BORDER, bottom: THICK_BORDER, left: NO_BORDER, right: NO_BORDER };
const BORDER_TOP_MID     = { top: THICK_BORDER, bottom: THIN_BORDER, left: NO_BORDER, right: NO_BORDER };

const CELL_MARGINS = { top: 40, bottom: 40, left: 80, right: 80 };

const FIG_DIR = path.resolve(__dirname);
const ER_PNG = path.join(FIG_DIR, "fig_er_diagram.png");
const OUT_DIR = path.resolve(__dirname, "..", "doc");
const OUT_FILE = path.join(OUT_DIR, "database_design_v2.docx");
if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

let imgData = null;
try {
  imgData = fs.readFileSync(ER_PNG);
} catch (_) { console.log("ER图未找到, 跳过插图"); }

// =============================================================
// 辅助函数
// =============================================================

function bodyPara(textOrRuns) {
  if (typeof textOrRuns === "string") {
    textOrRuns = [new TextRun({ text: textOrRuns, font: FONT_BODY, size: SIZE_BODY, color: "000000" })];
  }
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    indent: { firstLine: FIRST_LINE_INDENT },
    spacing: { line: LINE_SPACING, lineRule: "auto" },
    children: textOrRuns,
  });
}

function bodyParaNoIndent(textOrRuns) {
  if (typeof textOrRuns === "string") {
    textOrRuns = [new TextRun({ text: textOrRuns, font: FONT_BODY, size: SIZE_BODY, color: "000000" })];
  }
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { line: LINE_SPACING, lineRule: "auto" },
    children: textOrRuns,
  });
}

function heading1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    alignment: AlignmentType.LEFT,
    spacing: { before: 300, after: 200, line: LINE_SPACING },
    children: [new TextRun({ text, font: FONT_HEADING, size: SIZE_H1, bold: true, color: "000000" })],
  });
}

function heading2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    alignment: AlignmentType.LEFT,
    spacing: { before: 200, after: 120, line: LINE_SPACING },
    children: [new TextRun({ text, font: FONT_HEADING, size: SIZE_H2, bold: true, color: "000000" })],
  });
}

function centeredPara(text, font, size) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { line: LINE_SPACING },
    children: [new TextRun({ text, font, size, color: "000000" })],
  });
}

/**
 * 三线表: 顶线(粗)+表头底线(细)+底线(粗), 无竖线
 * @param {string} caption - 表名(上方居中)
 * @param {string[]} head - 表头
 * @param {number[]} widths - 列宽 DXA
 * @param {string[][]} rows - 数据行
 */
function threeLineTable(caption, head, widths, rows) {
  const totalW = widths.reduce((a, b) => a + b, 0);
  const elems = [];

  // 表名: 上方居中, 宋体五号
  elems.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 200, after: 60, line: LINE_SPACING },
    children: [new TextRun({ text: caption, font: FONT_BODY, size: SIZE_TABLE_CAPTION, bold: true, color: "000000" })],
  }));

  // 表头行: 顶粗线 + 下细线
  elems.push(
    ...headRowThreeLine(head, widths),
  );

  // 数据行
  rows.forEach((row, ri) => {
    const isLast = ri === rows.length - 1;
    elems.push(dataRowThreeLine(row, widths, isLast));
  });

  // 表不需要外层width(DXA表) — 但docx-js要求, 我们给一个近似值
  // 包装在Table里但需要整体宽度
  // 注意: 三线表在docx-js中逐行构造Cell的borders
  return elems;
}

function headRowThreeLine(head, widths) {
  const cells = head.map((h, i) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA },
    margins: CELL_MARGINS,
    borders: i === 0
      ? { top: THICK_BORDER, bottom: THIN_BORDER, left: NO_BORDER, right: NO_BORDER }
      : i === head.length - 1
        ? { top: THICK_BORDER, bottom: THIN_BORDER, left: NO_BORDER, right: NO_BORDER }
        : { top: THICK_BORDER, bottom: THIN_BORDER, left: NO_BORDER, right: NO_BORDER },
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { line: 300 },
      children: [new TextRun({ text: h, font: FONT_BODY, size: SIZE_TABLE_BODY, bold: true, color: "000000" })],
    })],
  }));
  return [new TableRow({ children: cells })];
}

function dataRowThreeLine(row, widths, isLast) {
  const cells = row.map((cell, i) => {
    const borderCfg = isLast
      ? (i === 0
          ? { top: NO_BORDER, bottom: THICK_BORDER, left: NO_BORDER, right: NO_BORDER }
          : i === row.length - 1
            ? { top: NO_BORDER, bottom: THICK_BORDER, left: NO_BORDER, right: NO_BORDER }
            : { top: NO_BORDER, bottom: THICK_BORDER, left: NO_BORDER, right: NO_BORDER })
      : NO_BORDERS;
    return new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      margins: CELL_MARGINS,
      borders: borderCfg,
      children: [new Paragraph({
        alignment: i === 0 ? AlignmentType.CENTER : AlignmentType.LEFT,
        spacing: { line: 280 },
        children: [new TextRun({ text: String(cell), font: FONT_BODY, size: SIZE_TABLE_BODY, color: "000000" })],
      })],
    });
  });
  return new TableRow({ children: cells });
}

// ---- 表定义 ----

const tblUsers = {
  caption: "表 1  users 用户表结构",
  head: ["字段", "类型", "约束", "说明"],
  widths: [1800, 1600, 2200, 3755],
  rows: [
    ["id", "TEXT", "PRIMARY KEY", "用户唯一标识"],
    ["username", "TEXT", "NOT NULL, UNIQUE", "登录用户名"],
    ["password_hash", "TEXT", "NULL", "PBKDF2-SHA256 密码哈希 (120,000轮加盐)"],
    ["role", "TEXT", "NOT NULL, DEFAULT 'student'", "角色: student / admin"],
    ["created_at", "DATETIME", "NOT NULL", "账户创建时间"],
    ["updated_at", "DATETIME", "NOT NULL", "最后更新时间"],
  ],
};

const tblSessions = {
  caption: "表 2  user_sessions 会话表结构",
  head: ["字段", "类型", "约束", "说明"],
  widths: [1800, 1600, 2200, 3755],
  rows: [
    ["token", "TEXT", "PRIMARY KEY", "Bearer 令牌"],
    ["user_id", "TEXT", "NOT NULL, FK → users.id", "关联用户"],
    ["created_at", "DATETIME", "NOT NULL", "创建时间"],
    ["expired_at", "DATETIME", "NULL", "过期时间 (有效期30天)"],
    ["is_revoked", "INTEGER", "NOT NULL, DEFAULT 0", "撤销标记: 0=有效 1=已撤销"],
  ],
};

const tblQuestions = {
  caption: "表 3  questions 题目表结构",
  head: ["字段", "类型", "约束", "说明"],
  widths: [1800, 1600, 2000, 3955],
  rows: [
    ["id", "TEXT", "PRIMARY KEY", "题目唯一标识 (q_xxx)"],
    ["user_id", "TEXT", "NOT NULL, FK → users.id", "所属用户"],
    ["stem", "TEXT", "NOT NULL", "题干文本"],
    ["options_json", "TEXT", "NULL", "选项列表的 JSON 字符串"],
    ["correct_answer", "TEXT", "NULL", "正确答案"],
    ["analysis", "TEXT", "NULL", "AI 解析文本"],
    ["ai_label", "TEXT", "NULL", "模型预测的学科标签"],
    ["final_label", "TEXT", "NOT NULL", "用户最终确认标签"],
    ["confidence", "REAL", "NULL", "预测置信度 (0~1)"],
    ["mastery_status", "TEXT", "NOT NULL, DEFAULT 'unreviewed'", "掌握状态"],
    ["source_type", "TEXT", "NOT NULL, DEFAULT 'manual'", "来源: manual/import/ocr"],
    ["is_deleted", "INTEGER", "NOT NULL, DEFAULT 0", "软删除标记"],
    ["created_at", "DATETIME", "NOT NULL", "创建时间"],
    ["updated_at", "DATETIME", "NOT NULL", "最后更新时间"],
  ],
};

const tblFeedback = {
  caption: "表 4  question_feedback 反馈表结构",
  head: ["字段", "类型", "约束", "说明"],
  widths: [1800, 1600, 2200, 3755],
  rows: [
    ["id", "TEXT", "PRIMARY KEY", "反馈唯一标识 (fb_xxx)"],
    ["question_id", "TEXT", "NOT NULL, FK → questions.id", "关联题目"],
    ["user_id", "TEXT", "NOT NULL, FK → users.id", "关联用户"],
    ["question_text", "TEXT", "NOT NULL", "题目文本快照"],
    ["predicted_label", "TEXT", "NOT NULL", "模型原始预测标签"],
    ["corrected_label", "TEXT", "NOT NULL", "用户纠正后的标签"],
    ["is_corrected", "INTEGER", "NOT NULL", "是否被纠正: 0=一致 1=已纠正"],
    ["created_at", "DATETIME", "NOT NULL", "反馈提交时间"],
  ],
};

const tblCorpus = {
  caption: "表 5  incremental_corpus 增量语料表结构",
  head: ["字段", "类型", "约束", "说明"],
  widths: [1800, 1600, 2200, 3755],
  rows: [
    ["id", "TEXT", "PRIMARY KEY", "语料唯一标识 (corpus_xxx)"],
    ["question_text", "TEXT", "NOT NULL", "题目文本"],
    ["label", "TEXT", "NOT NULL", "纠正后的正确标签"],
    ["source_feedback_id", "TEXT", "NOT NULL, FK → question_feedback.id", "来源反馈"],
    ["write_status", "TEXT", "NOT NULL, DEFAULT 'pending'", "写入状态: pending/written/failed"],
    ["write_error", "TEXT", "NULL", "写入失败时的错误信息"],
    ["written_at", "DATETIME", "NULL", "成功写入 train.txt 的时间"],
    ["created_at", "DATETIME", "NOT NULL", "创建时间"],
    ["updated_at", "DATETIME", "NULL", "最后更新时间"],
  ],
};

const tblModels = {
  caption: "表 6  model_versions 模型版本表结构",
  head: ["字段", "类型", "约束", "说明"],
  widths: [1800, 1600, 2200, 3755],
  rows: [
    ["id", "TEXT", "PRIMARY KEY", "版本唯一标识"],
    ["version_name", "TEXT", "NOT NULL, UNIQUE", "版本名 (如 textcnn-v1)"],
    ["model_path", "TEXT", "NOT NULL", "模型文件路径"],
    ["notes", "TEXT", "NULL", "版本备注"],
    ["is_active", "INTEGER", "NOT NULL, DEFAULT 0", "激活状态: 0=非活跃 1=活跃"],
    ["is_deleted", "INTEGER", "NOT NULL, DEFAULT 0", "软删除标记"],
    ["created_at", "DATETIME", "NOT NULL", "创建时间"],
    ["updated_at", "DATETIME", "NOT NULL", "最后更新时间"],
  ],
};

const tblLogs = {
  caption: "表 7  question_review_logs 复习日志表结构",
  head: ["字段", "类型", "约束", "说明"],
  widths: [1800, 1600, 2200, 3755],
  rows: [
    ["id", "TEXT", "PRIMARY KEY", "日志唯一标识 (log_xxx)"],
    ["question_id", "TEXT", "NOT NULL, FK → questions.id", "关联题目"],
    ["user_id", "TEXT", "NOT NULL, FK → users.id", "关联用户"],
    ["from_status", "TEXT", "NULL", "变更前状态"],
    ["to_status", "TEXT", "NOT NULL", "变更后状态"],
    ["created_at", "DATETIME", "NOT NULL", "状态变更时间"],
  ],
};

// ---- 索引表 ----
const tblIndexes = {
  caption: "表 8  核心索引列表",
  head: ["索引名 (示例)", "所属表", "索引字段", "用途"],
  widths: [2400, 2000, 2555, 2400],
  rows: [
    ["idx_users_role", "users", "role", "按角色筛选用户"],
    ["idx_questions_user_created", "questions", "user_id, created_at DESC", "按用户+时间排序查题目"],
    ["idx_questions_final_label", "questions", "final_label", "按学科标签筛选"],
    ["idx_questions_mastery_status", "questions", "mastery_status", "按掌握状态筛选"],
    ["idx_questions_deleted", "questions", "is_deleted", "软删除快速过滤"],
    ["idx_feedback_question", "question_feedback", "question_id", "按题目查反馈"],
    ["idx_feedback_corrected", "question_feedback", "is_corrected", "按是否纠错筛选"],
    ["idx_corpus_status", "incremental_corpus", "write_status", "flush任务筛选pending语料"],
    ["idx_corpus_created", "incremental_corpus", "created_at DESC", "按时间排序查语料"],
    ["idx_model_versions_active", "model_versions", "is_active", "查询当前激活版本"],
    ["idx_sessions_user", "user_sessions", "user_id, created_at DESC", "按用户查会话"],
    ["idx_sessions_revoked", "user_sessions", "is_revoked", "按撤销状态过滤"],
    ["idx_review_question", "question_review_logs", "question_id", "按题目查复习日志"],
    ["idx_review_user_created", "question_review_logs", "user_id, created_at DESC", "按用户+时间查日志"],
  ],
};

// =============================================================
// 构建文档正文
// =============================================================

const contentChildren = [];

// 一级标题: X 数据库设计
contentChildren.push(heading1("数据库设计"));

// 正文概述
contentChildren.push(bodyPara([
  new TextRun({ text: "本系统采用 SQLite 作为后端数据库", font: FONT_BODY, size: SIZE_BODY }),
  new TextRun({ text: "，数据库文件存储于 data/app.db，服务启动时通过 init_db() 自动建表并初始化种子数据。数据库包含七张核心表，分别为用户表 (users)、会话表 (user_sessions)、题目表 (questions)、反馈表 (question_feedback)、增量语料表 (incremental_corpus)、模型版本表 (model_versions) 和复习日志表 (question_review_logs)。各表之间的关系如图 1 所示。", font: FONT_BODY, size: SIZE_BODY }),
]));

// ER 图
if (imgData) {
  contentChildren.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 200, after: 60, line: LINE_SPACING },
    children: [new ImageRun({
      type: "png",
      data: imgData,
      transformation: { width: 490, height: 368 },
      altText: { title: "ER图", description: "数据库ER图", name: "er_diagram" },
    })],
  }));
  contentChildren.push(centeredPara("图 1  TextCNN 系统数据库 E-R 图", FONT_BODY, SIZE_TABLE_CAPTION));
}

// --- 2.1 用户与会话 ---
contentChildren.push(heading2("1.  用户与会话"));

contentChildren.push(bodyPara([
  new TextRun({ text: "用户表 ", font: FONT_BODY, size: SIZE_BODY }),
  new TextRun({ text: "(users)", font: "Consolas", size: SIZE_BODY }),
  new TextRun({ text: " 存储系统账户信息。密码采用 PBKDF2-SHA256 哈希方案，120,000 轮迭代加盐后存储，密码原文不在数据库中落地。角色字段 (role) 区分学生 (student) 和管理员 (admin)，系统内置 demo_user 和 admin_user 两个默认账户，初始密码由环境变量 TEXTCNN_DEMO_PASSWORD 和 TEXTCNN_ADMIN_PASSWORD 注入。", font: FONT_BODY, size: SIZE_BODY }),
]));

contentChildren.push(bodyPara([
  new TextRun({ text: "会话表 ", font: FONT_BODY, size: SIZE_BODY }),
  new TextRun({ text: "(user_sessions)", font: "Consolas", size: SIZE_BODY }),
  new TextRun({ text: " 管理 Bearer Token 登录态。用户登录成功后服务端生成全局唯一令牌并写入该表，有效期 30 天。每次 API 请求通过 get_current_user 依赖函数解析 Authorization 头中的令牌，查询 user_sessions 表验证有效性，过期或已撤销 (is_revoked=1) 的令牌拒绝访问。", font: FONT_BODY, size: SIZE_BODY }),
]));

contentChildren.push(...threeLineTable(tblUsers.caption, tblUsers.head, tblUsers.widths, tblUsers.rows));
contentChildren.push(...threeLineTable(tblSessions.caption, tblSessions.head, tblSessions.widths, tblSessions.rows));

// --- 2.2 题目与标签 ---
contentChildren.push(heading2("2.  题目与标签"));

contentChildren.push(bodyPara([
  new TextRun({ text: "题目表 ", font: FONT_BODY, size: SIZE_BODY }),
  new TextRun({ text: "(questions)", font: "Consolas", size: SIZE_BODY }),
  new TextRun({ text: " 是系统业务核心表。每道题目记录题干 (stem)、选项列表 (options_json，以 JSON 字符串存储)、正确答案 (correct_answer) 和 AI 解析 (analysis)。模型预测标签 (ai_label) 记录分类器对题目的原始判断，最终标签 (final_label) 为用户确认或修改后的标签。掌握状态 (mastery_status) 支持四档流转：未复习 (unreviewed)、已复习 (reviewed)、已掌握 (mastered) 和粗心错误 (careless)。来源类型 (source_type) 区分手动录入 (manual)、文件批量导入 (import) 和 OCR 图片识别 (ocr) 三种渠道。题目采用软删除机制，is_deleted 字段标记删除状态而非物理删除数据，保留数据恢复和审计能力。", font: FONT_BODY, size: SIZE_BODY }),
]));

contentChildren.push(...threeLineTable(tblQuestions.caption, tblQuestions.head, tblQuestions.widths, tblQuestions.rows));

// --- 2.3 反馈与增量语料 ---
contentChildren.push(heading2("3.  反馈与增量语料"));

contentChildren.push(bodyPara([
  new TextRun({ text: "反馈表 ", font: FONT_BODY, size: SIZE_BODY }),
  new TextRun({ text: "(question_feedback)", font: "Consolas", size: SIZE_BODY }),
  new TextRun({ text: " 记录用户对模型预测结果的每一次纠错操作。当用户认为模型预测的学科标签不正确时，通过前端的反馈功能提交纠正后的标签，系统记录原始预测标签 (predicted_label) 和纠正后标签 (corrected_label)，同时计算 is_corrected 字段标识标签是否被修改（predicted_label ≠ corrected_label 时为 1）。每次反馈提交时，系统在同一数据库事务中向增量语料表 (incremental_corpus) 写入一条待处理记录，确保反馈与语料数据的原子性。", font: FONT_BODY, size: SIZE_BODY }),
]));

contentChildren.push(bodyPara([
  new TextRun({ text: "增量语料表 ", font: FONT_BODY, size: SIZE_BODY }),
  new TextRun({ text: "(incremental_corpus)", font: "Consolas", size: SIZE_BODY }),
  new TextRun({ text: " 是连接用户反馈与模型训练的关键纽带。每条语料记录包含题目文本 (question_text)、纠正后的正确标签 (label) 和写入状态 (write_status)，后者取 pending / written / failed 三值之一。管理员通过 /api/v1/admin/corpus/flush 接口触发后台任务，逐条将 write_status=pending 的语料追加写入 data/train.txt 文件。写入成功则标记 written 并记录写入时间 (written_at)，失败则标记 failed 并在 write_error 字段中记录错误原因。整个过程由线程锁 (CORPUS_FLUSH_LOCK) 保护，避免并发的 flush 请求导致重复写入。增量语料写入 train.txt 后，需要依次重新运行 vocab_built.py 和 train.py 两个脚本，才能将新增数据纳入模型的词表和训练过程。", font: FONT_BODY, size: SIZE_BODY }),
]));

contentChildren.push(...threeLineTable(tblFeedback.caption, tblFeedback.head, tblFeedback.widths, tblFeedback.rows));
contentChildren.push(...threeLineTable(tblCorpus.caption, tblCorpus.head, tblCorpus.widths, tblCorpus.rows));

// --- 2.4 模型版本管理 ---
contentChildren.push(heading2("4.  模型版本管理"));

contentChildren.push(bodyPara([
  new TextRun({ text: "模型版本表 ", font: FONT_BODY, size: SIZE_BODY }),
  new TextRun({ text: "(model_versions)", font: "Consolas", size: SIZE_BODY }),
  new TextRun({ text: " 支持多模型版本的并存管理和在线切换。每行记录包含版本名称 (version_name)、模型文件路径 (model_path)、版本备注 (notes) 和激活状态 (is_active)。系统中同时只有一个版本处于激活状态。分类 API (/api/v1/ai/classify) 在每次请求时调用 _get_active_model_version 函数查询当前激活版本名，并随预测结果一并返回 model_version 字段。管理员通过 /api/v1/admin/models/active 接口切换生效版本，切换操作在单个数据库事务中完成——先将所有版本的 is_active 置 0，再将目标版本的 is_active 置 1，保证切换的原子性。该设计允许不停止在线服务即可完成模型升级。", font: FONT_BODY, size: SIZE_BODY }),
]));

contentChildren.push(...threeLineTable(tblModels.caption, tblModels.head, tblModels.widths, tblModels.rows));

// --- 2.5 复习日志 ---
contentChildren.push(heading2("5.  复习日志"));

contentChildren.push(bodyPara([
  new TextRun({ text: "复习日志表 ", font: FONT_BODY, size: SIZE_BODY }),
  new TextRun({ text: "(question_review_logs)", font: "Consolas", size: SIZE_BODY }),
  new TextRun({ text: " 完整记录每次掌握状态变更的历史信息。当用户通过前端界面修改某道题目的 mastery_status 时，系统在更新 questions 表的同时向该表写入一条记录，包含变更前状态 (from_status) 和变更后状态 (to_status)。由此形成从 unreviewed → reviewed → mastered 的状态变更链，为学习趋势分析 (/dashboard/study-trend) 和薄弱知识点诊断 (/dashboard/weak-topics) 两个仪表盘接口提供底层数据支持。", font: FONT_BODY, size: SIZE_BODY }),
]));

contentChildren.push(...threeLineTable(tblLogs.caption, tblLogs.head, tblLogs.widths, tblLogs.rows));

// --- 2.6 索引设计 ---
contentChildren.push(heading2("6.  索引设计"));

contentChildren.push(bodyPara([
  new TextRun({ text: "在 SQLite 中，索引设计直接影响查询性能。本系统根据实际 API 查询模式对高频字段建立了覆盖性索引，共计 14 个。索引策略遵循以下原则：(1) 所有涉及 WHERE 筛选条件的单列建立普通索引；(2) 排序字段与筛选字段组合建立复合索引，例如 questions(user_id, created_at DESC) 支持按用户过滤并按时间降序排列的题目列表查询；(3) 软删除标记字段 (is_deleted) 和状态机字段 (write_status, is_active, is_revoked) 均建索引，保证状态筛选的低延迟；(4) 外键关联字段 (question_id, user_id) 建立索引以加速 JOIN 查询。全部索引如表 8 所示。", font: FONT_BODY, size: SIZE_BODY }),
]));

contentChildren.push(...threeLineTable(tblIndexes.caption, tblIndexes.head, tblIndexes.widths, tblIndexes.rows));

// =============================================================
// 构建文档
// =============================================================

const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: FONT_BODY, size: SIZE_BODY },
      },
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
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 1 },
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
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "—", font: FONT_BODY, size: 18 }),
            // PageNumber not usable in plain Paragraph without special run — use simple
            new TextRun({ text: " ", font: FONT_BODY, size: 18 }),
          ],
        })],
      }),
    },
    children: contentChildren,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT_FILE, buf);
  console.log(`Word文档已生成: ${OUT_FILE} (${(buf.length / 1024).toFixed(1)} KB)`);
}).catch((err) => {
  console.error("生成失败:", err);
  process.exit(1);
});
