<script lang="ts">
	import { createEventDispatcher, tick } from 'svelte';
	import { agentLogs, type AgentLogEntry } from '$lib/ws';

	const dispatch = createEventDispatcher();

	const MIN_WIDTH = 250;
	const MAX_WIDTH = 600;
	let paneWidth = 350;
	let resizing = false;
	let resizeStartX = 0;
	let resizeStartWidth = 0;

	let logContainer: HTMLDivElement | undefined;
	let autoScroll = true;

	function onResizeStart(e: PointerEvent) {
		resizing = true;
		resizeStartX = e.clientX;
		resizeStartWidth = paneWidth;
		(e.currentTarget as Element).setPointerCapture(e.pointerId);
	}

	function onResizeMove(e: PointerEvent) {
		if (!resizing) return;
		const delta = resizeStartX - e.clientX;
		paneWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, resizeStartWidth + delta));
	}

	function onResizeEnd() {
		resizing = false;
	}

	function formatTime(ts: string): string {
		try {
			const d = new Date(ts);
			return d.toTimeString().slice(0, 8);
		} catch {
			return ts;
		}
	}

	function clearLogs() {
		agentLogs.set([]);
	}

	// Auto-scroll to bottom when new entries arrive
	$: if ($agentLogs && logContainer && autoScroll) {
		tick().then(() => {
			if (logContainer) {
				logContainer.scrollTop = logContainer.scrollHeight;
			}
		});
	}

	function onScroll() {
		if (!logContainer) return;
		const atBottom = logContainer.scrollHeight - logContainer.scrollTop - logContainer.clientHeight < 40;
		if (autoScroll !== atBottom) autoScroll = atBottom;
	}
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="log-pane" style="width: {paneWidth}px;">
	<div
		class="resize-handle"
		class:resizing
		on:pointerdown={onResizeStart}
		on:pointermove={onResizeMove}
		on:pointerup={onResizeEnd}
		on:pointercancel={onResizeEnd}
	></div>
	<div class="pane-header">
		<span class="pane-title">Agent Log</span>
		<div class="header-actions">
			<button class="clear-btn" on:click={clearLogs}>Clear</button>
			<button class="close-btn" on:click={() => dispatch('close')} aria-label="Close log pane">✕</button>
		</div>
	</div>

	<div class="pane-body" bind:this={logContainer} on:scroll={onScroll}>
		{#if $agentLogs.length === 0}
			<div class="empty-state">No activity yet. Send a chat message to see logs.</div>
		{:else}
			{#each $agentLogs as entry (entry.ts + entry.msg)}
				<div class="log-entry">
					<span class="log-time">[{formatTime(entry.ts)}]</span>
					<span class="log-level" class:level-error={entry.level === 'error'}>{entry.level}</span>
					<span class="log-msg">{entry.msg}</span>
				</div>
			{/each}
		{/if}
	</div>
</div>

<style>
	.log-pane {
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

	.pane-title {
		color: #e2e8f0;
		font-size: 13px;
		font-family: monospace;
		font-weight: 600;
	}

	.header-actions {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.clear-btn {
		background: none;
		border: 1px solid #334155;
		border-radius: 4px;
		color: #64748b;
		cursor: pointer;
		font-size: 11px;
		padding: 2px 8px;
		line-height: 1.5;
	}

	.clear-btn:hover {
		border-color: #475569;
		color: #94a3b8;
	}

	.close-btn {
		background: none;
		border: none;
		color: #475569;
		cursor: pointer;
		font-size: 14px;
		padding: 2px 6px;
		border-radius: 4px;
		flex-shrink: 0;
		line-height: 1;
	}

	.close-btn:hover {
		background: #1e293b;
		color: #94a3b8;
	}

	.pane-body {
		flex: 1;
		overflow-y: auto;
		overflow-x: hidden;
		padding: 6px 0;
	}

	.empty-state {
		padding: 20px 14px;
		color: #475569;
		font-size: 12px;
		font-family: monospace;
	}

	.log-entry {
		display: flex;
		align-items: baseline;
		gap: 6px;
		padding: 2px 14px;
		font-family: 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace;
		font-size: 12px;
		line-height: 1.6;
	}

	.log-entry:hover {
		background: #0f1f35;
	}

	.log-time {
		color: #334155;
		flex-shrink: 0;
		user-select: none;
	}

	.log-level {
		color: #475569;
		flex-shrink: 0;
		font-size: 11px;
		min-width: 3ch;
	}

	.log-level.level-error {
		color: #f87171;
	}

	.log-msg {
		color: #94a3b8;
		word-break: break-word;
	}
</style>
