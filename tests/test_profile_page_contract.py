import subprocess
import unittest
from pathlib import Path


class ProfilePageContractTests(unittest.TestCase):
    def run_profile_script(self, body):
        harness = r"""
const fs = require("fs");
const vm = require("vm");
const script = fs.readFileSync("site/profile.js", "utf8");
const elements = {};
const storage = {};

function element(id) {
  if (!elements[id]) {
    elements[id] = { textContent: "", value: "", href: "", download: "", addEventListener() {} };
  }
  return elements[id];
}

const context = {
  document: { getElementById: element },
  fetch: async () => ({
    ok: true,
    json: async () => ({
      name: "Test Profile",
      core_categories: ["cs.AR"],
      expansion_categories: ["cs.AI"],
      sections: [
        { id: "arch", label: "Architecture", weight: 4, keywords: ["gem5", "microarchitecture"] }
      ],
    }),
  }),
  localStorage: {
    getItem(key) {
      return Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null;
    },
    setItem(key, value) {
      storage[key] = String(value);
    },
  },
  encodeURIComponent,
  setTimeout,
};

vm.createContext(context);
vm.runInContext(script, context);

setTimeout(() => {
  try {
__BODY__
  } catch (error) {
    console.error(error.stack || error.message);
    process.exit(1);
  }
}, 0);
"""
        result = subprocess.run(
            ["node", "-e", harness.replace("__BODY__", body)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_profile_page_has_editor_and_export_hooks(self):
        html = Path("site/profile.html").read_text(encoding="utf-8")
        script = Path("site/profile.js").read_text(encoding="utf-8")

        self.assertIn('id="profileEditor"', html)
        self.assertIn('id="saveProfileButton"', html)
        self.assertIn('id="downloadProfileLink"', html)
        self.assertIn("PROFILE_OVERRIDE_JSON", html)
        self.assertIn("loadProfile", script)
        self.assertIn("saveProfileOverride", script)
        self.assertIn("renderProfileExport", script)

    def test_profile_page_saves_and_exports_valid_json(self):
        self.run_profile_script(
            """
const override = {
  name: "EDA Agents",
  core_categories: ["cs.AR"],
  expansion_categories: ["cs.AI"],
  sections: [
    { id: "eda_agents", label: "EDA Agents", weight: 4, keywords: ["placement agent"] }
  ],
};
elements.profileEditor.value = JSON.stringify(override);
context.saveProfileOverride();

if (!storage.recommender_profile_override) {
  throw new Error("profile override was not saved");
}
if (!elements.downloadProfileLink.href.startsWith("data:application/json;charset=utf-8,")) {
  throw new Error(`download href missing data URL: ${elements.downloadProfileLink.href}`);
}
if (elements.downloadProfileLink.download !== "recommender-profile.json") {
  throw new Error(`unexpected download filename: ${elements.downloadProfileLink.download}`);
}
if (!elements.profileStatus.textContent.includes("已保存")) {
  throw new Error(`missing saved status: ${elements.profileStatus.textContent}`);
}
"""
        )

    def test_profile_page_uses_chinese_copy(self):
        html = Path("site/profile.html").read_text(encoding="utf-8")
        script = Path("site/profile.js").read_text(encoding="utf-8")

        self.assertIn('lang="zh-CN"', html)
        self.assertIn("兴趣画像", html)
        self.assertIn("返回推荐列表", html)
        self.assertIn("保存本地副本", html)
        self.assertIn("下载 JSON", html)
        self.assertIn("已加载本地画像覆盖", script)
        self.assertIn("画像 JSON 无效", script)


if __name__ == "__main__":
    unittest.main()
