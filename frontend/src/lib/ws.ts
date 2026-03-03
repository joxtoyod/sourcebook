import { writable } from 'svelte/store';
import { diagram } from './stores/diagram';
import { mermaidCards } from './stores/mermaid';

const WS_URL =
	typeof window !== 'undefined'
		? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`
		: 'ws://localhost:8000/ws';

export interface ChatMessage {
	role: 'user' | 'assistant';
	content: string;
	timestamp: string;
}

export interface AgentLogEntry {
	ts: string;
	level: string;
	msg: string;
}

export const messages = writable<ChatMessage[]>([]);
export const isConnected = writable(false);
export const isStreaming = writable(false);
export const projectRoot = writable<string>('');
export const editorType = writable<string>('vscode');
export const projectName = writable<string>('');
export const agentLogs = writable<AgentLogEntry[]>([]);

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

export function connect(): void {
	if (reconnectTimer !== null) {
		clearTimeout(reconnectTimer);
		reconnectTimer = null;
	}
	if (ws) ws.close();

	ws = new WebSocket(WS_URL);

	ws.onopen = () => {
		isConnected.set(true);
		fetch('/api/project-root')
			.then((r) => r.json())
			.then((data: { project_root: string; editor: string }) => {
				projectRoot.set(data.project_root);
				editorType.set(data.editor);
			})
			.catch(() => {});
	};

	ws.onclose = () => {
		isConnected.set(false);
		isStreaming.set(false);
		reconnectTimer = setTimeout(connect, 3000);
	};

	ws.onerror = () => ws?.close();

	ws.onmessage = (event: MessageEvent) => {
		try {
			handleMessage(JSON.parse(event.data as string));
		} catch {
			// ignore malformed frames
		}
	};
}

function handleMessage(msg: Record<string, unknown>): void {
	if (msg.type === 'chat_chunk') {
		const chunk = msg.content as string;
		messages.update((prev) => {
			const last = prev[prev.length - 1];
			if (last?.role === 'assistant') {
				return [...prev.slice(0, -1), { ...last, content: last.content + chunk }];
			}
			return [...prev, { role: 'assistant', content: chunk, timestamp: now() }];
		});
		isStreaming.set(true);
	} else if (msg.type === 'chat_done') {
		isStreaming.set(false);
	} else if (msg.type === 'diagram_update') {
		diagram.set({
			nodes: (msg.nodes as unknown[]) as DiagramState['nodes'],
			edges: (msg.edges as unknown[]) as DiagramState['edges'],
			groups: ((msg.groups as unknown[]) ?? []) as DiagramState['groups'],
		});
	} else if (msg.type === 'mermaid_diagrams') {
		mermaidCards.set(
			(msg.cards as Record<string, unknown>[]).map((c) => ({
				id: c.id as string,
				title: (c.title as string) || 'Flow Diagram',
				syntax: c.syntax as string,
				x: c.x as number,
				y: c.y as number,
				minimized: Boolean(c.minimized),
				is_proposed: Boolean(c.is_proposed)
			}))
		);
	} else if (msg.type === 'project_name') {
		projectName.set(msg.name as string);
	} else if (msg.type === 'mermaid_diagram') {
		mermaidCards.update((cards) => [
			...cards,
			{
				id: msg.id as string,
				title: (msg.title as string) || 'Flow Diagram',
				syntax: msg.syntax as string,
				x: msg.x as number,
				y: msg.y as number,
				minimized: false,
				is_proposed: Boolean(msg.is_proposed)
			}
		]);
	} else if (msg.type === 'mermaid_update') {
		mermaidCards.update((cards) =>
			cards.map((c) => (c.id === (msg.id as string) ? { ...c, syntax: msg.syntax as string } : c))
		);
	} else if (msg.type === 'spec_chunk') {
		const chunk = msg.text as string;
		messages.update((prev) => {
			const last = prev[prev.length - 1];
			if (last?.role === 'assistant') {
				return [...prev.slice(0, -1), { ...last, content: last.content + chunk }];
			}
			return [...prev, { role: 'assistant', content: chunk, timestamp: now() }];
		});
		isStreaming.set(true);
	} else if (msg.type === 'spec_done') {
		isStreaming.set(false);
		messages.update((prev) => {
			const last = prev[prev.length - 1];
			const notice = `\n\n---\nSpec written to \`${msg.spec_path as string}\`. Feature accepted.`;
			if (last?.role === 'assistant') {
				return [...prev.slice(0, -1), { ...last, content: last.content + notice }];
			}
			return prev;
		});
	} else if (msg.type === 'spec_error') {
		isStreaming.set(false);
		messages.update((prev) => {
			const last = prev[prev.length - 1];
			const errMsg = `\n\n[Spec generation failed: ${msg.error as string}]`;
			if (last?.role === 'assistant') {
				return [...prev.slice(0, -1), { ...last, content: last.content + errMsg }];
			}
			return prev;
		});
	} else if (msg.type === 'agent_log') {
		agentLogs.update((prev) => [...prev.slice(-499), msg.entry as AgentLogEntry]);
	} else if (msg.type === 'agent_logs_history') {
		const incoming = msg.entries as AgentLogEntry[];
		agentLogs.update((prev) => {
			const seen = new Set(prev.map((e) => e.ts + e.msg));
			return [...incoming.filter((e) => !seen.has(e.ts + e.msg)), ...prev];
		});
	}
}

