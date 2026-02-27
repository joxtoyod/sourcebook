<script lang="ts">
	import { diagram } from '$lib/stores/diagram';
	import type { DiagramNode, DiagramEdge, DiagramGroup } from '$lib/stores/diagram';
	import { mermaidCards } from '$lib/stores/mermaid';
	import { projectName, sendFilePathOverride, sendProjectName, sendAcceptFeatureWithSpec, sendAcceptNode, sendRejectFeature } from '$lib/ws';
	import { selectedNode } from '$lib/stores/diagram';
	import { editMode } from '$lib/stores/editMode';
	import MermaidCard from './MermaidCard.svelte';
	import MinimizedDiagrams from './MinimizedDiagrams.svelte';
	import FeatureRequestModal from './FeatureRequestModal.svelte';

	// Pan / zoom state
	let tx = 0, ty = 0, scale = 1;
	let isPanning = false;
	let panStart = { x: 0, y: 0 };

	// Drag node state
	let draggingId: string | null = null;
	let dragOffset = { x: 0, y: 0 };

	// Drag group state
	let draggingGroupId: string | null = null;
	let groupDragLastPos = { x: 0, y: 0 };

	// Tooltip state
	let hoveredNodeId: string | null = null;
	let tooltipPos = { x: 0, y: 0 };

	// Click vs drag disambiguation
	let pointerDownPos = { x: 0, y: 0 };
	let hasDragged = false;
	const CLICK_THRESHOLD = 5;

	// Context menu state
	let contextMenu: { node: DiagramNode; x: number; y: number } | null = null;
	let filePathInput = '';

	// Feature proposal modal state
	let showFeatureModal = false;

	// Spec confirmation dialog state
	let confirmSpecGroupId: string | null = null;
	let confirmSpecGroupLabel: string = '';

	function openSpecConfirm(groupId: string, groupLabel: string) {
		confirmSpecGroupId = groupId;
		confirmSpecGroupLabel = groupLabel;
	}

	function closeSpecConfirm() {
		confirmSpecGroupId = null;
		confirmSpecGroupLabel = '';
	}

	function proceedWithSpec() {
		if (!confirmSpecGroupId) return;
		sendAcceptFeatureWithSpec(confirmSpecGroupId);
		closeSpecConfirm();
	}

	// Project name editing state
	let editingProjectName = false;
	let projectNameInput = '';

	function startEditProjectName() {
		projectNameInput = $projectName;
		editingProjectName = true;
	}

	function commitProjectName() {
		const name = projectNameInput.trim();
		if (name && name !== $projectName) {
			projectName.set(name);
			sendProjectName(name);
		}
		editingProjectName = false;
	}

	function cancelProjectNameEdit() {
		editingProjectName = false;
	}

	const NODE_W = 160;
	const NODE_H = 60;

	const NODE_COLORS: Record<string, string> = {
		module:   '#4f9cf9',
		service:  '#a78bfa',
		database: '#34d399',
		external: '#f97316'
	};

	const PROPOSED_COLOR = '#a855f7';

	const GROUP_PADDING = 32;

	function computeGroupBox(groupId: string, nodes: DiagramNode[]): { x: number; y: number; w: number; h: number } | null {
		const members = nodes.filter((n) => n.group_id === groupId);
		if (members.length === 0) return null;
		const minX = Math.min(...members.map((n) => n.x));
		const minY = Math.min(...members.map((n) => n.y));
		const maxX = Math.max(...members.map((n) => n.x + NODE_W));
		const maxY = Math.max(...members.map((n) => n.y + NODE_H));
		return {
			x: minX - GROUP_PADDING,
			y: minY - GROUP_PADDING,
			w: maxX - minX + GROUP_PADDING * 2,
			h: maxY - minY + GROUP_PADDING * 2,
		};
	}

	function hexToRgba(hex: string, alpha: number): string {
		const h = hex.replace('#', '');
		const r = parseInt(h.substring(0, 2), 16);
		const g = parseInt(h.substring(2, 4), 16);
		const b = parseInt(h.substring(4, 6), 16);
		return `rgba(${r},${g},${b},${alpha})`;
	}

	function nodeById(id: string): DiagramNode | undefined {
		return $diagram.nodes.find((n) => n.id === id);
	}

	function edgePath(edge: DiagramEdge): string {
		const s = nodeById(edge.source || edge.source_id || '');
		const t = nodeById(edge.target || edge.target_id || '');
		if (!s || !t) return '';
		const sx = s.x + NODE_W / 2, sy = s.y + NODE_H / 2;
		const tx2 = t.x + NODE_W / 2, ty2 = t.y + NODE_H / 2;
		const cx = (sx + tx2) / 2;
		return `M ${sx} ${sy} C ${cx} ${sy}, ${cx} ${ty2}, ${tx2} ${ty2}`;
	}

	function edgeMidpoint(edge: DiagramEdge): { x: number; y: number } | null {
		const s = nodeById(edge.source || edge.source_id || '');
		const t = nodeById(edge.target || edge.target_id || '');
		if (!s || !t) return null;
		return {
			x: (s.x + t.x) / 2 + NODE_W / 2,
			y: (s.y + t.y) / 2 + NODE_H / 2 - 10
		};
	}

	// ---- Pointer events ----

	function onSvgPointerDown(e: PointerEvent) {
		const target = e.target as SVGElement;
		// Only start pan if clicking the background (not a node)
		if (target.tagName === 'svg' || target.tagName === 'g' && !target.dataset.nodeId) {
			isPanning = true;
			panStart = { x: e.clientX - tx, y: e.clientY - ty };
			(e.currentTarget as Element).setPointerCapture(e.pointerId);
		}
	}

	function onNodePointerDown(e: PointerEvent, node: DiagramNode) {
		e.stopPropagation();
		draggingId = node.id;
		hasDragged = false;
		pointerDownPos = { x: e.clientX, y: e.clientY };
		dragOffset = {
			x: (e.clientX - tx) / scale - node.x,
			y: (e.clientY - ty) / scale - node.y
		};
		(e.currentTarget as Element).setPointerCapture(e.pointerId);
	}

	function onGroupPointerDown(e: PointerEvent, groupId: string) {
		e.stopPropagation();
		draggingGroupId = groupId;
		hasDragged = false;
		pointerDownPos = { x: e.clientX, y: e.clientY };
		groupDragLastPos = {
			x: (e.clientX - tx) / scale,
			y: (e.clientY - ty) / scale
		};
		(e.currentTarget as Element).setPointerCapture(e.pointerId);
	}

	function onPointerMove(e: PointerEvent) {
		if (isPanning) {
			tx = e.clientX - panStart.x;
			ty = e.clientY - panStart.y;
		} else if (draggingId) {
			hasDragged = true;
			const nx = (e.clientX - tx) / scale - dragOffset.x;
			const ny = (e.clientY - ty) / scale - dragOffset.y;
			diagram.update((d) => ({
				...d,
				nodes: d.nodes.map((n) => (n.id === draggingId ? { ...n, x: nx, y: ny } : n))
			}));
		} else if (draggingGroupId) {
			hasDragged = true;
			const cx = (e.clientX - tx) / scale;
			const cy = (e.clientY - ty) / scale;
			const dx = cx - groupDragLastPos.x;
			const dy = cy - groupDragLastPos.y;
			groupDragLastPos = { x: cx, y: cy };
			diagram.update((d) => ({
				...d,
				nodes: d.nodes.map((n) =>
					n.group_id === draggingGroupId ? { ...n, x: n.x + dx, y: n.y + dy } : n
				)
			}));
		}
		if (hoveredNodeId) tooltipPos = { x: e.clientX, y: e.clientY };
	}

	function onPointerUp(e: PointerEvent) {
		if (hasDragged) hoveredNodeId = null;
		isPanning = false;
		draggingId = null;
		draggingGroupId = null;
	}

	function onWheel(e: WheelEvent) {
		e.preventDefault();
		const delta = e.deltaY > 0 ? 0.95 : 1.05;
		scale = Math.min(3, Math.max(0.15, scale * delta));
	}

	function onNodePointerEnter(e: PointerEvent, node: DiagramNode) {
		if (!draggingId) {
			hoveredNodeId = node.id;
			tooltipPos = { x: e.clientX, y: e.clientY };
		}
	}

	function onNodePointerLeave() {
		hoveredNodeId = null;
	}

	function onNodeClick(e: MouseEvent, node: DiagramNode) {
		const dx = Math.abs(e.clientX - pointerDownPos.x);
		const dy = Math.abs(e.clientY - pointerDownPos.y);
		if (dx <= CLICK_THRESHOLD && dy <= CLICK_THRESHOLD && node.file_path) {
			selectedNode.set(node);
		}
	}

	function onNodeContextMenu(e: MouseEvent, node: DiagramNode) {
		e.preventDefault();
		e.stopPropagation();
		contextMenu = { node, x: e.clientX, y: e.clientY };
		filePathInput = node.file_path ?? '';
	}

	function closeContextMenu() {
		contextMenu = null;
	}

	function commitFilePathEdit() {
		if (!contextMenu) return;
		const path = filePathInput.trim();
		sendFilePathOverride(contextMenu.node.id, path);
		diagram.update((d) => ({
			...d,
			nodes: d.nodes.map((n) =>
				n.id === contextMenu!.node.id ? { ...n, file_path: path || undefined } : n
			)
		}));
		closeContextMenu();
	}
