// Commitlint configuration — enforced on PRs via .github/workflows/commitlint.yml
// Extends the conventional-commits preset used by release-please.
module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "type-enum": [
      2,
      "always",
      ["feat", "fix", "perf", "revert", "docs", "chore", "build", "ci", "refactor", "test", "style"],
    ],
    "body-max-line-length": [0],
  },
};
