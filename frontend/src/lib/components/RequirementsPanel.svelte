<script lang="ts">
	import { onMount } from 'svelte';
	import { getRequirements, saveRequirements } from '$lib/api';
	import { diagram } from '$lib/stores/diagram';
	import { sendChat } from '$lib/ws';

	let vision = '';
	let keyRequirements = '';
	let techPrefs = '';
	let apiError = '';
	let submitting = false;

	$: canSubmit = vision.trim().length > 0 && !submitting;

	onMount(async () => {
		try {
			const text = await getRequirements();
			if (text) {
				const visionMatch = text.match(/^Vision:\s*(.+?)(?:\n|$)/m);
				const reqMatch = text.match(/Key Requirements:\n([\s\S]+?)(?:\n\nTechnical Preferences:|$)/);
				const prefMatch = text.match(/Technical Preferences:\s*(.+?)$/m);
				if (visionMatch) vision = visionMatch[1].trim();
				if (reqMatch) keyRequirements = reqMatch[1].trim();
				if (prefMatch) techPrefs = prefMatch[1].trim();
			}
		} catch {
			// silently ignore pre-fill errors
		}
	});

	async function handleSubmit() {
		if (!canSubmit) return;

		submitting = true;
		apiError = '';

		const parts: string[] = [`Vision: ${vision.trim()}`];
		if (keyRequirements.trim()) {
			parts.push(`Key Requirements:\n${keyRequirements.trim()}`);
		}
		if (techPrefs.trim()) {
			parts.push(`Technical Preferences: ${techPrefs.trim()}`);
		}
		const formattedText = parts.join('\n\n');

		try {
			await saveRequirements(formattedText);
			sendChat(
				`Generate an architecture diagram for this project:\n\n${formattedText}`,
				$diagram
			);
		} catch (e) {
			apiError = String(e);
			submitting = false;
		}
	}
</script>

<div class="panel" role="dialog" aria-label="Define your project">
	<div class="panel-header">
		<h2>Define Your Project</h2>
		<p class="subtitle">Describe your project so the AI can generate an initial architecture.</p>
	</div>

	{#if submitting}
		<div class="generating">
			<div class="spinner" />
			<p class="generating-text">Generating architecture…</p>
			<p class="generating-sub">The AI is designing your system. This may take a moment.</p>
		</div>
	{:else}
		<div class="fields">
			<label class="field">
				<span class="label-text">Vision <span class="required">*</span></span>
				<input
					type="text"
					bind:value={vision}
					placeholder="e.g. A real-time chat app for remote teams"
					class="input"
				/>
			</label>

			<label class="field">
				<span class="label-text">Key Requirements <span class="optional">(optional)</span></span>
				<textarea
					bind:value={keyRequirements}
					rows={4}
					placeholder="e.g.&#10;- User authentication&#10;- Message history&#10;- File attachments"
					class="input textarea"
				></textarea>
			</label>

			<label class="field">
				<span class="label-text">Technical Preferences <span class="optional">(optional)</span></span>
				<input
					type="text"
					bind:value={techPrefs}
					placeholder="e.g. React frontend, Node.js API, PostgreSQL"
					class="input"
				/>
			</label>
		</div>

		{#if apiError}
			<p class="error">{apiError}</p>
		{/if}

		<button class="submit-btn" disabled={!canSubmit} on:click={handleSubmit}>
			Generate Architecture →
		</button>
	{/if}
</div>

<style>
	.panel {
		background: #1e293b;
		border: 1px solid #334155;
		border-radius: 12px;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
		max-width: 520px;
		padding: 28px 32px 24px;
		pointer-events: auto;
		width: 100%;
	}

	.panel-header {
		margin-bottom: 20px;
	}

	h2 {
		color: #e2e8f0;
		font-size: 18px;
		font-weight: 600;
		margin: 0 0 6px;
	}

	.subtitle {
		color: #64748b;
		font-size: 13px;
		margin: 0;
	}

	.fields {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 5px;
	}

	.label-text {
		color: #94a3b8;
		font-size: 12px;
		font-weight: 500;
		letter-spacing: 0.02em;
		text-transform: uppercase;
	}

	.required {
		color: #f87171;
	}

	.optional {
		color: #475569;
		font-weight: 400;
		text-transform: none;
		letter-spacing: 0;
	}

	.input {
		background: #0f172a;
		border: 1px solid #334155;
		border-radius: 6px;
		color: #e2e8f0;
		font-family: inherit;
		font-size: 13px;
		outline: none;
		padding: 8px 12px;
		transition: border-color 0.15s;
		width: 100%;
		box-sizing: border-box;
	}

	.input:focus {
		border-color: #3b82f6;
	}

	.input::placeholder {
		color: #475569;
	}

	.textarea {
		resize: vertical;
		line-height: 1.5;
	}

	.error {
		color: #f87171;
		font-size: 12px;
		margin: 10px 0 0;
	}

	.submit-btn {
		background: #3b82f6;
		border: none;
		border-radius: 7px;
		color: #fff;
		cursor: pointer;
		font-family: inherit;
		font-size: 14px;
		font-weight: 500;
		margin-top: 20px;
		padding: 10px 20px;
		transition: background 0.15s, opacity 0.15s;
		width: 100%;
	}

	.submit-btn:hover:not(:disabled) {
		background: #2563eb;
	}

	.submit-btn:disabled {
		cursor: not-allowed;
		opacity: 0.45;
	}

	.generating {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 14px;
		padding: 32px 0 16px;
	}

	.spinner {
		width: 36px;
		height: 36px;
		border: 3px solid #334155;
		border-top-color: #3b82f6;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.generating-text {
		color: #e2e8f0;
		font-size: 15px;
		font-weight: 500;
		margin: 0;
	}

	.generating-sub {
		color: #64748b;
		font-size: 12px;
		margin: 0;
		text-align: center;
	}
</style>
