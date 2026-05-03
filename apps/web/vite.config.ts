import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const buildLabel =
  process.env.VITE_SYNAPSE_WEB_BUILD ||
  process.env.SYNAPSE_WEB_BUILD ||
  process.env.SOURCE_VERSION ||
  new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 12);

process.env.VITE_SYNAPSE_WEB_BUILD = buildLabel;

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
