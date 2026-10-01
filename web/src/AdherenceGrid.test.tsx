import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { AdherenceGrid } from "./AdherenceGrid";
import { Dashboard, spokenPreview } from "./Dashboard";
import { ElderCall } from "./ElderCall";

const cells = [
  { day: "mon", date: "2026-09-28", time: "09:00", label: "बीपी की दवा", status: "taken" },
  { day: "mon", date: "2026-09-28", time: "21:00", label: "बीपी की दवा", status: "missed" },
];

test("the dashboard shows the weekly adherence grid", () => {
  render(<Dashboard cells={cells} />);
  expect(screen.getByRole("table", { name: "Weekly adherence" })).toBeTruthy();
  expect(screen.getByRole("cell", { name: "taken" })).toBeTruthy();
  expect(screen.getByRole("cell", { name: "missed" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Export data" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Erase elder data" })).toBeTruthy();
});

test("the elder page has one talk button", () => {
  render(<ElderCall />);
  expect(screen.getByRole("button", { name: "बात करें" })).toBeTruthy();
});

test("spoken label preview uses the honorific and label", () => {
  render(<AdherenceGrid cells={cells} />);
  expect(spokenPreview("बाबूजी", "बीपी की दवा")).toBe("बाबूजी, बीपी की दवा का समय है।");
});
