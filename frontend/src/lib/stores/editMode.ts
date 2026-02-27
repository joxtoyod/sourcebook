import { writable } from 'svelte/store';

export interface EditModeState {
	groupId: string;
	groupLabel: string;
}

export const editMode = writable<EditModeState | null>(null);