</script>

<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<div
	class="canvas-wrap"
	class:panning={isPanning}
	class:dragging-group={!!draggingGroupId}
	role="img"
	aria-label="Architecture diagram canvas"
>
	{#if $projectName || editingProjectName}
		<div class="project-name-bar">
			{#if editingProjectName}
				<!-- svelte-ignore a11y-autofocus -->
				<input
					class="project-name-input"
					type="text"
					bind:value={projectNameInput}
					on:keydown={(e) => {
						if (e.key === 'Enter') commitProjectName();
						if (e.key === 'Escape') cancelProjectNameEdit();
					}}
					on:blur={commitProjectName}
					autofocus
				/>
			{:else}
				<!-- svelte-ignore a11y-no-static-element-interactions -->
				<span class="project-name-label" on:click={startEditProjectName} title="Click to rename">{$projectName}</span>
			{/if}
		</div>
	{/if}

	<!-- Toolbar: New Feature button (above SVG, top-right) -->
	<div class="toolbar">
		<button class="btn-new-feature" on:click={() => (showFeatureModal = true)}>
			＋ New Feature
		</button>
	</div>

	<svg
		width="100%"
		height="100%"
		on:pointerdown={onSvgPointerDown}
		on:pointermove={onPointerMove}
		on:pointerup={onPointerUp}
		on:wheel={onWheel}
	>
		<defs>
			<marker id="arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
				<polygon points="0 0, 10 3.5, 0 7" fill="#64748b" />
			</marker>
			<marker id="arrow-proposed" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
				<polygon points="0 0, 10 3.5, 0 7" fill={PROPOSED_COLOR} />
			</marker>
		</defs>

		<g transform={`translate(${tx}, ${ty}) scale(${scale})`}>
			<!-- Group containers (bottom layer) -->
			{#each $diagram.groups as group (group.id)}
				{@const box = computeGroupBox(group.id, $diagram.nodes)}
				{@const isProposedGroup = group.id.startsWith('proposed-')}
				{#if box}
					<g class="group-container">
						<rect
							x={box.x}
							y={box.y}
							width={box.w}
							height={box.h}
							rx="16"
							fill={hexToRgba(group.color, isProposedGroup ? 0.18 : 0.12)}
							stroke={hexToRgba(group.color, isProposedGroup ? 0.75 : 0.40)}
							stroke-width={isProposedGroup ? 2.5 : 1.5}
							stroke-dasharray={isProposedGroup ? '8 4' : undefined}
							style="pointer-events: all; cursor: {draggingGroupId === group.id ? 'grabbing' : 'grab'};"
							on:pointerdown={(e) => onGroupPointerDown(e, group.id)}
						/>
						<text
							x={box.x + 14}
							y={box.y + 20}
							fill={hexToRgba(group.color, 0.85)}
							font-size="12"
							font-weight="700"
							letter-spacing="0.06em"
							font-family="inherit"
						>{group.label}</text>
						{#if isProposedGroup}
							<!-- "Edit" button -->
							<!-- svelte-ignore a11y-no-static-element-interactions -->
							<g
								class="accept-all-btn"
								transform={`translate(${box.x + box.w - 246}, ${box.y + 6})`}
								on:click|stopPropagation={() => editMode.set({ groupId: group.id, groupLabel: group.label })}
								style="cursor: pointer; pointer-events: all;"
							>
								<rect width="76" height="22" rx="6" fill="#0f172a" stroke="#a855f7" stroke-width="1.5" />
								<text
									x="38"
									y="15"
									text-anchor="middle"
									fill="#a855f7"
									font-size="10"
									font-weight="700"
									font-family="inherit"
									letter-spacing="0.04em"
								>✎ Edit</text>
							</g>
							<!-- "Accept All" button -->
							<!-- svelte-ignore a11y-no-static-element-interactions -->
							<g
								class="accept-all-btn"
								transform={`translate(${box.x + box.w - 164}, ${box.y + 6})`}
								on:click|stopPropagation={() => openSpecConfirm(group.id, group.label)}
								style="cursor: pointer; pointer-events: all;"
							>
								<rect width="78" height="22" rx="6" fill="#7c3aed" />
								<text
									x="39"
									y="15"
									text-anchor="middle"
									fill="white"
									font-size="10"
									font-weight="700"
									font-family="inherit"
									letter-spacing="0.04em"
								>✓ Accept All</text>
							</g>
							<!-- "Reject" button -->
							<!-- svelte-ignore a11y-no-static-element-interactions -->
							<g
								class="reject-btn"
								transform={`translate(${box.x + box.w - 80}, ${box.y + 6})`}
								on:click|stopPropagation={() => sendRejectFeature(group.id)}
								style="cursor: pointer; pointer-events: all;"
							>
								<rect width="74" height="22" rx="6" fill="#dc2626" />
								<text
									x="37"
									y="15"
									text-anchor="middle"
									fill="white"
									font-size="10"
									font-weight="700"
									font-family="inherit"
									letter-spacing="0.04em"
								>✗ Reject</text>
							</g>
						{/if}
					</g>
				{/if}
			{/each}

			<!-- Edges -->
			{#each $diagram.edges as edge (edge.id)}
				{@const mid = edgeMidpoint(edge)}
				<path
					d={edgePath(edge)}
					fill="none"
					stroke={edge.is_proposed ? PROPOSED_COLOR : '#64748b'}
					stroke-width="1.5"
					stroke-dasharray={edge.is_proposed ? '6 3' : undefined}
					opacity={edge.is_proposed ? 0.75 : 1}
					marker-end={edge.is_proposed ? 'url(#arrow-proposed)' : 'url(#arrow)'}
				/>
				{#if edge.label && mid}
					<text
						x={mid.x}
						y={mid.y}
						text-anchor="middle"
						fill="#94a3b8"
						font-size="11"
						font-family="inherit"
					>{edge.label}</text>
				{/if}
			{/each}

			<!-- Nodes -->
			{#each $diagram.nodes as node (node.id)}
				<!-- svelte-ignore a11y-no-static-element-interactions -->
				<g
					transform={`translate(${node.x}, ${node.y})`}
					style="cursor: {node.file_path ? 'pointer' : 'grab'}"
					on:pointerdown={(e) => onNodePointerDown(e, node)}
					on:pointerenter={(e) => onNodePointerEnter(e, node)}
					on:pointerleave={onNodePointerLeave}
					on:click={(e) => onNodeClick(e, node)}
					on:contextmenu={(e) => onNodeContextMenu(e, node)}
				>
					<rect
						width={NODE_W}
						height={NODE_H}
						rx="8"
						fill={NODE_COLORS[node.type] ?? '#4f9cf9'}
						opacity="0.9"
					/>
					{#if node.is_overridden}
						<rect
							width={NODE_W}
							height={NODE_H}
							rx="8"
							fill="none"
							stroke="#fbbf24"
							stroke-width="2"
							stroke-dasharray="4 2"
						/>
					{/if}
					{#if node.is_proposed}
						<rect
							width={NODE_W}
							height={NODE_H}
							rx="8"
							fill="none"
							stroke={PROPOSED_COLOR}
							stroke-width="2.5"
							stroke-dasharray="6 3"
						/>
						<!-- "PROPOSED" badge — top-right corner -->
						<rect x={NODE_W - 58} y="-8" width="56" height="14" rx="4" fill={PROPOSED_COLOR} />
						<text
							x={NODE_W - 30}
							y="2"
							text-anchor="middle"
							fill="white"
							font-size="8"
							font-weight="700"
							font-family="inherit"
							letter-spacing="0.06em"
						>PROPOSED</text>
					{/if}
					<text
						x={NODE_W / 2}
						y="26"
						text-anchor="middle"
						fill="white"
						font-size="13"
						font-weight="600"
						font-family="inherit"
					>{node.label}</text>
					<text
						x={NODE_W / 2}
						y="44"
						text-anchor="middle"
						fill="rgba(255,255,255,0.7)"
						font-size="10"
						font-family="inherit"
					>{node.type}</text>
				</g>
			{/each}
		</g>
	</svg>

	<!-- Hover tooltip -->
	{#if hoveredNodeId}
		{@const hn = $diagram.nodes.find((n) => n.id === hoveredNodeId)}
		{#if hn?.file_path}
			<div class="node-tooltip" style="left:{tooltipPos.x + 14}px;top:{tooltipPos.y - 8}px;">
				<span class="tooltip-path">{hn.file_path}</span>
				<span class="tooltip-hint">Click to view code</span>
			</div>
		{/if}
	{/if}

	<!-- Context menu -->
	{#if contextMenu}
		<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
		<div class="ctx-overlay" on:click={closeContextMenu} role="presentation"></div>
		<div class="ctx-menu" style="left:{contextMenu.x}px;top:{contextMenu.y}px;">
			<div class="ctx-title">Set file path</div>
			<div class="ctx-node-label">{contextMenu.node.label}</div>
			<!-- svelte-ignore a11y-autofocus -->
			<input
				class="ctx-input"
				type="text"
				placeholder="backend/sourcebook/ai_agent.py"
				bind:value={filePathInput}
				on:keydown={(e) => {
					if (e.key === 'Enter') commitFilePathEdit();
					if (e.key === 'Escape') closeContextMenu();
				}}
				autofocus
			/>
			<div class="ctx-actions">
				<button class="ctx-btn ctx-btn-primary" on:click={commitFilePathEdit}>Save</button>
				<button class="ctx-btn" on:click={closeContextMenu}>Cancel</button>
			</div>
			{#if contextMenu.node.is_proposed}
				<div class="ctx-divider"></div>
				<button
					class="ctx-btn ctx-btn-accept"
					on:click={() => {
						if (contextMenu) sendAcceptNode(contextMenu.node.id);
						closeContextMenu();
					}}
				>✓ Accept node</button>
			{/if}
		</div>
	{/if}

	<!-- Feature request modal -->
	{#if showFeatureModal}
		<FeatureRequestModal onClose={() => (showFeatureModal = false)} />
	{/if}

	<!-- Spec confirmation dialog -->
	{#if confirmSpecGroupId}
		<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
		<div
			class="modal-backdrop"
			role="presentation"
			on:click={closeSpecConfirm}
			on:keydown={(e) => { if (e.key === 'Escape') closeSpecConfirm(); }}
		>
			<!-- svelte-ignore a11y-no-static-element-interactions -->
			<div class="confirm-panel" on:click|stopPropagation on:keydown|stopPropagation>
				<div class="confirm-header">
					<span class="confirm-title">Accept Feature</span>
				</div>
				<div class="confirm-body">
					<p class="confirm-message">
						By confirming, a spec of the <strong>{confirmSpecGroupLabel}</strong> feature will be created.
					</p>
					<p class="confirm-sub">
						The spec will be saved to
						<code>specs/{confirmSpecGroupLabel.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}/spec.md</code>
						and will contain detailed implementation instructions.
					</p>
				</div>
				<div class="confirm-footer">
					<button class="confirm-btn confirm-btn-cancel" on:click={closeSpecConfirm}>Cancel</button>
					<button class="confirm-btn confirm-btn-proceed" on:click={proceedWithSpec}>
						Proceed creating specs
					</button>
				</div>
			</div>
		</div>
	{/if}

	<MinimizedDiagrams />

	<!-- World-space layer: same transform as the SVG <g>, renders HTML cards at canvas coordinates -->
	<div
		class="world-layer"
		style="transform: translate({tx}px, {ty}px) scale({scale}); transform-origin: 0 0;"
	>
		{#each $mermaidCards as card (card.id)}
			{#if !card.minimized}
				<MermaidCard {card} {scale} />
			{/if}
		{/each}
	</div>

	{#if $diagram.nodes.length === 0}
		<div class="empty">
			<p>Select or create a project to begin.</p>
		</div>
	{/if}

	<div class="hint-bar">
		Scroll to zoom · Drag canvas to pan · Drag nodes to reposition · Drag group background to move group
	</div>
</div>

<style>
	.canvas-wrap {
		flex: 1;
		position: relative;
		background: #0f172a;
		background-image: radial-gradient(circle, #1e293b 1px, transparent 1px);
		background-size: 24px 24px;
		overflow: hidden;
		cursor: default;
	}
	.canvas-wrap.panning {
		cursor: grabbing;
	}
	.canvas-wrap.dragging-group {
		cursor: grabbing;
	}

	svg {
		width: 100%;
		height: 100%;
		display: block;
	}

	.group-container {
		pointer-events: none;
	}
	.accept-all-btn {
		pointer-events: all;
	}

	.world-layer {
		position: absolute;
		top: 0;
		left: 0;
		width: 0;
		height: 0;
		overflow: visible;
		pointer-events: none;
	}

	.empty {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		text-align: center;
		color: #475569;
		pointer-events: none;
	}
	.empty p {
		margin: 4px 0;
		font-size: 14px;
	}

	.hint-bar {
		position: absolute;
		bottom: 12px;
		left: 50%;
		transform: translateX(-50%);
		background: rgba(30, 41, 59, 0.8);
		color: #475569;
		font-size: 11px;
		padding: 4px 12px;
		border-radius: 20px;
		pointer-events: none;
		white-space: nowrap;
	}

	.node-tooltip {
		position: fixed;
		background: #0f172a;
		border: 1px solid #334155;
		border-radius: 6px;
		padding: 6px 10px;
		pointer-events: none;
		z-index: 100;
		display: flex;
		flex-direction: column;
		gap: 2px;
		max-width: 320px;
	}
	.tooltip-path {
		color: #e2e8f0;
		font-size: 11px;
		font-family: monospace;
		word-break: break-all;
	}
	.tooltip-hint {
		color: #475569;
		font-size: 10px;
	}

	.ctx-overlay {
		position: fixed;
		inset: 0;
		z-index: 200;
	}
	.ctx-menu {
		position: fixed;
		z-index: 201;
		background: #1e293b;
		border: 1px solid #334155;
		border-radius: 8px;
		padding: 12px;
		min-width: 260px;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.ctx-title {
		color: #94a3b8;
		font-size: 10px;
		font-weight: 600;
		text-transform: uppercase;
	}
	.ctx-node-label {
		color: #e2e8f0;
		font-size: 13px;
		font-weight: 600;
	}
	.ctx-input {
		background: #0f172a;
		border: 1px solid #475569;
		border-radius: 4px;
		color: #e2e8f0;
		font-size: 12px;
		font-family: monospace;
		padding: 6px 8px;
		outline: none;
		width: 100%;
		box-sizing: border-box;
	}
	.ctx-input:focus {
		border-color: #4f9cf9;
	}
	.ctx-actions {
		display: flex;
		gap: 6px;
		justify-content: flex-end;
	}
	.ctx-btn {
		background: #334155;
		border: none;
		border-radius: 4px;
		color: #e2e8f0;
		cursor: pointer;
		font-size: 12px;
		padding: 5px 12px;
	}
	.ctx-btn:hover {
		background: #475569;
	}
	.ctx-btn-primary {
		background: #4f9cf9;
		color: #fff;
	}
	.ctx-btn-primary:hover {
		background: #3b82f6;
	}
	.ctx-btn-accept {
		background: #7c3aed;
		color: #fff;
		width: 100%;
		text-align: left;
	}
	.ctx-btn-accept:hover {
		background: #6d28d9;
	}
	.ctx-divider {
		height: 1px;
		background: #334155;
		margin: 2px 0;
	}

	.toolbar {
		position: absolute;
		top: 14px;
		right: 14px;
		z-index: 50;
		display: flex;
		gap: 8px;
		pointer-events: all;
	}

	.btn-new-feature {
		background: #7c3aed;
		border: none;
		border-radius: 8px;
		color: #fff;
		cursor: pointer;
		font-size: 13px;
		font-weight: 700;
		padding: 7px 14px;
		letter-spacing: 0.02em;
		box-shadow: 0 2px 8px rgba(124, 58, 237, 0.4);
		transition: background 0.15s;
	}
	.btn-new-feature:hover {
		background: #6d28d9;
	}

	.project-name-bar {
		position: absolute;
		top: 16px;
		left: 50%;
		transform: translateX(-50%);
		z-index: 50;
		display: flex;
		align-items: center;
		pointer-events: all;
	}

	.project-name-label {
		color: #e2e8f0;
		font-size: 15px;
		font-weight: 600;
		letter-spacing: 0.02em;
		background: rgba(30, 41, 59, 0.75);
		border: 1px solid #334155;
		border-radius: 20px;
		padding: 4px 16px;
		cursor: pointer;
		white-space: nowrap;
		user-select: none;
		transition: background 0.15s, border-color 0.15s;
	}

	.project-name-label:hover {
		background: rgba(51, 65, 85, 0.9);
		border-color: #4f9cf9;
	}

	.project-name-input {
		background: #0f172a;
		border: 1px solid #4f9cf9;
		border-radius: 20px;
		color: #e2e8f0;
		font-size: 15px;
		font-weight: 600;
		letter-spacing: 0.02em;
		padding: 4px 16px;
		outline: none;
		min-width: 160px;
		text-align: center;
	}

	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.65);
		z-index: 400;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.confirm-panel {
		background: #1e293b;
		border: 1px solid #334155;
		border-radius: 12px;
		width: 440px;
		max-width: 95vw;
		box-shadow: 0 16px 48px rgba(0, 0, 0, 0.6);
		display: flex;
		flex-direction: column;
	}
	.confirm-header {
		padding: 16px 20px 12px;
		border-bottom: 1px solid #334155;
	}
	.confirm-title {
		color: #e2e8f0;
		font-size: 15px;
		font-weight: 700;
	}
	.confirm-body {
		padding: 18px 20px 14px;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.confirm-message {
		color: #e2e8f0;
		font-size: 14px;
		line-height: 1.55;
		margin: 0;
	}
	.confirm-message strong {
		color: #c084fc;
	}
	.confirm-message code,
	.confirm-sub code {
		background: #0f172a;
		border: 1px solid #334155;
		border-radius: 4px;
		color: #a78bfa;
		font-size: 12px;
		padding: 1px 5px;
	}
	.confirm-sub {
		color: #94a3b8;
		font-size: 12px;
		line-height: 1.5;
		margin: 0;
	}
	.confirm-footer {
		display: flex;
		gap: 8px;
		justify-content: flex-end;
		padding: 12px 20px 16px;
		border-top: 1px solid #334155;
	}
	.confirm-btn {
		border: none;
		border-radius: 6px;
		cursor: pointer;
		font-size: 13px;
		font-weight: 600;
		padding: 8px 16px;
		transition: background 0.15s;
	}
	.confirm-btn-cancel {
		background: #334155;
		color: #e2e8f0;
	}
	.confirm-btn-cancel:hover {
		background: #475569;
	}
	.confirm-btn-proceed {
		background: #7c3aed;
		color: #fff;
	}
	.confirm-btn-proceed:hover {
		background: #6d28d9;
	}
</style>
