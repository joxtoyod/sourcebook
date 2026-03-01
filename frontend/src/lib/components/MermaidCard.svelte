<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { mermaidCards } from '$lib/stores/mermaid';
	import type { MermaidCard } from '$lib/stores/mermaid';
	import { selectedNode } from '$lib/stores/diagram';
	import { sendMermaidDelete, sendMermaidMinimize, sendMermaidMove, sendMermaidRename, sendMermaidResize } from '$lib/ws';

	export let card: MermaidCard;
	export let scale: number;

	const MIN_WIDTH = 240;
	const MIN_HEIGHT = 160;
	const DEFAULT_WIDTH = 500;
	const DEFAULT_HEIGHT = 460;

	let svgOutput = '';
	let renderError = '';
	let renderId = 0;

	// Title editing state
	let isEditingTitle = false;
	let editTitleValue = '';
	let titleInput: HTMLInputElement;

	// Drag state
	let isDragging = false;
	let draggingId = '';
	let dragStartPointer = { x: 0, y: 0 };
	let dragStartCard = { x: 0, y: 0 };
	let lastDx = 0;
	let lastDy = 0;

	// Resize state
	let isResizing = false;
	let resizeStartPointer = { x: 0, y: 0 };
	let resizeStartSize = { w: DEFAULT_WIDTH, h: DEFAULT_HEIGHT };
	let lastRw = DEFAULT_WIDTH;
	let lastRh = DEFAULT_HEIGHT;

	$: cardWidth = card.width ?? DEFAULT_WIDTH;
	$: cardHeight = card.height ?? DEFAULT_HEIGHT;

	onMount(() => renderDiagram(card.syntax));

	onDestroy(() => {
		window.removeEventListener('pointermove', onWindowMove);
		window.removeEventListener('pointerup', onWindowUp);
		window.removeEventListener('pointermove', onResizeMove);
		window.removeEventListener('pointerup', onResizeUp);
	});

	async function renderDiagram(src: string) {
		renderError = '';
		svgOutput = '';
		try {
			const mermaid = (await import('mermaid')).default;
			mermaid.initialize({
				startOnLoad: false,
				securityLevel: 'loose',
				theme: 'dark',
				themeVariables: {
					background: '#0f172a',
					primaryColor: '#1e293b',
					lineColor: '#64748b',
					textColor: '#e2e8f0'
				}
			});
			renderId += 1;
			const { svg } = await mermaid.render(`mermaid-card-${card.id}-${renderId}`, src);
			// Strip href/xlink:href from <a> elements so the browser status bar doesn't
			// show raw vscode:// URIs on hover. Values are preserved in data-href for
			// the click handler to read.
			svgOutput = svg.replace(/<a\b([^>]*)>/g, (_match, attrs) => {
				const newAttrs = attrs
					.replace(/\s+xlink:href="([^"]*)"/g, ' data-href="$1"')
					.replace(/\s+href="([^"]*)"/g, ' data-href="$1"');
				return `<a${newAttrs}>`;
			});
		} catch (e) {
			renderError = e instanceof Error ? e.message : 'Failed to render diagram';
		}
	}

	function onHeaderPointerDown(e: PointerEvent) {
		if (e.button !== 0) return;
		e.stopPropagation();
		e.preventDefault();
		isDragging = true;
		draggingId = card.id;
		dragStartPointer = { x: e.clientX, y: e.clientY };
		dragStartCard = { x: card.x, y: card.y };
		lastDx = 0;
		lastDy = 0;
		window.addEventListener('pointermove', onWindowMove);
		window.addEventListener('pointerup', onWindowUp);
	}

	function onWindowMove(e: PointerEvent) {
		if (!isDragging) return;
		lastDx = (e.clientX - dragStartPointer.x) / scale;
		lastDy = (e.clientY - dragStartPointer.y) / scale;
		mermaidCards.update((cards) =>
			cards.map((c) =>
				c.id === draggingId
					? { ...c, x: dragStartCard.x + lastDx, y: dragStartCard.y + lastDy }
					: c
			)
		);
	}

	function onWindowUp() {
		if (isDragging) {
			sendMermaidMove(draggingId, dragStartCard.x + lastDx, dragStartCard.y + lastDy);
		}
		isDragging = false;
		window.removeEventListener('pointermove', onWindowMove);
		window.removeEventListener('pointerup', onWindowUp);
	}

	function onResizePointerDown(e: PointerEvent) {
		if (e.button !== 0) return;
		e.stopPropagation();
		e.preventDefault();
		isResizing = true;
		resizeStartPointer = { x: e.clientX, y: e.clientY };
		resizeStartSize = { w: cardWidth, h: cardHeight };
		lastRw = cardWidth;
		lastRh = cardHeight;
		window.addEventListener('pointermove', onResizeMove);
		window.addEventListener('pointerup', onResizeUp);
	}

	function onResizeMove(e: PointerEvent) {
		if (!isResizing) return;
		const dw = (e.clientX - resizeStartPointer.x) / scale;
		const dh = (e.clientY - resizeStartPointer.y) / scale;
		lastRw = Math.max(MIN_WIDTH, resizeStartSize.w + dw);
		lastRh = Math.max(MIN_HEIGHT, resizeStartSize.h + dh);
		mermaidCards.update((cards) =>
			cards.map((c) =>
				c.id === card.id ? { ...c, width: lastRw, height: lastRh } : c
			)
		);
	}

	function onResizeUp() {
		if (isResizing) {
			sendMermaidResize(card.id, lastRw, lastRh);
		}
		isResizing = false;
		window.removeEventListener('pointermove', onResizeMove);
		window.removeEventListener('pointerup', onResizeUp);
	}

	function minimize() {
		mermaidCards.update((cards) =>
			cards.map((c) => (c.id === card.id ? { ...c, minimized: true } : c))
		);
		sendMermaidMinimize(card.id);
	}

	function deleteDiagram() {
		mermaidCards.update((cards) => cards.filter((c) => c.id !== card.id));
		sendMermaidDelete(card.id);
	}

	function startEditTitle(e: MouseEvent) {
		e.stopPropagation();
		editTitleValue = card.title;
		isEditingTitle = true;
		// Focus input on next tick after render
		setTimeout(() => titleInput?.focus(), 0);
	}

	function commitTitle() {
		const newTitle = editTitleValue.trim() || card.title;
		isEditingTitle = false;
		if (newTitle === card.title) return;
		mermaidCards.update((cards) =>
			cards.map((c) => (c.id === card.id ? { ...c, title: newTitle } : c))
		);
		sendMermaidRename(card.id, newTitle);
	}

	function onTitleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') commitTitle();
		if (e.key === 'Escape') isEditingTitle = false;
	}

	function onSvgClick(e: MouseEvent) {
		const anchor = (e.target as Element).closest('a');
		if (!anchor) return;
		// Read from data-href (set during SVG post-processing); fall back to href
		// in case a browser or Mermaid version re-adds the attribute.
		const href = anchor.dataset.href ?? anchor.getAttribute('href') ?? anchor.getAttribute('xlink:href') ?? '';
		if (!href || href.startsWith('http://') || href.startsWith('https://')) return;
		e.preventDefault();

		// Convert vscode://file/<path> URIs to plain filesystem paths the backend can serve.
		let filePath = href;
		if (filePath.startsWith('vscode://file/')) {
			filePath = decodeURIComponent(filePath.slice('vscode://file'.length));
			// Windows paths arrive as /C:/...; strip the leading slash.
			if (/^\/[A-Za-z]:/.test(filePath)) filePath = filePath.slice(1);
		}

		selectedNode.set({
			id: '__mermaid_link__',
			label: href,
			type: 'module',
			x: 0,
			y: 0,
			file_path: filePath,
		});
	}
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
	class="card"
	style="left: {card.x}px; top: {card.y}px; width: {cardWidth}px; height: {cardHeight}px;"
	class:is-dragging={isDragging}
	class:is-resizing={isResizing}
	class:is-proposed={card.is_proposed}
