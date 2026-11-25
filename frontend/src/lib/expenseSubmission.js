const STATUS = "volunteering.volunteering.expense_claim_requests.get_expense_submission_status";

// Private to this origin and employee. Only an attempted submission is retained;
// receipt bytes are removed as soon as the server confirms its claim number.
export function expenseSubmissionStore() {
  let database;
  async function open() {
    if (!database) database = new Promise((resolve, reject) => {
      const request = indexedDB.open("sf-expense-submissions", 1);
      request.onupgradeneeded = () => request.result.createObjectStore("attempts");
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error("Could not save this submission safely on this device. Check browser storage and try again."));
    });
    return database;
  }
  async function operation(mode, key, value) {
    const db = await open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("attempts", mode), store = tx.objectStore("attempts");
      const request = mode === "readonly" ? store.get(key) : value === undefined ? store.delete(key) : store.put(value, key);
      tx.oncomplete = () => resolve(request.result);
      tx.onerror = tx.onabort = () => reject(new Error("Could not save this submission safely on this device. No new request was sent."));
    });
  }
  return { get: key => operation("readonly", key), put: (key, value) => operation("readwrite", key, value), remove: key => operation("readwrite", key) };
}

export class ExpenseSubmission {
  constructor({ slot, call, store = expenseSubmissionStore(), uuid = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, "0")).join(""), status = () => {} }) {
    Object.assign(this, { slot, call, store, uuid, status });
    this.pending = null; this.busy = false;
  }
  async restore() {
    this.pending = await this.store.get(this.slot) || null;
    if (!this.pending) return null;
    if (this.pending.result) return this.pending.result;
    try { return await this.check(); }
    catch (_) { this.status("A previous submission needs confirmation. Its details and receipts are saved on this device."); return null; }
  }
  async check() {
    if (!this.pending) return null;
    this.status("Checking whether your claim was saved…");
    const response = await this.call(STATUS, { request_key: this.pending.key });
    if (response.found) return this.complete(response.result);
    this.status("The server has not saved this submission. You can retry safely; your details and receipts are retained.");
    return null;
  }
  async complete(result) {
    this.pending = { key: this.pending.key, result };
    await this.store.put(this.slot, this.pending);
    this.status("");
    return result;
  }
  async submit(method, args, draft) {
    if (this.busy) throw new Error("Your submission is already being checked.");
    this.busy = true;
    try {
      if (!this.pending) this.pending = await this.store.get(this.slot) || null;
      if (this.pending) {
        if (this.pending.result) return this.pending.result;
        const recovered = await this.check();
        if (recovered) return recovered;
        // We only permit a changed payload after the server confirmed that the
        // previous request did not commit. An uncertain check never gets here.
        if (JSON.stringify({ method, args }) !== JSON.stringify({ method: this.pending.method, args: this.pending.args })) await this.reset();
      }
      if (!this.pending) {
        const pending = { key: this.uuid(), method, args: structuredClone(args), draft: structuredClone(draft) };
        await this.store.put(this.slot, pending);
        this.pending = pending;
      }
      return await this.send();
    } finally { this.busy = false; }
  }
  async retry() {
    if (!this.pending?.args) return this.pending?.result || null;
    return this.submit(this.pending.method, this.pending.args, this.pending.draft);
  }
  async send() {
    this.status("Submitting your claim and receipts. Please keep this page open…");
    try {
      const result = await this.call(this.pending.method, { ...this.pending.args, request_key: this.pending.key });
      return await this.complete(result);
    } catch (error) {
      if (error.status && error.status < 500) {
        await this.reset(); // A rejected request is rolled back by the server.
        throw error;
      }
      try {
        const recovered = await this.check();
        if (recovered) return recovered;
        this.status("The server has not saved this submission. You can retry safely; your details and receipts are retained.");
      } catch (_) {
        this.status("We could not confirm the result. Your details and receipts are saved. Use Retry saved submission; it will check before sending again.");
      }
      throw new Error("Submission confirmation was interrupted. Check the message above before continuing.");
    }
  }
  async reset() { await this.store.remove(this.slot); this.pending = null; this.status(""); }
}
