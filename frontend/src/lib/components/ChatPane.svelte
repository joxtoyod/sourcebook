<script lang="ts">
	import { afterUpdate, tick } from 'svelte';
	import { messages, isConnected, isStreaming, sendChat, sendEditFeature } from '$lib/ws';
	import { diagram } from '$lib/stores/diagram';
	import { editMode } from '$lib/stores/editMode';

	let input = '';
	let messagesEl: HTMLElement;
	let textareaEl: HTMLTextAreaElement;

	afterUpdate(() => {
		messagesEl?.scrollTo({ top: messagesEl.scrollHeight, behavior: 'smooth' });
	});

	$: if ($editMode) {
		tick().then(() => textareaEl?.focus());
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

	function dismissEditMode() {
		editMode.set(null);
	}
</script>

<aside class="chat-pane">
	<header>
		<h2>AI Architect</h2>
		<span class="status" class:connected={$isConnected}>
			{$isConnected ? 'Connected' : 'Disconnected'}
		</span>
	</header>

	<div class="messages" bind:this={messagesEl}>
		{#if $messages.length === 0}
			<div class="welcome">
				<p>Describe your system and I'll generate an architecture diagram.</p>
				<p class="hint">
					Try: "I'm building a REST API with a PostgreSQL database and a React frontend"
				</p>
			</div>
		{:else}
			{#each $messages as msg (msg.timestamp + msg.role)}
				<div class="msg {msg.role}">
					<div class="bubble">{msg.content}</div>
				</div>
			{/each}
			{#if $isStreaming}
				<div class="typing">
					<span /><span /><span />
				</div>
			{/if}
		{/if}
	</div>

	{#if $editMode}
		<div class="edit-chip">
			<span class="edit-chip-label">Editing: <strong>{$editMode.groupLabel}</strong></span>
			<!-- svelte-ignore a11y-no-static-element-interactions -->
			<!-- svelte-ignore a11y-click-events-have-key-events -->
			<span class="edit-chip-dismiss" on:click={dismissEditMode} title="Cancel edit">×</span>
		</div>
	{/if}

	<form class="input-row" on:submit|preventDefault={submit}>
		<textarea
			bind:this={textareaEl}
			bind:value={input}
			on:keydown={onKeydown}
			placeholder={$editMode ? `Describe changes for "${$editMode.groupLabel}"…` : 'Describe your architecture…'}
			rows="3"
			disabled={!$isConnected || $isStreaming}
		/>
		<button type="submit" disabled={!input.trim() || !$isConnected || $isStreaming}>
			{$editMode ? 'Edit' : 'Send'}
		</button>
	</form>
</aside>

<style>
	.chat-pane {
		width: 380px;
		min-width: 300px;
		display: flex;
		flex-direction: column;
		background: #1e293b;
		border-left: 1px solid #334155;
	}

	header {
		padding: 14px 18px;
		border-bottom: 1px solid #334155;
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-shrink: 0;
	}
	header h2 {
		margin: 0;
		font-size: 15px;
		font-weight: 600;
		color: #e2e8f0;
	}
	.status {
		font-size: 12px;
		color: #ef4444;
	}
	.status.connected {
		color: #22c55e;
	}

	.messages {
		flex: 1;
		overflow-y: auto;
		padding: 14px;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.welcome {
		color: #64748b;
		font-size: 14px;
		text-align: center;
		padding: 20px 0;
	}
	.welcome .hint {
		font-size: 12px;
		color: #475569;
		margin-top: 6px;
		font-style: italic;
	}

	.msg {
		display: flex;
	}
	.msg.user {
		justify-content: flex-end;
	}

	.bubble {
		max-width: 88%;
		padding: 9px 13px;
		border-radius: 12px;
		font-size: 14px;
		line-height: 1.5;
		white-space: pre-wrap;
		word-break: break-word;
	}
	.msg.user .bubble {
		background: #3b82f6;
		color: white;
		border-bottom-right-radius: 3px;
	}
	.msg.assistant .bubble {
		background: #334155;
		color: #e2e8f0;
		border-bottom-left-radius: 3px;
	}

	.typing {
		display: flex;
		gap: 4px;
		padding: 6px 2px;
	}
	.typing span {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: #475569;
		animation: bounce 1s infinite;
	}
	.typing span:nth-child(2) { animation-delay: 0.15s; }
	.typing span:nth-child(3) { animation-delay: 0.3s; }

	@keyframes bounce {
		0%, 80%, 100% { transform: translateY(0); }
		40% { transform: translateY(-6px); }
	}

	.edit-chip {
		margin: 0 14px 8px;
		padding: 6px 10px;
		background: rgba(168, 85, 247, 0.15);
		border: 1px solid rgba(168, 85, 247, 0.4);
		border-radius: 8px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-shrink: 0;
	}
	.edit-chip-label {
		font-size: 12px;
		color: #c084fc;
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
		padding: 0 2px;
		user-select: none;
	}
	.edit-chip-dismiss:hover {
		color: #e9d5ff;
	}

	.input-row {
		padding: 10px 14px;
		border-top: 1px solid #334155;
		display: flex;
		gap: 8px;
		align-items: flex-end;
		flex-shrink: 0;
	}

	textarea {
		flex: 1;
		background: #0f172a;
		border: 1px solid #334155;
		border-radius: 8px;
		color: #e2e8f0;
		padding: 9px 11px;
		font-size: 14px;
		font-family: inherit;
		resize: none;
		outline: none;
	}
	textarea:focus {
		border-color: #3b82f6;
	}
	textarea::placeholder {
		color: #475569;
	}

	button {
		background: #3b82f6;
		color: white;
		border: none;
		border-radius: 8px;
		padding: 9px 15px;
		font-size: 14px;
		cursor: pointer;
		white-space: nowrap;
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
