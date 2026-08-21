import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}

// One-time cleanup: all data now lives in the local SQLite database (backend).
if ("indexedDB" in window && indexedDB.databases) {
  indexedDB.databases()
    .then((dbs) => {
      if (dbs.some((d) => d.name === "shree-stay-pg-db")) {
        indexedDB.deleteDatabase("shree-stay-pg-db");
      }
    })
    .catch(() => {});
}
