<script lang="ts">
	import { tick } from 'svelte';
	import { isConnected, isStreaming, sendChat, sendEditFeature } from '$lib/ws';
	import { diagram } from '$lib/stores/diagram';
	import { editMode } from '$lib/stores/editMode';

	let input = '';
	let inputEl: HTMLInputElement;

	$: if ($editMode) {
		tick().then(() => inputEl?.focus());
	}

	function submit() {
		const trimmed = input.trim();
		if (!trimmed || !$isConnected || $isStreaming) return;
		if ($editMode) {
			sendEditFeature(trimmed, $editMode.groupId, $diagram);
			editMode.set(null);
		} else {
			sendChat(trimmed, $diagram);
		}
		input = '';
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && $editMode) {
			editMode.set(null);
			return;
		}
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			submit();
		}
	}
</script>

<div class="chat-bar">
	{#if $editMode}
		<div class="edit-chip">
			<span class="edit-chip-label">Editing: <strong>{$editMode.groupLabel}</strong></span>
			<!-- svelte-ignore a11y-no-static-element-interactions -->
			<!-- svelte-ignore a11y-click-events-have-key-events -->
			<span class="edit-chip-dismiss" on:click={() => editMode.set(null)} title="Cancel">×</span>
		</div>
	{/if}
	{#if $isStreaming}
		<div class="working-indicator">
			<span class="dot" /><span class="dot" /><span class="dot" />
			<span class="working-label">AI is working…</span>
		</div>
	{/if}
	<form class="input-row" class:edit-mode={$editMode} on:submit|preventDefault={submit}>
		<input
			bind:this={inputEl}
			type="text"
			bind:value={input}
			on:keydown={onKeydown}
			placeholder={$editMode ? `Describe changes for "${$editMode.groupLabel}"…` : 'Ask the AI architect…'}
			disabled={!$isConnected || $isStreaming}
		/>
		<button type="submit" disabled={!input.trim() || !$isConnected || $isStreaming}>
			{$editMode ? 'Edit' : 'Send'}
		</button>
	</form>
</div>

<style>
	.chat-bar {
		position: absolute;
		bottom: 50px;
		left: 50%;
		transform: translateX(-50%);
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
		z-index: 30;
		pointer-events: none;
	}

	.edit-chip {
		pointer-events: auto;
		display: flex;
		align-items: center;
		gap: 8px;
		background: rgba(168, 85, 247, 0.15);
		border: 1px solid rgba(168, 85, 247, 0.45);
		border-radius: 20px;
		padding: 5px 12px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
	}

	.edit-chip-label {
		font-size: 12px;
		color: #c084fc;
		white-space: nowrap;
	}

	.edit-chip-label strong {
		color: #e9d5ff;
		font-weight: 600;
	}

	.edit-chip-dismiss {
		color: #a855f7;
		font-size: 16px;
		line-height: 1;
		cursor: pointer;
		user-select: none;
		padding: 0 2px;
	}

	.edit-chip-dismiss:hover {
		color: #e9d5ff;
	}

	.working-indicator {
		pointer-events: none;
		display: flex;
		align-items: center;
		gap: 5px;
		background: #1e293b;
		border: 1px solid #334155;
		border-radius: 20px;
		padding: 6px 14px;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
	}

	.working-indicator .dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: #3b82f6;
		animation: bounce 1s infinite;
	}
	.working-indicator .dot:nth-child(2) { animation-delay: 0.15s; }
	.working-indicator .dot:nth-child(3) { animation-delay: 0.3s; }

	.working-label {
		font-size: 12px;
		color: #94a3b8;
		margin-left: 2px;
	}

	@keyframes bounce {
		0%, 80%, 100% { transform: translateY(0); }
		40% { transform: translateY(-4px); }
	}

	.input-row {
		pointer-events: auto;
		display: flex;
		gap: 8px;
		align-items: center;
		background: #1e293b;
		border: 1px solid #334155;
		border-radius: 28px;
		padding: 6px 6px 6px 16px;
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
		width: 480px;
		transition: border-color 0.15s;
	}

	.input-row.edit-mode {
		border-color: rgba(168, 85, 247, 0.6);
		box-shadow: 0 4px 16px rgba(168, 85, 247, 0.15);
	}

	input {
		flex: 1;
		background: none;
		border: none;
		outline: none;
		color: #e2e8f0;
		font-size: 14px;
		font-family: inherit;
		min-width: 0;
	}

	input::placeholder {
		color: #475569;
	}

	input:disabled {
		cursor: not-allowed;
		opacity: 0.5;
	}

	button {
		background: #3b82f6;
		color: white;
		border: none;
		border-radius: 22px;
		padding: 7px 18px;
		font-size: 13px;
		font-weight: 500;
		cursor: pointer;
		white-space: nowrap;
		flex-shrink: 0;
		transition: background 0.15s;
	}

	button:hover:not(:disabled) {
		background: #2563eb;
	}

	button:disabled {
		background: #334155;
		color: #475569;
		cursor: not-allowed;
	}
</style>
