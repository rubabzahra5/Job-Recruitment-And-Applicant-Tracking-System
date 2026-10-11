/**
 * Fail-fast environment validation at server startup.
 *
 * `register()` runs when the Next.js server boots (not during `next build`),
 * so missing/invalid configuration crashes the process immediately with a
 * clear message instead of failing obscurely on the first request.
 * Error messages never include secret values — only variable names.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { validateEnv } = await import("./lib/env");
    validateEnv();
  }
}
