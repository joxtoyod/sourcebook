import { writable } from 'svelte/store';

export interface DiagramGroup {
	id: string;
	label: string;
	color: string;
}

export interface DiagramNode {
	id: string;
	label: string;
	type: 'module' | 'service' | 'database' | 'external';
	x: number;
	y: number;
	description?: string;
	is_overridden?: boolean;
	is_proposed?: boolean;
	file_path?: string;
	group_id?: string;
}

export interface DiagramEdge {
	id: string;
	source: string;   // matches DiagramNode.id; backend may return source_id
	source_id?: string;
	target: string;
	target_id?: string;
	label?: string;
	type: 'dependency' | 'data_flow' | 'api_call';
	is_proposed?: boolean;
}

export interface DiagramState {
	nodes: DiagramNode[];
	edges: DiagramEdge[];
	groups: DiagramGroup[];
}

export const diagram = writable<DiagramState>({ nodes: [], edges: [], groups: [] });

export const selectedNode = writable<DiagramNode | null>(null);
