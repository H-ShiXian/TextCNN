const apiBaseInput = document.getElementById("apiBase");
const usernameSelect = document.getElementById("username");
const loginBtn = document.getElementById("loginBtn");
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

const state = {
  token: "",
  labels: [],
  classified: null,
  page: 1,
  size: 8,
  total: 0
};

function getApiBase() {
  const custom = apiBaseInput.value.trim();
  if (custom) {
    return custom.replace(/\/$/, "");
  }
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
    throw new Error(data.message || `HTTP ${response.status}`);
  }
  return data.data || {};
}

async function loadLabels() {
  const data = await apiGet("/labels", false);
  state.labels = data.labels || [];

  entryFinalLabel.innerHTML = "";
  filterLabel.innerHTML = '<option value="">全部</option>';

  state.labels.forEach((label) => {
    const option1 = document.createElement("option");
    option1.value = label;
    option1.textContent = label;
    entryFinalLabel.appendChild(option1);

    const option2 = document.createElement("option");
    option2.value = label;
    option2.textContent = label;
    filterLabel.appendChild(option2);
  });
}

async function login() {
  const username = usernameSelect.value;
  const data = await apiPost("/auth/login", { username }, false);
  state.token = data.access_token;
  authStatus.textContent = `已登录 ${data.user.id} (${data.user.role})`;
  authStatus.className = "hint ok";
}

async function classifyText() {
  const text = entryText.value.trim();
  if (!text) {
    setEntryResult("请输入题干文本", "warn");
    return;
  }
  const data = await apiPost("/ai/classify", { text }, false);
  state.classified = data;
  entryAiLabel.value = data.label;
  entryConfidence.value = `${(Number(data.confidence) * 100).toFixed(2)}%`;
  entryFinalLabel.value = data.label;
  setEntryResult(`分类完成，模型版本: ${data.model_version}`, "ok");
}

async function saveQuestion() {
  const stem = entryText.value.trim();
  if (!stem) {
    setEntryResult("请输入题干文本", "warn");
    return;
  }

  const aiLabel = state.classified ? state.classified.label : null;
  const confidence = state.classified ? state.classified.confidence : null;
  const payload = {
    stem,
    analysis: entryAnalysis.value.trim() || null,
    ai_label: aiLabel,
    final_label: entryFinalLabel.value,
    confidence,
    source_type: "manual"
  };

  const data = await apiPost("/questions", payload, true);
  setEntryResult(`保存成功，题目ID: ${data.id}`, "ok");
  await loadQuestions();
  await refreshBoard();
}

function statusSelectHtml(questionId, currentStatus) {
  const statuses = ["unreviewed", "reviewed", "mastered", "careless"];
  const options = statuses
    .map((s) => `<option value="${s}" ${s === currentStatus ? "selected" : ""}>${s}</option>`)
    .join("");
  return `<select data-action="change-status" data-id="${questionId}">${options}</select>`;
}

function actionButtonsHtml(questionId) {
  return [
    `<button class="small ghost" data-action="edit" data-id="${questionId}">改类</button>`,
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
  listMeta.textContent = `第 ${state.page} 页 / 每页 ${state.size} 条 / 总计 ${state.total} 条`;

  questionTbody.innerHTML = "";
  items.forEach((item) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${item.stem}</td>
      <td>${item.final_label}</td>
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
  const newLabel = prompt("输入新的 final_label");
  if (!newLabel) return;
  await apiPatch(`/questions/${questionId}`, { final_label: newLabel.trim() }, true);
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
  const data = await apiGet("/dashboard/subject-distribution", true);
  const labels = data.labels || [];
  const counts = data.counts || [];
  const total = Number(data.total || 0);
  boardTotal.textContent = `总题数：${total}`;

  boardChart.innerHTML = "";
  if (!labels.length) {
    boardChart.textContent = "暂无数据";
    return;
  }

  labels.forEach((label, idx) => {
    const count = Number(counts[idx] || 0);
    const ratio = total > 0 ? (count / total) * 100 : 0;
    const row = document.createElement("div");
    row.className = "bar-item";
    row.innerHTML = `
      <span>${label}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${ratio.toFixed(2)}%"></div></div>
      <span>${count} (${ratio.toFixed(1)}%)</span>
    `;
    boardChart.appendChild(row);
  });
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    switchTab(tab.dataset.tab);
  });
});

loginBtn.addEventListener("click", async () => {
  try {
    await login();
    await loadQuestions();
    await refreshBoard();
  } catch (error) {
    authStatus.textContent = `登录失败: ${error.message}`;
    authStatus.className = "hint warn";
  }
});

classifyBtn.addEventListener("click", async () => {
  try {
    await classifyText();
  } catch (error) {
    setEntryResult(`分类失败: ${error.message}`, "warn");
  }
});

saveBtn.addEventListener("click", async () => {
  try {
    await saveQuestion();
  } catch (error) {
    setEntryResult(`保存失败: ${error.message}`, "warn");
  }
});

searchBtn.addEventListener("click", async () => {
  try {
    state.page = 1;
    await loadQuestions();
  } catch (error) {
    listMeta.textContent = `查询失败: ${error.message}`;
  }
});

prevPageBtn.addEventListener("click", async () => {
  if (state.page <= 1) return;
  state.page -= 1;
  try {
    await loadQuestions();
  } catch (error) {
    listMeta.textContent = `翻页失败: ${error.message}`;
  }
});

nextPageBtn.addEventListener("click", async () => {
  const maxPage = Math.max(1, Math.ceil(state.total / state.size));
  if (state.page >= maxPage) return;
  state.page += 1;
  try {
    await loadQuestions();
  } catch (error) {
    listMeta.textContent = `翻页失败: ${error.message}`;
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
    listMeta.textContent = `状态更新失败: ${error.message}`;
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
    listMeta.textContent = `操作失败: ${error.message}`;
  }
});

refreshBoardBtn.addEventListener("click", async () => {
  try {
    await refreshBoard();
  } catch (error) {
    boardTotal.textContent = `刷新失败: ${error.message}`;
  }
});

(async function bootstrap() {
  try {
    await loadLabels();
    if (state.labels.length) {
      entryFinalLabel.value = state.labels[0];
    }
  } catch (error) {
    setEntryResult(`初始化失败: ${error.message}`, "warn");
  }
})();
