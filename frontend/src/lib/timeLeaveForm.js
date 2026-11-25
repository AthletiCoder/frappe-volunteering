export const timeLeaveHasCategory = type =>
  ["Privilege Leave", "Compensatory Leave", "Leave Without Pay"].includes(type);

export const timeLeaveCategory = (type, category) =>
  timeLeaveHasCategory(type) ? category : "Normal";
