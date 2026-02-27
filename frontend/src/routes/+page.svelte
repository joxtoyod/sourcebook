<script lang="ts">
	import { onMount } from 'svelte';
	import Canvas from '$lib/components/Canvas.svelte';
	import CodePane from '$lib/components/CodePane.svelte';
	import FloatingChat from '$lib/components/FloatingChat.svelte';
	import RequirementsPanel from '$lib/components/RequirementsPanel.svelte';
	import VersionHistory from '$lib/components/VersionHistory.svelte';
	import { diagram } from '$lib/stores/diagram';
	import { connect, isConnected } from '$lib/ws';

	let showHistory = false;

	onMount(() => {
		connect();
	});

	function closeHistory() {
		showHistory = false;
	}
</script>

<div class="workspace">
	<Canvas />
	<CodePane />
	{#if $isConnected && $diagram.nodes.length === 0}
		<div class="canvas-overlay">
			<RequirementsPanel />
		</div>
	{/if}
	{#if $isConnected && $diagram.nodes.length > 0}
		<FloatingChat />
	{/if}
	{#if $isConnected && $diagram.nodes.length > 0}
		<div class="top-left-overlay">
			<button class="history-btn" on:click={() => (showHistory = !showHistory)}>
				⟳ History
			</button>
			{#if showHistory}
				<VersionHistory on:close={closeHistory} />
			{/if}
		</div>
	{/if}
</div>

<style>
	.workspace {
		display: flex;
		height: 100vh;
		overflow: hidden;
		position: relative;
	}

	.canvas-overlay {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 20;
		pointer-events: none;
	}

	.top-left-overlay {
		position: absolute;
		top: 14px;
		left: 18px;
		z-index: 50;
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 6px;
	}

	.history-btn {
		background: #1e293b;
		border: 1px solid #334155;
		border-radius: 6px;
		color: #e2e8f0;
		cursor: pointer;
		font-size: 13px;
		padding: 6px 12px;
		transition: border-color 0.15s;
	}

	.history-btn:hover {
		border-color: #475569;
	}
</style>
