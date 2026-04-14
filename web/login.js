const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");
const registerBtn = document.getElementById("registerBtn");
const loginBtn = document.getElementById("loginBtn");
const authStatus = document.getElementById("authStatus");

function getApiBase() {
  return `${location.origin}/api/v1`;
}

async function postJson(path, body) {
  const response = await fetch(`${getApiBase()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok || data.code !== 0) {
    throw new Error(data.message || `HTTP ${response.status}`);
  }
  return data.data || {};
}

async function handleLogin() {
  const username = usernameInput.value.trim();
  const password = passwordInput.value;
  if (!username || !password) {
    throw new Error("请输入用户名和密码");
  }

  const data = await postJson("/auth/login", { username, password });
  localStorage.setItem("auth_token", data.access_token);
  localStorage.setItem("auth_user", data.user.username);
  authStatus.textContent = "登录成功，正在跳转...";
  authStatus.className = "hint auth-footer ok";
  location.href = "/";
}

async function handleRegister() {
  const username = usernameInput.value.trim();
  const password = passwordInput.value;
  if (!username || !password) {
    throw new Error("请输入用户名和密码");
  }

  await postJson("/auth/register", { username, password });
  authStatus.textContent = `注册成功：${username}`;
  authStatus.className = "hint auth-footer ok";
}

loginBtn.addEventListener("click", async () => {
  try {
    await handleLogin();
  } catch (error) {
    authStatus.textContent = `登录失败：${error.message}`;
    authStatus.className = "hint auth-footer warn";
  }
});

registerBtn.addEventListener("click", async () => {
  try {
    await handleRegister();
  } catch (error) {
    authStatus.textContent = `注册失败：${error.message}`;
    authStatus.className = "hint auth-footer warn";
  }
});

// 如果有本地 token 直接跳转进入前台应用
if (localStorage.getItem("auth_token")) {
  location.href = "/";
}