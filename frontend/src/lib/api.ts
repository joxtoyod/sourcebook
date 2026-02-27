export async function getRequirements(): Promise<string | null> {
	const res = await fetch('/api/requirements');
	if (!res.ok) throw new Error(`Failed to load requirements: ${res.status}`);
	const data = (await res.json()) as { requirements_text: string | null };
	return data.requirements_text;
}

export async function saveRequirements(text: string): Promise<void> {
	const res = await fetch('/api/requirements', {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ requirements_text: text })
	});
	if (!res.ok) throw new Error(`Failed to save requirements: ${res.status}`);
}

export interface DiagramVersion {
	id: string;
	label: string;
	created_at: string;
}

export async function getVersions(): Promise<DiagramVersion[]> {
	const res = await fetch('/api/versions');
	if (!res.ok) throw new Error(`Failed to load versions: ${res.status}`);
	const data = (await res.json()) as { versions: DiagramVersion[] };
	return data.versions;
}

export async function restoreVersion(
	versionId: string
): Promise<{ nodes: unknown[]; edges: unknown[]; groups: unknown[] }> {
	const res = await fetch(`/api/versions/${versionId}/restore`, { method: 'POST' });
	if (!res.ok) throw new Error(`Failed to restore version: ${res.status}`);
	return res.json() as Promise<{ nodes: unknown[]; edges: unknown[]; groups: unknown[] }>;
}
