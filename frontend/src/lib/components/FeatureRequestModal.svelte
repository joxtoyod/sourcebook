<script lang="ts">
	import { diagram } from '$lib/stores/diagram';
	import { isStreaming, sendFeatureRequest } from '$lib/ws';

	export let onClose: () => void;

	let featureName = '';
	let requirements = '';
	let intentions = '';

	function handleSubmit() {
		if (!featureName.trim() || $isStreaming) return;
		sendFeatureRequest(featureName.trim(), requirements, intentions, $diagram);
		onClose();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}
</script>

<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<div class="modal-backdrop" role="presentation" on:click={onClose} on:keydown={handleKeydown}>
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div class="modal-panel" on:click|stopPropagation on:keydown|stopPropagation>
		<div class="modal-header">
			<span class="modal-title">＋ Propose New Feature</span>
			<button class="modal-close" on:click={onClose} aria-label="Close">✕</button>
		</div>

		<div class="modal-body">
			<label class="field-label" for="feature-name">Feature Name <span class="required">*</span></label>
			<!-- svelte-ignore a11y-autofocus -->
			<input
				id="feature-name"
				class="field-input"
				type="text"
				placeholder="e.g. OAuth2 Authentication"
				bind:value={featureName}
				autofocus
				on:keydown={(e) => { if (e.key === 'Enter') handleSubmit(); }}
			/>

			<label class="field-label" for="feature-requirements">Requirements</label>
			<textarea
				id="feature-requirements"
				class="field-textarea"
				placeholder="What should this feature do? List the key behaviours and acceptance criteria."
				rows="4"
				bind:value={requirements}
			></textarea>

			<label class="field-label" for="feature-intentions">Intentions / Notes</label>
			<textarea
				id="feature-intentions"
				class="field-textarea"
				placeholder="Any architectural preferences, constraints, or context the AI should know."
				rows="3"
				bind:value={intentions}
			></textarea>
		</div>

		<div class="modal-footer">
			<button class="btn btn-cancel" on:click={onClose}>Cancel</button>
			<button
				class="btn btn-propose"
				disabled={!featureName.trim() || $isStreaming}
				on:click={handleSubmit}
			>
				{$isStreaming ? 'Streaming…' : 'Propose Feature'}
			</button>
		</div>
	</div>
</div>

<style>
	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		z-index: 300;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.modal-panel {
		background: #1e293b;
		border: 1px solid #334155;
		border-radius: 12px;
		width: 480px;
		max-width: 95vw;
		box-shadow: 0 16px 48px rgba(0, 0, 0, 0.6);
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	.modal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 20px 12px;
		border-bottom: 1px solid #334155;
	}

	.modal-title {
		color: #e2e8f0;
		font-size: 15px;
		font-weight: 700;
		letter-spacing: 0.01em;
	}

	.modal-close {
		background: none;
		border: none;
		color: #64748b;
		font-size: 14px;
		cursor: pointer;
		padding: 4px 6px;
		border-radius: 4px;
		line-height: 1;
	}
	.modal-close:hover {
		color: #e2e8f0;
		background: #334155;
	}

	.modal-body {
		padding: 16px 20px;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.field-label {
		color: #94a3b8;
		font-size: 11px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}

	.required {
		color: #a855f7;
	}

	.field-input,
	.field-textarea {
		background: #0f172a;
		border: 1px solid #475569;
		border-radius: 6px;
		color: #e2e8f0;
		font-size: 13px;
		font-family: inherit;
		padding: 8px 10px;
		outline: none;
		width: 100%;
		box-sizing: border-box;
		resize: vertical;
	}
	.field-input:focus,
	.field-textarea:focus {
		border-color: #a855f7;
	}

	.modal-footer {
		display: flex;
		gap: 8px;
		justify-content: flex-end;
		padding: 12px 20px 16px;
		border-top: 1px solid #334155;
	}

	.btn {
		border: none;
		border-radius: 6px;
		cursor: pointer;
		font-size: 13px;
		font-weight: 600;
		padding: 8px 18px;
	}

	.btn-cancel {
		background: #334155;
		color: #e2e8f0;
	}
	.btn-cancel:hover {
		background: #475569;
	}

	.btn-propose {
		background: #7c3aed;
		color: #fff;
	}
	.btn-propose:hover:not(:disabled) {
		background: #6d28d9;
	}
	.btn-propose:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
</style>
