/** @type {import('tailwindcss').Config} */
module.exports = {
  // 注意:Tailwind v3 的 content 路径相对 CWD 解析
  // 项目根(15CircleWeb/)跑 npx,所以 templates/ 是同级目录
  content: [
    "./templates/**/*.html",
    "./templates/**/*.js",
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
