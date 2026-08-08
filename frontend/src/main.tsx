import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "./App";
import { applyUiPreferences, loadUiPreferences } from "./utils/uiPreferences";
import "./styles.css";

applyUiPreferences(loadUiPreferences());

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
