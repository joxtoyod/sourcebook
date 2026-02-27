<script lang="ts">
	import { selectedNode } from '$lib/stores/diagram';
	import { onDestroy } from 'svelte';
	import { codeToTokens, type ThemedToken } from 'shiki';

	let content: string | null = null;
	let tokenLines: ThemedToken[][] | null = null;
	let error: string | null = null;
	let loading = false;
	let highlightLine: number | null = null;
	let lineContainer: HTMLDivElement | undefined;

	function detectLanguage(filePath: string): string {
		const ext = filePath.split('.').pop()?.toLowerCase() ?? '';
		const map: Record<string, string> = {
			ts: 'typescript', tsx: 'tsx', js: 'javascript', jsx: 'jsx',
			svelte: 'svelte', py: 'python', html: 'html', css: 'css',
			json: 'json', md: 'markdown', yaml: 'yaml', yml: 'yaml',
			sh: 'bash', rs: 'rust', go: 'go', java: 'java',
			c: 'c', cpp: 'cpp', rb: 'ruby', toml: 'toml',
		};
		return map[ext] ?? 'text';
	}

	// Resize state
	const MIN_WIDTH = 220;
	const MAX_WIDTH = 900;
	let paneWidth = 460;
	let resizing = false;
	let resizeStartX = 0;
	let resizeStartWidth = 0;

	function onResizeStart(e: PointerEvent) {
		resizing = true;
		resizeStartX = e.clientX;
		resizeStartWidth = paneWidth;
		(e.currentTarget as Element).setPointerCapture(e.pointerId);
	}

	function onResizeMove(e: PointerEvent) {
		if (!resizing) return;
		// Drag leftward increases width (pane is on the right)
		const delta = resizeStartX - e.clientX;
		paneWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, resizeStartWidth + delta));
	}

	function onResizeEnd() {
		resizing = false;
	}

	function parseFilePath(filePath: string): { path: string; line: number | null } {
		const lastColon = filePath.lastIndexOf(':');
		if (lastColon > 0) {
			const suffix = filePath.slice(lastColon + 1);
			const n = parseInt(suffix, 10);
			if (!isNaN(n) && String(n) === suffix) {
				return { path: filePath.slice(0, lastColon), line: n };
			}
		}
		return { path: filePath, line: null };
	}

	function filename(path: string): string {
		return path.split('/').pop() ?? path;
	}

	async function loadFile(filePath: string) {
		const { path, line } = parseFilePath(filePath);
		highlightLine = line;
		content = null;
		tokenLines = null;
		error = null;
		loading = true;
		try {
			const res = await fetch(`/api/file?path=${encodeURIComponent(filePath)}`);
			const json = await res.json();
			if (!res.ok) {
				error = json.detail ?? 'Failed to load file';
			} else {
				content = json.content;
				const lang = detectLanguage(path);
				if (lang !== 'text') {
					try {
						const result = await codeToTokens(json.content, {
							lang,
							theme: 'github-dark',
						});
						tokenLines = result.tokens;
					} catch {
						tokenLines = null;
					}
				}
			}
		} catch (e) {
			error = 'Network error';
		} finally {
			loading = false;
		}
	}

	// Reactive: load file whenever selectedNode changes
	$: if ($selectedNode?.file_path) {
		loadFile($selectedNode.file_path);
	}

	// Scroll highlighted line into view after content renders
	$: if (content !== null && highlightLine !== null && lineContainer) {
		// Use a microtask to allow the DOM to update first
		Promise.resolve().then(() => {
			const el = lineContainer?.querySelector<HTMLElement>(`[data-line="${highlightLine}"]`);
			el?.scrollIntoView({ block: 'center' });
		});
	}

	function close() {
		selectedNode.set(null);
	}

	onDestroy(() => {
		// Nothing to clean up
	});
</script>

