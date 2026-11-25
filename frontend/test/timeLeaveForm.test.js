import test from "node:test";
import assert from "node:assert/strict";
import { timeLeaveHasCategory, timeLeaveCategory } from "../src/lib/timeLeaveForm.js";

test("ordinary leave keeps its medical category", () => {
  for (const type of ["Privilege Leave", "Compensatory Leave", "Leave Without Pay"]) {
    assert.equal(timeLeaveHasCategory(type), true);
    assert.equal(timeLeaveCategory(type, "Medical"), "Medical");
  }
});

test("parental and optional leave do not inherit medical requirements", () => {
  for (const type of ["Maternity Leave", "Paternity Leave", "Optional Holiday"]) {
    assert.equal(timeLeaveHasCategory(type), false);
    assert.equal(timeLeaveCategory(type, "Medical"), "Normal");
  }
});
