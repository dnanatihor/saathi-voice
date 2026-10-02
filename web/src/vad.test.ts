import { expect, test } from "vitest";
import { speechShouldEnd } from "./vad";

test("silence after speech ends the turn", () => {
  const levels = [0.05, ...Array.from({ length: 59 }, () => 0)];
  expect(speechShouldEnd(levels)).toBe(false);
  levels.push(0);
  expect(speechShouldEnd(levels)).toBe(true);
});

test("quiet audio with no speech keeps the turn open", () => {
  expect(speechShouldEnd(Array.from({ length: 80 }, () => 0))).toBe(false);
});