{#if $selectedNode}
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div class="code-pane" style="width: {paneWidth}px;">
		<div
			class="resize-handle"
			class:resizing
			on:pointerdown={onResizeStart}
			on:pointermove={onResizeMove}
			on:pointerup={onResizeEnd}
			on:pointercancel={onResizeEnd}
		></div>
		<div class="pane-header">
			<span class="pane-filename" title={$selectedNode.file_path}>
				{filename(parseFilePath($selectedNode.file_path ?? '').path)}
				{#if parseFilePath($selectedNode.file_path ?? '').line !== null}
					<span class="pane-line-badge">:{parseFilePath($selectedNode.file_path ?? '').line}</span>
				{/if}
			</span>
			<button class="pane-close" on:click={close} aria-label="Close code pane">✕</button>
		</div>

		<div class="pane-body">
			{#if loading}
				<div class="pane-status">Loading…</div>
			{:else if error}
				<div class="pane-status pane-error">{error}</div>
			{:else if content !== null}
				<div class="line-container" bind:this={lineContainer}>
					<pre class="code-block">{#each content.split('\n') as line, i}<div
							class="code-line"
							class:highlight={highlightLine !== null && i + 1 === highlightLine}
							data-line={i + 1}
						><span class="line-num">{i + 1}</span><span class="line-text">{#if tokenLines}{#each tokenLines[i] ?? [] as token}<span style="color: {token.color ?? 'inherit'}">{token.content}</span>{/each}{:else}{line}{/if}</span></div>{/each}</pre>
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.code-pane {
		flex-shrink: 0;
		display: flex;
		flex-direction: column;
		background: #0f172a;
		border-left: 1px solid #1e293b;
		overflow: hidden;
		height: 100%;
		position: relative;
	}

	.resize-handle {
		position: absolute;
		left: 0;
		top: 0;
		bottom: 0;
		width: 5px;
		cursor: col-resize;
		z-index: 10;
		background: transparent;
		transition: background 0.15s;
	}

	.resize-handle:hover,
	.resize-handle.resizing {
		background: #4f9cf9;
	}

	.pane-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 14px;
		border-bottom: 1px solid #1e293b;
		background: #0f172a;
		flex-shrink: 0;
	}

	.pane-filename {
		color: #e2e8f0;
		font-size: 13px;
		font-family: monospace;
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		flex: 1;
		min-width: 0;
	}

	.pane-line-badge {
		color: #64748b;
		font-weight: 400;
	}

	.pane-close {
		background: none;
		border: none;
		color: #475569;
		cursor: pointer;
		font-size: 14px;
		padding: 2px 6px;
		border-radius: 4px;
		flex-shrink: 0;
		margin-left: 8px;
		line-height: 1;
	}

	.pane-close:hover {
		background: #1e293b;
		color: #94a3b8;
	}

	.pane-body {
		flex: 1;
		overflow-y: auto;
		overflow-x: auto;
	}

	.pane-status {
		padding: 20px;
		color: #475569;
		font-size: 13px;
	}

	.pane-error {
		color: #f87171;
	}

	.line-container {
		height: 100%;
	}

	.code-block {
		margin: 0;
		padding: 8px 0;
		font-family: 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace;
		font-size: 12px;
		line-height: 1.6;
		background: transparent;
		color: #e2e8f0;
		min-width: max-content;
	}

	.code-line {
		display: flex;
		padding: 0 12px;
		min-width: max-content;
	}

	.code-line.highlight {
		background: rgba(251, 191, 36, 0.15);
		border-left: 3px solid #fbbf24;
		padding-left: 9px;
	}

	.line-num {
		color: #334155;
		user-select: none;
		min-width: 3.5ch;
		text-align: right;
		margin-right: 16px;
		flex-shrink: 0;
	}

	.code-line.highlight .line-num {
		color: #fbbf24;
	}

	.line-text {
		white-space: pre;
		color: #e2e8f0;
	}
</style>
