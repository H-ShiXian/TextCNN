const LABEL_MAP = {
  "computer_architecture": "计算机组成原理",
  "computer_network": "计算机网络",
  "data_structure": "数据结构",
  "operating_system": "操作系统",
  "xiaosi":"政治"
};

function formatLabel(label) {
  return LABEL_MAP[label] || label;
}

const logoutBtn = document.getElementById("logoutBtn");
const authStatus = document.getElementById("authStatus");

const tabs = Array.from(document.querySelectorAll(".tab"));
const tabPanels = {
  entry: document.getElementById("tab-entry"),
  list: document.getElementById("tab-list"),
  board: document.getElementById("tab-board")
};

const entryText = document.getElementById("entryText");
const classifyBtn = document.getElementById("classifyBtn");
const saveBtn = document.getElementById("saveBtn");
const entryAiLabel = document.getElementById("entryAiLabel");
const entryConfidence = document.getElementById("entryConfidence");
const entryFinalLabel = document.getElementById("entryFinalLabel");
const entryAnalysis = document.getElementById("entryAnalysis");
const entryResult = document.getElementById("entryResult");

const filterLabel = document.getElementById("filterLabel");
const filterStatus = document.getElementById("filterStatus");
const filterKeyword = document.getElementById("filterKeyword");
const searchBtn = document.getElementById("searchBtn");
const prevPageBtn = document.getElementById("prevPageBtn");
const nextPageBtn = document.getElementById("nextPageBtn");
const listMeta = document.getElementById("listMeta");
const questionTbody = document.getElementById("questionTbody");

const refreshBoardBtn = document.getElementById("refreshBoardBtn");
const boardTotal = document.getElementById("boardTotal");
const boardChart = document.getElementById("boardChart");
const masteryOverview = document.getElementById("masteryOverview");
const trendChart = document.getElementById("trendChart");
const weakTopics = document.getElementById("weakTopics");

const state = {
  token: "",
  currentUser: "",
  labels: [],
  classified: null,
  page: 1,
  size: 8,
  total: 0
};

function getApiBase() {
  return `${location.origin}/api/v1`;
}

function setEntryResult(msg, type = "") {
  entryResult.className = `result ${type}`.trim();
  entryResult.textContent = msg;
}

function switchTab(name) {
  tabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === name);
  });
  Object.keys(tabPanels).forEach((key) => {
    tabPanels[key].classList.toggle("active", key === name);
  });
}

function authHeaders() {
  if (!state.token) {
    throw new Error("请先登录");
  }
  return {
    Authorization: `Bearer ${state.token}`,
    "Content-Type": "application/json"
  };
}

async function apiGet(path, useAuth = false) {
  const headers = useAuth ? { Authorization: `Bearer ${state.token}` } : {};
  const response = await fetch(`${getApiBase()}${path}`, { headers });
  return handleApiResponse(response);
}

