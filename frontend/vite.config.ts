import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 개발: npm run dev (5173) → /api 는 FastAPI(8000)로 전달
// 배포: npm run build → dist/ 를 FastAPI 가 / 에서 제공
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
