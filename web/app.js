const input = document.getElementById("inputText");
const predictBtn = document.getElementById("predictBtn");
const sampleBtn = document.getElementById("sampleBtn");
const resultBox = document.getElementById("resultBox");
const historyList = document.getElementById("historyList");
const apiBaseInput = document.getElementById("apiBase");
const confidenceBar = document.getElementById("confidenceBar");

const historyItems = [];

function setResult(text, className = "") {
  resultBox.className = `result ${className}`.trim();
  resultBox.innerHTML = text;
}

function renderHistory() {
  historyList.innerHTML = "";
  historyItems.slice().reverse().forEach((item) => {
    const li = document.createElement("li");
    li.textContent = `${item.label} (${item.confidence}%) <- ${item.text}`;
    historyList.appendChild(li);
  });
}

function getApiBase() {
  const custom = apiBaseInput.value.trim();
  if (custom) {
    return custom.replace(/\/$/, "");
  }
  return `${location.origin}/api/v1`;
}

async function doPredict() {
  const text = input.value.trim();
  if (!text) {
    setResult("请输入要分类的文本。", "warn");
    return;
  }

  const apiBase = getApiBase();
  setResult(`正在请求 ${apiBase}/predict ...`);

  try {
    const response = await fetch(`${apiBase}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });

    const data = await response.json();
    const success = response.ok && data.code === 0;

    if (!success) {
      const msg = data.message || "请求失败";
      setResult(`后端返回错误：${msg}`, "warn");
      confidenceBar.style.width = "0%";
      return;
    }

    const payload = data.data || {};

    const confidence = (Number(payload.confidence) * 100).toFixed(2);
    setResult(
      `分类结果：<strong>${payload.label}</strong><br/>置信度：<strong>${confidence}%</strong>`,
      "ok"
    );

    confidenceBar.style.width = `${confidence}%`;

    historyItems.push({ text, label: payload.label, confidence });
    if (historyItems.length > 8) {
      historyItems.shift();
    }
    renderHistory();
  } catch (error) {
    setResult(`网络或服务异常：${error.message}`, "warn");
    confidenceBar.style.width = "0%";
  }
}

predictBtn.addEventListener("click", doPredict);

sampleBtn.addEventListener("click", () => {
  input.value = "简述进程与线程的区别";
  input.focus();
});

input.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    doPredict();
  }
});
