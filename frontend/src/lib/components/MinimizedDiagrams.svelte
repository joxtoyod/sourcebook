<script lang="ts">
	import { mermaidCards } from '$lib/stores/mermaid';
	import { sendMermaidDelete, sendMermaidRestore } from '$lib/ws';

	$: minimizedRegular = $mermaidCards.filter((c) => c.minimized && !c.is_proposed);
	$: minimizedProposed = $mermaidCards.filter((c) => c.minimized && c.is_proposed);

	function chipLabel(title: string): string {
		return title.length > 18 ? title.slice(0, 17) + '…' : title;
	}

	function restore(id: string) {
		mermaidCards.update((cards) =>
			cards.map((c) => (c.id === id ? { ...c, minimized: false } : c))
		);
		sendMermaidRestore(id);
	}

	function deleteDiagram(id: string) {
		mermaidCards.update((cards) => cards.filter((c) => c.id !== id));
		sendMermaidDelete(id);
	}
</script>

{#if minimizedRegular.length > 0}
	<div class="panel panel-left">
		{#each minimizedRegular as card (card.id)}
			<div class="chip-row">
				<button class="chip" title={card.title} on:click={() => restore(card.id)}>
					<span class="chip-icon">⬡</span>
					<span class="chip-label">{chipLabel(card.title)}</span>
				</button>
				<!-- svelte-ignore a11y-click-events-have-key-events -->
				<!-- svelte-ignore a11y-no-static-element-interactions -->
				<button class="chip-delete" title="Delete" on:click|stopPropagation={() => deleteDiagram(card.id)}>✕</button>
			</div>
		{/each}
	</div>
{/if}

{#if minimizedProposed.length > 0}
	<div class="panel panel-right">
		{#each minimizedProposed as card (card.id)}
			<div class="chip-row">
				<button class="chip chip-proposed" title={card.title} on:click={() => restore(card.id)}>
					<span class="chip-icon-proposed">◈</span>
					<span class="chip-label">{chipLabel(card.title)}</span>
				</button>
				<!-- svelte-ignore a11y-click-events-have-key-events -->
				<!-- svelte-ignore a11y-no-static-element-interactions -->
				<button class="chip-delete" title="Delete" on:click|stopPropagation={() => deleteDiagram(card.id)}>✕</button>
			</div>
		{/each}
	</div>
{/if}

<style>
	.panel {
		position: absolute;
		top: 50%;
		transform: translateY(-50%);
		display: flex;
		flex-direction: column;
		gap: 6px;
		z-index: 15;
		pointer-events: auto;
	}

	.panel-left {
		left: 12px;
	}

	.panel-right {
		right: 12px;
		align-items: flex-end;
	}

	.chip-row {
		display: flex;
		align-items: center;
		gap: 4px;
	}

	.chip {
		display: flex;
		align-items: center;
		gap: 6px;
		background: #1e293b;
		border: 1px solid #334155;
		border-radius: 8px;
		color: #94a3b8;
		cursor: pointer;
		font-family: inherit;
		font-size: 11px;
		font-weight: 500;
		letter-spacing: 0.04em;
		padding: 6px 10px;
		text-transform: uppercase;
		white-space: nowrap;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
		transition: border-color 0.15s, color 0.15s;
	}

	.chip:hover {
		border-color: #3b82f6;
		color: #e2e8f0;
	}

	.chip-proposed {
		border-color: #7c3aed;
		color: #c4b5fd;
		background: rgba(124, 58, 237, 0.12);
	}

	.chip-proposed:hover {
		border-color: #a855f7;
		color: #fff;
		background: rgba(124, 58, 237, 0.25);
	}

	.chip-icon {
		font-size: 13px;
		color: #3b82f6;
	}

	.chip-icon-proposed {
		font-size: 13px;
		color: #a855f7;
	}

	.chip-delete {
		background: none;
		border: 1px solid #334155;
		border-radius: 6px;
		color: #475569;
		cursor: pointer;
		font-size: 10px;
		line-height: 1;
		padding: 5px 6px;
		flex-shrink: 0;
		transition: border-color 0.15s, color 0.15s, background 0.15s;
	}

	.chip-delete:hover {
		border-color: #f87171;
		color: #f87171;
		background: #3b1a1a;
	}
</style>
