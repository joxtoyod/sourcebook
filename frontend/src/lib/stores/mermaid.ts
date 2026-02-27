import { writable } from 'svelte/store';

export interface MermaidCard {
	id: string;
	title: string;
	syntax: string;
	x: number;
	y: number;
	minimized: boolean;
	is_proposed?: boolean;
	width?: number;
	height?: number;
}

export const mermaidCards = writable<MermaidCard[]>([]);
