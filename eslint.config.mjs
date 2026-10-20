import js from "@eslint/js";

export default [{
  files: ["src/darkfactory/web/app.js"],
  languageOptions: {
    ecmaVersion: 2022,
    globals: {
      document: "readonly", fetch: "readonly", setInterval: "readonly",
      AbortController: "readonly", HTMLElement: "readonly",
      setTimeout: "readonly", clearTimeout: "readonly"
    }
  },
  rules: { ...js.configs.recommended.rules, eqeqeq: "error" }
}];
