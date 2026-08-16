import * as fs from 'fs';
import * as path from 'path';

/** Load e2e/.env before reading credentials. */
export function loadE2eEnv(envPath = 'e2e/.env'): void {
	const resolved = path.resolve(envPath);
	if (!fs.existsSync(resolved)) {
		return;
	}
	for (const raw of fs.readFileSync(resolved, 'utf-8').split('\n')) {
		const line = raw.trim();
		if (!line || line.startsWith('#')) continue;
		const eq = line.indexOf('=');
		if (eq <= 0) continue;
		const key = line.slice(0, eq).trim();
		let value = line.slice(eq + 1).trim();
		if (
			(value.startsWith('"') && value.endsWith('"')) ||
			(value.startsWith("'") && value.endsWith("'"))
		) {
			value = value.slice(1, -1);
		}
		if (process.env[key] === undefined) {
			process.env[key] = value;
		}
	}
}

loadE2eEnv();

export type PersonaKey =
	| 'admin'
	| 'employee'
	| 'employee_b'
	| 'associate'
	| 'manager'
	| 'director'
	| 'chair'
	| 'hr'
	| 'accounts'
	| 'unpaid'
	| 'coordinator'
	| 'volunteer';

export interface PersonaCreds {
	key: PersonaKey;
	email: string;
	password: string;
	storageState: string;
	csrfFile: string;
}

const AUTH_DIR = 'e2e/.auth';

function envPassword(): string {
	return process.env.E2E_PASSWORD || 'E2eTestPass!26';
}

function cred(
	key: PersonaKey,
	emailEnv: string,
	defaultEmail: string,
): PersonaCreds {
	return {
		key,
		email: process.env[emailEnv] || defaultEmail,
		password: process.env[`E2E_${key.toUpperCase()}_PASSWORD`] || envPassword(),
		storageState: path.join(AUTH_DIR, `${key}.json`),
		csrfFile: path.join(AUTH_DIR, `${key}.csrf.json`),
	};
}

/** Canonical E2E cast — emails match volunteering.volunteering.e2e_seed.PERSONAS */
export const PERSONAS: Record<PersonaKey, PersonaCreds> = {
	admin: cred('admin', 'E2E_ADMIN_USER', process.env.FRAPPE_USER || 'Administrator'),
	employee: cred('employee', 'E2E_EMPLOYEE_USER', 'e2e.employee@sevamrita.local'),
	employee_b: cred('employee_b', 'E2E_EMPLOYEE_B_USER', 'e2e.employee.b@sevamrita.local'),
	associate: cred('associate', 'E2E_ASSOCIATE_USER', 'e2e.associate@sevamrita.local'),
	manager: cred('manager', 'E2E_MANAGER_USER', 'e2e.manager@sevamrita.local'),
	director: cred('director', 'E2E_DIRECTOR_USER', 'e2e.director@sevamrita.local'),
	chair: cred('chair', 'E2E_CHAIR_USER', 'e2e.chair@sevamrita.local'),
	hr: cred('hr', 'E2E_HR_USER', 'e2e.hr@sevamrita.local'),
	accounts: cred('accounts', 'E2E_ACCOUNTS_USER', 'e2e.accounts@sevamrita.local'),
	unpaid: cred('unpaid', 'E2E_UNPAID_USER', 'e2e.unpaid@sevamrita.local'),
	coordinator: cred(
		'coordinator',
		'E2E_COORDINATOR_USER',
		'e2e.coordinator@sevamrita.local',
	),
	volunteer: cred('volunteer', 'E2E_VOLUNTEER_USER', 'e2e.volunteer@sevamrita.local'),
};

PERSONAS.admin.password =
	process.env.E2E_ADMIN_PASSWORD ||
	process.env.FRAPPE_PASSWORD ||
	'password';

export const DEFAULT_PERSONA: PersonaKey = 'admin';

export function personaStorage(key: PersonaKey = DEFAULT_PERSONA): string {
	return PERSONAS[key].storageState;
}
