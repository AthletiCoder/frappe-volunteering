import type { APIRequestContext } from '@playwright/test';
import type { PersonaKey } from './personas';
import { callMethod } from './frappe';

const API = 'volunteering.volunteering.e2e_api';

export interface CastEntry {
	email: string;
	employee: string | null;
	exists_user: boolean;
	grade?: string;
}

export type Cast = Record<string, CastEntry>;

export async function getCast(
	request: APIRequestContext,
	persona: PersonaKey = 'admin',
): Promise<Cast> {
	return callMethod<Cast>(request, `${API}.get_cast`, {}, persona);
}

export async function getFixtures(
	request: APIRequestContext,
	persona: PersonaKey = 'admin',
): Promise<{ project: string; department: string }> {
	return callMethod(request, `${API}.get_fixtures`, {}, persona);
}

/** @deprecated Fixtures are seeded once in globalSetup; use getFixtures(). */
export async function ensureFixtures(
	request: APIRequestContext,
	persona: PersonaKey = 'admin',
): Promise<{ project: string; department: string }> {
	return getFixtures(request, persona);
}

export async function cleanupDay(
	request: APIRequestContext,
	employee: string,
	date: string,
	persona: PersonaKey = 'admin',
): Promise<void> {
	await callMethod(request, `${API}.cleanup_day`, { employee, date }, persona);
}

export async function cleanupLeaveSpan(
	request: APIRequestContext,
	employee: string,
	fromDate: string,
	toDate: string,
	persona: PersonaKey = 'admin',
): Promise<void> {
	await callMethod(
		request,
		`${API}.cleanup_leave_span`,
		{ employee, from_date: fromDate, to_date: toDate },
		persona,
	);
}

export async function cleanupEmployeeAdvances(
	request: APIRequestContext,
	employee: string,
	persona: PersonaKey = 'admin',
): Promise<void> {
	await callMethod(request, `${API}.cleanup_employee_advances`, { employee }, persona);
}

export async function e2eCall<T>(
	request: APIRequestContext,
	method: string,
	args: Record<string, unknown> = {},
	persona: PersonaKey = 'admin',
): Promise<T> {
	return callMethod<T>(request, `${API}.${method}`, args, persona);
}

function parseLocalDate(isoDate: string): Date {
	const [year, month, day] = isoDate.split('-').map(Number);
	return new Date(year, month - 1, day);
}

function formatLocalDate(d: Date): string {
	const year = d.getFullYear();
	const month = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
}

export function addDays(isoDate: string, days: number): string {
	const d = parseLocalDate(isoDate);
	d.setDate(d.getDate() + days);
	return formatLocalDate(d);
}

export function todayLocal(): string {
	return new Intl.DateTimeFormat('en-CA', {
		timeZone: process.env.E2E_TZ || 'Asia/Kolkata',
		year: 'numeric',
		month: '2-digit',
		day: '2-digit',
	}).format(new Date());
}

/** Org weekly off is Wednesday (leave_setup.WEEKLY_OFF_DAY). */
export function isWeeklyOff(isoDate: string): boolean {
	return parseLocalDate(isoDate).getDay() === 3;
}

/** Last Wednesday strictly before today — used for holiday attendance cases. */
export function lastWednesday(): string {
	let date = addDays(todayLocal(), -1);
	while (!isWeeklyOff(date)) {
		date = addDays(date, -1);
	}
	return date;
}

/**
 * Calendar offset from today, then skip Wednesday.
 * Negative offsets walk backward so grace-closed days stay in the past.
 */
export function workingDayFromToday(offset: number): string {
	let date = addDays(todayLocal(), offset);
	const direction: 1 | -1 = offset >= 0 ? 1 : -1;
	for (let i = 0; i < 14 && isWeeklyOff(date); i++) {
		date = addDays(date, direction);
	}
	return date;
}

export function expectErrorContains(error: string, ...needles: string[]): void {
	const lower = error.toLowerCase();
	for (const n of needles) {
		if (!lower.includes(n.toLowerCase())) {
			throw new Error(`Expected error to contain "${n}" but got: ${error}`);
		}
	}
}
