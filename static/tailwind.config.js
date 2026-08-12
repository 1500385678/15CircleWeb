/** @type {import('tailwindcss').Config} */
module.exports = {
  // 注意:Tailwind v3 的 content 路径相对 CWD 解析
  // 项目根(15CircleWeb/)跑 npx,所以 templates/ 是同级目录
  content: [
    "./templates/**/*.html",
    "./templates/**/*.js",
  ],
  // ✅ P1 闭环:2026-08-13 Verifier R300 — sr-only 用于全局搜索 a11y 标签
  safelist: [
    "sr-only",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
  corePlugins: {
    preflight: true,
  },
  mode: "jit",
};
