// Who is reading on this device (no login: the family picks their newspaper), plus small helpers.

const KEY = 'eilkurier.reader';

function stored(): number | null {
	try {
		const value = Number(localStorage.getItem(KEY));
		return Number.isInteger(value) && value > 0 ? value : null;
	} catch {
		return null;
	}
}

export const household = $state({ readerId: stored() });

export function chooseReader(id: number | null): void {
	household.readerId = id;
	try {
		if (id === null) localStorage.removeItem(KEY);
		else localStorage.setItem(KEY, String(id));
	} catch {
		/* storage unavailable */
	}
}

const avatarColors = ['blue', 'green', 'violet', 'orange', 'red', 'grey'] as const;

export function avatarColor(id: number): string {
	return avatarColors[(id - 1) % avatarColors.length];
}

export function initials(name: string): string {
	const parts = name.trim().split(/\s+/).filter(Boolean);
	const letters =
		parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : (parts[0] ?? '?').slice(0, 2);
	return letters.toUpperCase();
}