import type { DiagramState } from './stores/diagram';

export function sendChat(content: string, diagramContext: DiagramState): void {
	if (!ws || ws.readyState !== WebSocket.OPEN) return;
	messages.update((prev) => [...prev, { role: 'user', content, timestamp: now() }]);
	isStreaming.set(true);
	ws.send(JSON.stringify({ type: 'chat', content, diagram_context: diagramContext }));
}

export function sendMermaidMove(id: string, x: number, y: number): void {
	if (!ws || ws.readyState !== WebSocket.OPEN) return;
	ws.send(JSON.stringify({ type: 'mermaid_move', id, x, y }));
}

export function sendMermaidMinimize(id: string): void {
	if (!ws || ws.readyState !== WebSocket.OPEN) return;
	ws.send(JSON.stringify({ type: 'mermaid_minimize', id }));
}

export function sendMermaidRestore(id: string): void {
	if (!ws || ws.readyState !== WebSocket.OPEN) return;
	ws.send(JSON.stringify({ type: 'mermaid_restore', id }));
}

export function sendMermaidResize(id: string, width: number, height: number): void {
	if (!ws || ws.readyState !== WebSocket.OPEN) return;
	ws.send(JSON.stringify({ type: 'mermaid_resize', id, width, height }));
}

export function sendMermaidRename(id: string, title: string): void {
	if (!ws || ws.readyState !== WebSocket.OPEN) return;
	ws.send(JSON.stringify({ type: 'mermaid_rename', id, title }));
}

export function sendMermaidDelete(id: string): void {
	if (!ws || ws.readyState !== WebSocket.OPEN) return;
	ws.send(JSON.stringify({ type: 'mermaid_delete', id }));
}

export function sendOverride(nodeId: string, patch: Record<string, unknown>): void {
	if (!ws || ws.readyState !== WebSocket.OPEN) return;
	ws.send(JSON.stringify({ type: 'override_node', node_id: nodeId, patch }));
}

export function sendFilePathOverride(nodeId: string, filePath: string): void {
	sendOverride(nodeId, { file_path: filePath });
}

export function sendProjectName(name: string): void {
	if (!ws || ws.readyState !== WebSocket.OPEN) return;
	ws.send(JSON.stringify({ type: 'set_project_name', name }));
}

export function sendFeatureRequest(
	featureName: string,
	requirements: string,
	intentions: string,
	diagramContext: DiagramState
): void {
	if (!ws || ws.readyState !== WebSocket.OPEN) return;
	isStreaming.set(true);
	ws.send(
		JSON.stringify({
			type: 'feature_request',
			feature_name: featureName,
			requirements,
			intentions,
			diagram_context: diagramContext
		})
	);
}

export function sendAcceptFeature(featureGroupId: string): void {
	if (!ws || ws.readyState !== WebSocket.OPEN) return;
	ws.send(JSON.stringify({ type: 'accept_feature', feature_group_id: featureGroupId }));
}

export function sendAcceptFeatureWithSpec(featureGroupId: string): void {
	if (!ws || ws.readyState !== WebSocket.OPEN) return;
	isStreaming.set(true);
	messages.update((prev) => [
		...prev,
		{ role: 'assistant', content: 'Generating spec...', timestamp: now() }
	]);
	ws.send(JSON.stringify({ type: 'accept_feature_with_spec', feature_group_id: featureGroupId }));
}

export function sendRejectFeature(featureGroupId: string): void {
	if (!ws || ws.readyState !== WebSocket.OPEN) return;
	ws.send(JSON.stringify({ type: 'reject_feature', feature_group_id: featureGroupId }));
}

export function sendAcceptNode(nodeId: string): void {
	if (!ws || ws.readyState !== WebSocket.OPEN) return;
	ws.send(JSON.stringify({ type: 'accept_node', node_id: nodeId }));
}

export function sendGetLogs(): void {
	if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'get_logs' }));
}

export function sendEditFeature(content: string, featureGroupId: string, diagramContext: DiagramState): void {
	if (!ws || ws.readyState !== WebSocket.OPEN) return;
	messages.update((prev) => [
		...prev,
		{ role: 'user', content: `[Editing: ${featureGroupId}]\n${content}`, timestamp: now() }
	]);
	isStreaming.set(true);
	ws.send(JSON.stringify({ type: 'edit_feature', content, feature_group_id: featureGroupId, diagram_context: diagramContext }));
}

function now(): string {
	return new Date().toISOString();
}
