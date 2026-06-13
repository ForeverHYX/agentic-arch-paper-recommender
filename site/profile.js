const profileStorageKey = "recommender_profile_override";

const profileEditor = document.getElementById("profileEditor");
const profileStatus = document.getElementById("profileStatus");
const saveProfileButton = document.getElementById("saveProfileButton");
const downloadProfileLink = document.getElementById("downloadProfileLink");

if (saveProfileButton) {
  saveProfileButton.addEventListener("click", saveProfileOverride);
}
if (profileEditor) {
  profileEditor.addEventListener("input", () => renderProfileExport(profileEditor.value));
}

loadProfile().catch((error) => {
  profileStatus.textContent = error.message;
});

async function loadProfile() {
  const stored = localStorage.getItem(profileStorageKey);
  if (stored) {
    profileEditor.value = formatProfileText(stored);
    profileStatus.textContent = "已加载本地画像覆盖。";
    renderProfileExport(profileEditor.value);
    return;
  }

  const response = await fetch("interests.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`画像文件加载失败：${response.status}`);
  }
  const profile = await response.json();
  profileEditor.value = JSON.stringify(profile, null, 2);
  profileStatus.textContent = "已加载当前 workflow 发布的画像。";
  renderProfileExport(profileEditor.value);
}

function saveProfileOverride() {
  let text = "";
  try {
    text = normalizedProfileText(profileEditor.value);
  } catch {
    profileStatus.textContent = "画像 JSON 无效。";
    return;
  }
  localStorage.setItem(profileStorageKey, text);
  profileEditor.value = text;
  profileStatus.textContent = "已保存本地画像覆盖。";
  renderProfileExport(text);
}

function renderProfileExport(text) {
  let normalized = "";
  try {
    normalized = normalizedProfileText(text);
  } catch {
    profileStatus.textContent = "画像 JSON 无效。";
    return;
  }
  downloadProfileLink.download = "recommender-profile.json";
  downloadProfileLink.href = `data:application/json;charset=utf-8,${encodeURIComponent(normalized)}`;
}

function normalizedProfileText(text) {
  return JSON.stringify(JSON.parse(text), null, 2);
}

function formatProfileText(text) {
  try {
    return normalizedProfileText(text);
  } catch {
    return text;
  }
}
