import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// Desktop talks to the backend directly via window.mlibDesktop.apiBase; a relative
// "/api/..." URL goes through the Next.js rewrite, which is dead in the desktop bundle.
const apiLiteralMessage = "Build backend URLs with apiUrl() from @/lib/api instead of a literal /api path.";

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/lib/api.ts"],
    rules: {
      "no-restricted-syntax": [
        "error",
        { selector: "Literal[value=/^\\/api(\\/|$)/]", message: apiLiteralMessage },
        { selector: "TemplateElement[value.raw=/^\\/api(\\/|$)/]", message: apiLiteralMessage },
      ],
    },
  },
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
]);