>
	{#if card.is_proposed}
		<div class="proposed-banner">◈ PROPOSED FEATURE</div>
	{/if}
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div class="card-header" on:pointerdown={onHeaderPointerDown}>
		<span class="drag-hint">⠿</span>
		{#if isEditingTitle}
			<!-- svelte-ignore a11y-no-static-element-interactions -->
			<input
				class="title-input"
				bind:this={titleInput}
				bind:value={editTitleValue}
				on:blur={commitTitle}
				on:keydown={onTitleKeydown}
				on:pointerdown|stopPropagation
			/>
		{:else}
			<!-- svelte-ignore a11y-click-events-have-key-events -->
			<span class="card-title" title="Double-click to rename" on:dblclick={startEditTitle}>{card.title}</span>
		{/if}
		<button class="minimize-btn" title="Minimize" on:click|stopPropagation={minimize}>—</button>
		<button class="delete-btn" title="Delete" on:click|stopPropagation={deleteDiagram}>✕</button>
	</div>
	<div class="card-body">
		{#if renderError}
			<p class="error">Could not render diagram: {renderError}</p>
		{:else if svgOutput}
			<!-- svelte-ignore a11y-click-events-have-key-events -->
			<!-- svelte-ignore a11y-no-static-element-interactions -->
			<div class="svg-wrap" on:click={onSvgClick}>{@html svgOutput}</div>
		{:else}
			<p class="loading">Rendering…</p>
		{/if}
	</div>
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div class="resize-handle" on:pointerdown={onResizePointerDown} title="Resize"></div>
</div>

<style>
	.card {
		position: absolute;
		background: #1e293b;
		border: 1px solid #334155;
		border-radius: 10px;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
		overflow: hidden;
		user-select: none;
		pointer-events: auto;
		display: flex;
		flex-direction: column;
	}

	.card.is-proposed {
		border-color: #a855f7;
		border-width: 1.5px;
		box-shadow: 0 8px 32px rgba(168, 85, 247, 0.2);
	}

	.proposed-banner {
		background: #7c3aed;
		color: #fff;
		font-size: 9px;
		font-weight: 700;
		letter-spacing: 0.1em;
		text-align: center;
		padding: 3px 0;
		flex-shrink: 0;
	}

	.card-header {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 10px;
		background: #0f172a;
		border-bottom: 1px solid #334155;
		cursor: grab;
		flex-shrink: 0;
	}

	.is-dragging .card-header {
		cursor: grabbing;
	}

	.drag-hint {
		color: #334155;
		font-size: 14px;
		line-height: 1;
		flex-shrink: 0;
	}

	.card-title {
		color: #64748b;
		font-size: 11px;
		font-weight: 500;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		flex: 1;
		cursor: text;
	}

	.title-input {
		flex: 1;
		background: #1e293b;
		border: 1px solid #475569;
		border-radius: 3px;
		color: #e2e8f0;
		font-size: 11px;
		font-weight: 500;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		padding: 1px 4px;
		outline: none;
		min-width: 0;
	}

	.title-input:focus {
		border-color: #64748b;
	}

	.minimize-btn {
		background: none;
		border: none;
		color: #475569;
		cursor: pointer;
		font-size: 14px;
		line-height: 1;
		padding: 2px 6px;
		border-radius: 3px;
		flex-shrink: 0;
	}

	.minimize-btn:hover {
		color: #e2e8f0;
		background: #334155;
	}

	.delete-btn {
		background: none;
		border: none;
		color: #475569;
		cursor: pointer;
		font-size: 12px;
		line-height: 1;
		padding: 2px 6px;
		border-radius: 3px;
		flex-shrink: 0;
	}

	.delete-btn:hover {
		color: #f87171;
		background: #3b1a1a;
	}

	.card-body {
		flex: 1;
		overflow: auto;
		padding: 16px;
		min-height: 0;
	}

	.svg-wrap :global(svg) {
		max-width: 100%;
		height: auto;
		display: block;
	}

	.loading,
	.error {
		color: #64748b;
		font-size: 12px;
		margin: 0;
	}

	.error {
		color: #f87171;
	}

	.resize-handle {
		position: absolute;
		bottom: 0;
		right: 0;
		width: 18px;
		height: 18px;
		cursor: nwse-resize;
		background: linear-gradient(
			135deg,
			transparent 40%,
			#334155 40%,
			#334155 55%,
			transparent 55%,
			transparent 65%,
			#334155 65%,
			#334155 80%,
			transparent 80%
		);
		border-radius: 0 0 10px 0;
		flex-shrink: 0;
	}

	.is-resizing {
		cursor: nwse-resize;
	}

	.is-resizing .card-body {
		pointer-events: none;
	}
</style>
