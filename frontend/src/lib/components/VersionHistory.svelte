<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { getVersions, restoreVersion, type DiagramVersion } from '$lib/api';
	import { diagram } from '$lib/stores/diagram';
	import type { DiagramState } from '$lib/stores/diagram';

	const dispatch = createEventDispatcher<{ close: void }>();

	let versions: DiagramVersion[] = [];
	let loading = true;
	let error = '';
	let restoringId: string | null = null;

	onMount(() => {
		loadVersions();
	});

	async function loadVersions() {
		loading = true;
		error = '';
		try {
			versions = await getVersions();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load versions';
		} finally {
			loading = false;
		}
	}

	async function handleRestore(versionId: string) {
		if (restoringId) return;
		restoringId = versionId;
		try {
			const result = await restoreVersion(versionId);
			diagram.set({
				nodes: (result.nodes as unknown[]) as DiagramState['nodes'],
				edges: (result.edges as unknown[]) as DiagramState['edges'],
				groups: ((result.groups as unknown[]) ?? []) as DiagramState['groups'],
			});
			dispatch('close');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to restore version';
			restoringId = null;
		}
	}

	function formatDate(isoString: string): string {
		return new Date(isoString.replace(' ', 'T')).toLocaleString();
	}
</script>

<div class="panel">
	<div class="header">
		<span class="title">Version History</span>
		<button class="close-btn" on:click={() => dispatch('close')}>✕</button>
	</div>

	{#if loading}
		<div class="state-msg">Loading...</div>
	{:else if error}
		<div class="state-msg error">{error}</div>
	{:else if versions.length === 0}
		<div class="state-msg empty">No snapshots yet. Created automatically before each AI update.</div>
	{:else}
		<ul class="version-list">
			{#each versions as version (version.id)}
				<li class="version-item">
					<div class="version-meta">
						<span class="version-label" title={version.label}>{version.label}</span>
						<span class="version-date">{formatDate(version.created_at)}</span>
					</div>
					<button
						class="restore-btn"
						disabled={restoringId !== null}
						on:click={() => handleRestore(version.id)}
					>
						{restoringId === version.id ? '...' : 'Restore'}
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.panel {
		width: 300px;
		max-height: 420px;
		background: #1e293b;
		border: 1px solid #334155;
		border-radius: 12px;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 14px;
		border-bottom: 1px solid #334155;
	}

	.title {
		font-size: 13px;
		font-weight: 600;
		color: #e2e8f0;
	}

	.close-btn {
		background: none;
		border: none;
		color: #94a3b8;
		cursor: pointer;
		font-size: 13px;
		padding: 0;
		line-height: 1;
	}

	.close-btn:hover {
		color: #e2e8f0;
	}

	.state-msg {
		padding: 16px 14px;
		font-size: 12px;
		color: #94a3b8;
	}

	.state-msg.error {
		color: #f87171;
	}

	.state-msg.empty {
		line-height: 1.5;
	}

	.version-list {
		list-style: none;
		margin: 0;
		padding: 0;
		overflow-y: auto;
		flex: 1;
	}

	.version-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		padding: 8px 14px;
		border-bottom: 1px solid #1e293b;
	}

	.version-item:last-child {
		border-bottom: none;
	}

	.version-meta {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.version-label {
		font-size: 12px;
		color: #e2e8f0;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 190px;
	}

	.version-date {
		font-size: 11px;
		color: #64748b;
	}

	.restore-btn {
		background: #334155;
		border: 1px solid #475569;
		border-radius: 4px;
		color: #e2e8f0;
		cursor: pointer;
		font-size: 11px;
		padding: 4px 8px;
		white-space: nowrap;
		flex-shrink: 0;
		transition: border-color 0.15s;
	}

	.restore-btn:hover:not(:disabled) {
		border-color: #64748b;
	}

	.restore-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
</style>
