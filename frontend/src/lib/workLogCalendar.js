export function monthDates(month) {
  if (!/^\d{4}-\d{2}$/.test(month)) return [];
  const [year, number] = month.split("-").map(Number);
  if (number < 1 || number > 12 || year < 1) return [];
  const start = new Date(0);
  start.setFullYear(year, number - 1, 1);
  start.setHours(12, 0, 0, 0);
  const padding = (start.getDay() + 6) % 7;
  const end = new Date(start); end.setMonth(number, 0);
  const dates = Array(padding).fill(null);
  for (let day = 1; day <= end.getDate(); day++) dates.push(`${month}-${String(day).padStart(2, "0")}`);
  while (dates.length % 7) dates.push(null);
  return dates;
}

export function offsetMonth(month, offset) {
  const [year, number] = month.split("-").map(Number);
  const date = new Date(0); date.setFullYear(year, number - 1 + offset, 1);
  return `${String(date.getFullYear()).padStart(4, "0")}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

export const hoursLabel = value => Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });

// Keep the saved decimal value untouched until the user changes a duration.
export function durationMinutes(value) {
  if (value === "" || value == null || !Number.isFinite(Number(value)) || Number(value) < 0) return 0;
  return Math.round(Number(value) * 60);
}
export function durationHours(hours, minutes) {
  if (!Number.isInteger(hours) || !Number.isInteger(minutes) || hours < 0 || hours > 24 || minutes < 0 || minutes > 59 || (hours === 24 && minutes)) throw new RangeError("Invalid duration");
  return Number(((hours * 60 + minutes) / 60).toFixed(9));
}
export function durationLabel(value) {
  const total = durationMinutes(value), hours = Math.floor(total / 60), minutes = total % 60;
  return [hours ? hours + " h" : "", minutes || !hours ? minutes + " min" : ""].filter(Boolean).join(" ");
}

// Show older separately stored links in Details without changing saved data on load.
export function workLogDetails(description, legacyLink) {
  const details = description || "", link = (legacyLink || "").trim();
  return !link || details.includes(link) ? details : [details, link].filter(Boolean).join("\n\n");
}
