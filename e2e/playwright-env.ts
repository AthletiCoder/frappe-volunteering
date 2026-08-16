import fs from 'fs';
import os from 'os';
import path from 'path';

/**
 * Prefer a workspace browser cache (writable in the agent sandbox).
 * Fall back to the user cache, then Cursor's session cache if it already
 * has Chromium — never point at an empty throwaway path.
 */
function hasChromium(dir: string): boolean {
	if (!dir || !fs.existsSync(dir)) {
		return false;
	}
	try {
		return fs.readdirSync(dir).some((name) => name.startsWith('chromium'));
	} catch {
		return false;
	}
}

const workspaceBrowsers = path.resolve(__dirname, '..', '.playwright-browsers');
const stableBrowsers = path.join(os.homedir(), 'Library/Caches/ms-playwright');
const current = process.env.PLAYWRIGHT_BROWSERS_PATH || '';

if (hasChromium(workspaceBrowsers)) {
	process.env.PLAYWRIGHT_BROWSERS_PATH = workspaceBrowsers;
} else if (hasChromium(current)) {
	// keep session cache
} else if (hasChromium(stableBrowsers)) {
	process.env.PLAYWRIGHT_BROWSERS_PATH = stableBrowsers;
} else {
	process.env.PLAYWRIGHT_BROWSERS_PATH = workspaceBrowsers;
}
