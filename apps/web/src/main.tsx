import React from "react";
import ReactDOM from "react-dom/client";
import { MantineProvider, createTheme } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import App from "./App";
import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";
import "@mantine/charts/styles.css";
import "@mantine/tiptap/styles.css";
import "./styles.css";

const theme = createTheme({
  primaryColor: "teal",
  fontFamily: '"Plus Jakarta Sans", "Avenir Next", "Segoe UI", sans-serif',
  headings: {
    fontFamily: '"Space Grotesk", "Avenir Next", sans-serif',
  },
  radius: {
    md: "12px",
    lg: "18px",
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MantineProvider theme={theme}>
      <Notifications position="top-right" />
      <App />
    </MantineProvider>
  </React.StrictMode>,
);
