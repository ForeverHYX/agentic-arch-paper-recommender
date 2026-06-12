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
    profileStatus.textContent = "Loaded local profile override.";
    renderProfileExport(profileEditor.value);
    return;
  }

  const response = await fetch("interests.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load interests.json: ${response.status}`);
  }
  const profile = await response.json();
  profileEditor.value = JSON.stringify(profile, null, 2);
  profileStatus.textContent = "Loaded published workflow profile.";
  renderProfileExport(profileEditor.value);
}

function saveProfileOverride() {
  let text = "";
  try {
    text = normalizedProfileText(profileEditor.value);
  } catch {
    profileStatus.textContent = "Profile JSON is invalid.";
    return;
  }
  localStorage.setItem(profileStorageKey, text);
  profileEditor.value = text;
  profileStatus.textContent = "Saved local profile override.";
  renderProfileExport(text);
}

function renderProfileExport(text) {
  let normalized = "";
  try {
    normalized = normalizedProfileText(text);
  } catch {
    profileStatus.textContent = "Profile JSON is invalid.";
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
