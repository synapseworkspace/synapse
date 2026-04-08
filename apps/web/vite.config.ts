import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "./",
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react_vendor: ["react", "react-dom"],
          mantine_vendor: ["@mantine/core", "@mantine/hooks", "@mantine/notifications", "@tabler/icons-react"],
          intelligence_charts: ["@mantine/charts", "recharts"],
        },
      },
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
});