async function apiPatch(path, body, useAuth = true) {
  const response = await fetch(`${getApiBase()}${path}`, {
    method: "PATCH",
    headers: useAuth ? authHeaders() : { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  return handleApiResponse(response);
}

async function apiPost(path, body, useAuth = true) {
  const response = await fetch(`${getApiBase()}${path}`, {
    method: "POST",
    headers: useAuth ? authHeaders() : { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  return handleApiResponse(response);
}

async function handleApiResponse(response) {
  const data = await response.json();
  if (!response.ok || data.code !== 0) {
    if (response.status === 401) {
      localStorage.removeItem("auth_token");
      localStorage.removeItem("auth_user");
      location.href = "/login";
    }
    throw new Error(data.message || `HTTP ${response.status}`);
  }
  return data.data || {};
}

function ensureAuth() {
  const token = localStorage.getItem("auth_token") || "";
  const username = localStorage.getItem("auth_user") || "";
  if (!token) {
    location.href = "/login";
    return false;
  }
  state.token = token;
  state.currentUser = username;
  authStatus.textContent = username ? username : "已登录";
  return true;
}

async function loadLabels() {
  const data = await apiGet("/labels", false);
  state.labels = data.labels || [];

  entryFinalLabel.innerHTML = "";
  filterLabel.innerHTML = '<option value="">全部</option>';

  state.labels.forEach((label) => {
    const displayLabel = formatLabel(label);
    const option1 = document.createElement("option");
    option1.value = label;
    option1.textContent = displayLabel;
    entryFinalLabel.appendChild(option1);

    const option2 = document.createElement("option");
    option2.value = label;
    option2.textContent = displayLabel;
    filterLabel.appendChild(option2);
  });
}


async function classifyText() {
  const text = entryText.value.trim();
  if (!text) {
    setEntryResult("请输入题目文本", "warn");
    return;
  }
  const data = await apiPost("/ai/classify", { text }, false);
  state.classified = data;
  entryAiLabel.value = formatLabel(data.label);
  entryConfidence.value = `${(Number(data.confidence) * 100).toFixed(2)}%`;
  entryFinalLabel.value = data.label;
  setEntryResult(`分类完成 · 模型 ${data.model_version}`, "ok");
}

async function saveQuestion() {
  const stem = entryText.value.trim();
  if (!stem) {
    setEntryResult("请输入题目文本", "warn");
    return;
  }

  const aiLabel = state.classified ? state.classified.label : null;
  const confidence = state.classified ? state.classified.confidence : null;
  const finalLabel = entryFinalLabel.value;

  const payload = {
    stem,
    analysis: entryAnalysis.value.trim() || null,
    ai_label: aiLabel,
    final_label: finalLabel,
    confidence,
    source_type: "manual"
  };

  const data = await apiPost("/questions", payload, true);

  if (aiLabel && aiLabel !== finalLabel) {
    try {
      await apiPost("/ai/feedback", {
        question_id: data.id,
        question_text: stem,
        predicted_label: aiLabel,
        corrected_label: finalLabel
      }, true);
    } catch (error) {
      console.warn("AI错题反馈收集失败:", error.message);
    }
  }

  setEntryResult(`保存成功 · ${data.id}`, "ok");

  entryText.value = "";
  entryAnalysis.value = "";
  entryAiLabel.value = "";
  entryConfidence.value = "";
  state.classified = null;

  await loadQuestions();
  await refreshBoard();
}

entryText.addEventListener("input", () => {
  state.classified = null;
  entryAiLabel.value = "";
  entryConfidence.value = "";
});

function statusSelectHtml(questionId, currentStatus) {
  const statusMap = {
    "unreviewed": "未复习",
    "reviewed": "已复习",
    "mastered": "已掌握",
    "careless": "粗心错"
  };
  const options = Object.entries(statusMap)
    .map(([v, label]) => `<option value="${v}" ${v === currentStatus ? "selected" : ""}>${label}</option>`)
    .join("");
  return `<select data-action="change-status" data-id="${questionId}">${options}</select>`;
}

function actionButtonsHtml(questionId) {
  return [
    `<button class="small ghost" data-action="edit" data-id="${questionId}">编辑</button>`,
    `<button class="small ghost" data-action="delete" data-id="${questionId}">删除</button>`
  ].join(" ");
}

async function loadQuestions() {
  const params = new URLSearchParams({
    page: String(state.page),
    size: String(state.size)
  });
  if (filterLabel.value) params.set("final_label", filterLabel.value);
  if (filterStatus.value) params.set("mastery_status", filterStatus.value);
  if (filterKeyword.value.trim()) params.set("keyword", filterKeyword.value.trim());

  const data = await apiGet(`/questions?${params.toString()}`, true);
  const items = data.items || [];
  state.total = Number(data.total || 0);
  listMeta.textContent = `第 ${state.page} 页 / 每页 ${state.size} 条 / 共 ${state.total} 条`;

  questionTbody.innerHTML = "";
  items.forEach((item) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${item.stem}</td>
      <td>${formatLabel(item.final_label)}</td>
      <td>${statusSelectHtml(item.id, item.mastery_status)}</td>
      <td>${item.updated_at}</td>
      <td>${actionButtonsHtml(item.id)}</td>
    `;
    questionTbody.appendChild(tr);
  });
}

async function updateStatus(questionId, toStatus) {
  await apiPatch(`/questions/${questionId}/status`, { to_status: toStatus }, true);
}

async function editLabel(questionId) {
  const labelsText = state.labels.map(l => `${l} (${formatLabel(l)})`).join('\n');
  const newLabel = prompt(`请输入新的分类的英文标识，可选值包含: \n${labelsText}`);
  if (!newLabel) return;
  
  const trimmedLabel = newLabel.trim();
  if (!state.labels.includes(trimmedLabel)) {
    alert(`分类【${trimmedLabel}】不合法，请填入系统许可的有效学科标签。`);
    return;
  }
  
  await apiPatch(`/questions/${questionId}`, { final_label: trimmedLabel }, true);
  await loadQuestions();
  await refreshBoard();
}

async function softDelete(questionId) {
  const response = await fetch(`${getApiBase()}/questions/${questionId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${state.token}` }
  });
  const data = await response.json();
  if (!response.ok || data.code !== 0) {
    throw new Error(data.message || "删除失败");
  }
  await loadQuestions();
  await refreshBoard();
}

async function refreshBoard() {
  const [subjectData, masteryData, trendData, weakData] = await Promise.all([
    apiGet("/dashboard/subject-distribution", true),
    apiGet("/dashboard/mastery-overview", true),
    apiGet("/dashboard/study-trend?days=7", true),
    apiGet("/dashboard/weak-topics", true)
  ]);

  const labels = subjectData.labels || [];
  const counts = subjectData.counts || [];
  const total = Number(subjectData.total || 0);
  boardTotal.textContent = `总题数：${total}`;

  const masteryRate = Number(masteryData.mastery_rate || 0) * 100;
  const reviewRate = Number(masteryData.review_rate || 0) * 100;
  const statusCount = masteryData.status_count || {};
  masteryOverview.innerHTML = [
    `<div class="card">掌握率<br><strong>${masteryRate.toFixed(1)}%</strong></div>`,
    `<div class="card">复习覆盖率<br><strong>${reviewRate.toFixed(1)}%</strong></div>`,
    `<div class="card">未复习<br><strong>${Number(statusCount.unreviewed || 0)}</strong></div>`,
    `<div class="card">粗心题<br><strong>${Number(statusCount.careless || 0)}</strong></div>`
  ].join("");

  boardChart.innerHTML = "";
  if (!labels.length) {
    boardChart.textContent = "暂无数据";
  } else {
    labels.forEach((label, idx) => {
      const count = Number(counts[idx] || 0);
      const ratio = total > 0 ? (count / total) * 100 : 0;
      const row = document.createElement("div");
      row.className = "bar-item";
      row.innerHTML = `
        <span>${formatLabel(label)}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${ratio.toFixed(2)}%"></div></div>
        <span>${count} (${ratio.toFixed(1)}%)</span>
      `;
      boardChart.appendChild(row);
    });
  }

  trendChart.innerHTML = "";
  const trendLabels = trendData.labels || [];
  const createdCounts = trendData.created_counts || [];
  const reviewedCounts = trendData.reviewed_counts || [];
  if (!trendLabels.length) {
    trendChart.textContent = "暂无趋势数据";
  } else {
    trendLabels.forEach((d, idx) => {
      const createdCnt = Number(createdCounts[idx] || 0);
      const reviewedCnt = Number(reviewedCounts[idx] || 0);
      const maxV = Math.max(1, createdCnt, reviewedCnt);
      const row = document.createElement("div");
      row.className = "trend-item";
      row.innerHTML = `
        <span>${d}</span>
        <div class="trend-bars">
          <div class="bar-track"><div class="bar-fill trend-created" style="width:${((createdCnt / maxV) * 100).toFixed(2)}%"></div></div>
          <div class="bar-track"><div class="bar-fill trend-reviewed" style="width:${((reviewedCnt / maxV) * 100).toFixed(2)}%"></div></div>
        </div>
        <span>新录入:${createdCnt} / 复习:${reviewedCnt}</span>
      `;
      trendChart.appendChild(row);
    });
  }

  weakTopics.innerHTML = "";
  const weakItems = weakData.items || [];
  if (!weakItems.length) {
    weakTopics.textContent = "暂无薄弱学科数据";
  } else {
    weakItems.slice(0, 5).forEach((item) => {
      const row = document.createElement("div");
      row.className = "bar-item";
      row.innerHTML = `
        <span>${formatLabel(item.label)}</span>
        <div class="bar-track"><div class="bar-fill weak-fill" style="width:${(Number(item.weak_rate || 0) * 100).toFixed(2)}%"></div></div>
        <span>薄弱:${item.weak_cnt}/${item.total_cnt}</span>
      `;
      weakTopics.appendChild(row);
    });
  }
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    switchTab(tab.dataset.tab);
  });
});

logoutBtn.addEventListener("click", () => {
  localStorage.removeItem("auth_token");
  localStorage.removeItem("auth_user");
  location.href = "/login";
});

classifyBtn.addEventListener("click", async () => {
  try {
    await classifyText();
  } catch (error) {
    setEntryResult(`分类失败：${error.message}`, "warn");
  }
});

saveBtn.addEventListener("click", async () => {
  try {
    await saveQuestion();
  } catch (error) {
    setEntryResult(`保存失败：${error.message}`, "warn");
  }
});

searchBtn.addEventListener("click", async () => {
  try {
    state.page = 1;
    await loadQuestions();
  } catch (error) {
    listMeta.textContent = `查询失败：${error.message}`;
  }
});

prevPageBtn.addEventListener("click", async () => {
  if (state.page <= 1) return;
  state.page -= 1;
  try {
    await loadQuestions();
  } catch (error) {
    listMeta.textContent = `翻页失败：${error.message}`;
  }
});

nextPageBtn.addEventListener("click", async () => {
  const maxPage = Math.max(1, Math.ceil(state.total / state.size));
  if (state.page >= maxPage) return;
  state.page += 1;
  try {
    await loadQuestions();
  } catch (error) {
    listMeta.textContent = `翻页失败：${error.message}`;
  }
});

questionTbody.addEventListener("change", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLSelectElement)) return;
  const action = target.dataset.action;
  const questionId = target.dataset.id;
  if (action !== "change-status" || !questionId) return;
  try {
    await updateStatus(questionId, target.value);
    await loadQuestions();
  } catch (error) {
    listMeta.textContent = `状态更新失败：${error.message}`;
  }
});

questionTbody.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) return;
  const action = target.dataset.action;
  const questionId = target.dataset.id;
  if (!questionId) return;

  try {
    if (action === "edit") {
      await editLabel(questionId);
    } else if (action === "delete") {
      await softDelete(questionId);
    }
  } catch (error) {
    listMeta.textContent = `操作失败：${error.message}`;
  }
});

refreshBoardBtn.addEventListener("click", async () => {
  try {
    await refreshBoard();
  } catch (error) {
    boardTotal.textContent = `刷新失败：${error.message}`;
  }
});

(async function bootstrap() {
  try {
    if (!ensureAuth()) {
      return;
    }
    await loadLabels();
    if (state.labels.length) {
      entryFinalLabel.value = state.labels[0];
    }
    await loadQuestions();
    await refreshBoard();
  } catch (error) {
    setEntryResult(`初始化失败：${error.message}`, "warn");
  }
})();
