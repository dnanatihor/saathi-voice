import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Dashboard } from "./Dashboard";
import { ElderCall } from "./ElderCall";

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      {window.location.hash === "#elder" ? <ElderCall /> : <Dashboard cells={[]} />}
    </StrictMode>,
  );
}
