import test from "node:test";
import assert from "node:assert/strict";
import { monthDates, offsetMonth, hoursLabel } from "../src/lib/workLogCalendar.js";

test("month starts on Monday and pads complete weeks", () => {
  const dates = monthDates("2026-11");
  assert.equal(dates.length, 42);
  assert.deepEqual(dates.slice(0, 6), Array(6).fill(null));
  assert.equal(dates[6], "2026-11-01");
  assert.equal(dates.filter(Boolean).length, 30);
});
test("leap February contains every date exactly once", () => {
  const dates = monthDates("2024-02");
  assert.equal(dates.length, 35);
  assert.equal(dates.filter(Boolean).length, 29);
  assert.equal(new Set(dates.filter(Boolean)).size, 29);
  assert.equal(dates[3], "2024-02-01");
  assert.equal(dates[31], "2024-02-29");
});
test("Monday-start four-week month needs no extra row", () => {
  const dates = monthDates("2021-02");
  assert.equal(dates.length, 28);
  assert.equal(dates[0], "2021-02-01");
});
test("December and January navigation crosses the year correctly", () => {
  assert.equal(offsetMonth("2026-12", 1), "2027-01");
  assert.equal(offsetMonth("2026-01", -1), "2025-12");
});
test("invalid month cannot produce calendar cells", () => {
  for (const month of ["", "2026-00", "2026-13", "2026-1", "0000-01"]) assert.deepEqual(monthDates(month), []);
});
test("hours retain meaningful decimals without long trailing zeros", () => {
  assert.equal(hoursLabel(6.5), "6.5");
  assert.equal(hoursLabel(6), "6");
  assert.equal(hoursLabel(0), "0");
});

test("duration selectors preserve minute boundaries and validate the daily maximum", async () => {
  const { durationMinutes, durationHours, durationLabel } = await import("../src/lib/workLogCalendar.js");
  for (const total of [1, 15, 59, 60, 90, 359, 360, 1439, 1440]) assert.equal(durationMinutes(durationHours(Math.floor(total / 60), total % 60)), total);
  for (const [h, m] of [[24, 1], [25, 0], [-1, 0], [0, 60], [0, -1]]) assert.throws(() => durationHours(h, m), RangeError);
  assert.equal(durationLabel(2.5), "2 h 30 min");
  assert.equal(durationLabel(37), "37 h");
  assert.equal(durationLabel(0.016666667), "1 min");
  assert.equal(durationLabel("NaN"), "0 min");
});

test("older output links remain part of Details without duplication or data loss", async () => {
  const { workLogDetails } = await import("../src/lib/workLogCalendar.js");
  const link = "https://example.org/lesson-plan";
  assert.equal(workLogDetails("Prepared lesson materials.", link), "Prepared lesson materials.\n\n" + link);
  assert.equal(workLogDetails("Prepared materials: " + link, link), "Prepared materials: " + link);
  assert.equal(workLogDetails("Prepared lesson materials.", ""), "Prepared lesson materials.");
});
