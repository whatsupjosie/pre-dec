module.exports = {
  env:     { node: true, es2021: true, browser: true },
  extends: ["eslint:recommended"],
  parserOptions: { ecmaVersion: 2021 },
  rules: {
    "no-unused-vars":    ["warn", { argsIgnorePattern: "^_" }],
    "no-console":        "off",
    "semi":              ["error", "always"],
    "no-trailing-spaces": "warn",
  },
  ignorePatterns: ["node_modules/", "dist/"],
};
