// Accessibility guard only (not a full lint setup): jsx-a11y over the React
// source so a11y regressions fail CI. TextInput/Select are our control wrappers,
// so labels that wrap them count as associated.
import a11y from "eslint-plugin-jsx-a11y";
import tsparser from "@typescript-eslint/parser";

export default [
  { ignores: ["dist/**", "node_modules/**"] },
  {
    files: ["src/**/*.tsx"],
    languageOptions: { parser: tsparser, parserOptions: { ecmaFeatures: { jsx: true } } },
    plugins: { "jsx-a11y": a11y },
    rules: {
      ...a11y.flatConfigs.recommended.rules,
      "jsx-a11y/label-has-associated-control": [
        "error",
        { controlComponents: ["TextInput", "Select"], assert: "either" },
      ],
    },
  },
];
