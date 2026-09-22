import reactPlugin from "eslint-plugin-react";
import reactHooksPlugin from "eslint-plugin-react-hooks";
import jsxA11yPlugin from "eslint-plugin-jsx-a11y";
import importPlugin from "eslint-plugin-import";
import nextPlugin from "@next/eslint-plugin-next";
import tsParser from "@typescript-eslint/parser";

const eslintConfig = [
  {
    files: ["**/*.{js,jsx,ts,tsx}"],
    plugins: {
      react: reactPlugin,
      "react-hooks": reactHooksPlugin,
      "jsx-a11y": jsxA11yPlugin,
      import: importPlugin,
      "@next/next": nextPlugin,
    },
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
    },
    settings: {
      react: { version: "detect" },
      "import/parsers": {
        "@typescript-eslint/parser": [".ts", ".mts", ".cts", ".tsx", ".d.ts"],
      },
      "import/resolver": {
        node: { extensions: [".js", ".jsx", ".ts", ".tsx"] },
        typescript: { alwaysTryTypes: true },
      },
    },
    rules: {
      // next/core-web-vitals rules
      ...nextPlugin.configs["core-web-vitals"].rules,
      ...nextPlugin.configs.recommended.rules,

      // react recommended
      ...reactPlugin.configs.recommended.rules,
      "react/react-in-jsx-scope": "off",
      "react/prop-types": "off",
      "react/no-unknown-property": "off",
      "react/no-unescaped-entities": "off",

      // react-hooks
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",

      // jsx-a11y
      "jsx-a11y/alt-text": ["warn", { elements: ["img"], img: ["Image"] }],
      "jsx-a11y/aria-props": "warn",
      "jsx-a11y/aria-proptypes": "warn",
      "jsx-a11y/aria-unsupported-elements": "warn",
      "jsx-a11y/role-has-required-aria-props": "warn",
      "jsx-a11y/role-supports-aria-props": "warn",

      // import
      "import/no-anonymous-default-export": "warn",

      // next custom overrides
      "@next/next/no-page-custom-font": "off",
    },
  },
  {
    // BITB-102: public/sw.js is a hand-written, classic (non-module)
    // service worker script — it runs in the ServiceWorkerGlobalScope, not
    // as a module, and uses SW-only globals the main block doesn't know
    // about.
    files: ["public/sw.js"],
    languageOptions: {
      sourceType: "script",
      ecmaVersion: 2022,
      globals: {
        self: "readonly",
        caches: "readonly",
        clients: "readonly",
        fetch: "readonly",
        Response: "readonly",
        Request: "readonly",
        URL: "readonly",
        console: "readonly",
      },
    },
  },
  {
    ignores: ["*.config.js", "*.config.ts", "node_modules/", ".next/", "e2e/"],
  },
];
export default eslintConfig;
