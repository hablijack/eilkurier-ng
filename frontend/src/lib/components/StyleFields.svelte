<script lang="ts">
	import type { ReaderIn } from '$lib/api/client';
	import { t, type MessageKey } from '$lib/i18n.svelte';
	import { themes } from '$lib/reader';

	let { form = $bindable(), details = true }: { form: ReaderIn; details?: boolean } = $props();
</script>

<fieldset>
	<legend>{t('profile.theme')}</legend>
	<div class="grid three">
		{#each themes as theme (theme)}
			<label class="theme theme-{theme}">
				<input type="radio" name="theme" value={theme} bind:group={form.theme} />
				<span class="sample" aria-hidden="true">
					<span class="sample-mast">Eilkurier</span>
					<span class="sample-line"></span>
					<span class="sample-head">{t('style.sampleHeadline')}</span>
					<span class="sample-text"></span>
					<span class="sample-text short"></span>
				</span>
				<span class="theme-name">{t(`theme.${theme}` as MessageKey)}</span>
				<span class="small muted">{t(`theme.${theme}.hint` as MessageKey)}</span>
			</label>
		{/each}
	</div>
	<p class="small preview">
		<a href="/api/v1/samples/edition.pdf?theme={form.theme}" target="_blank" rel="noopener">{t('profile.preview')}</a>
	</p>
</fieldset>

<fieldset>
	<legend>{t('profile.fontScale')}</legend>
	<div class="choices">
		{#each [1, 1.2, 1.4] as scale, i (scale)}
			<label><input type="radio" name="font" value={scale} bind:group={form.font_scale} />{t(`style.font.${i}` as MessageKey)}</label>
		{/each}
	</div>
</fieldset>

{#if details}
	<div class="grid three">
		<div class="field">
			<label for="story-count">{t('profile.storyCount')}</label>
			<input id="story-count" type="number" min="3" max="15" bind:value={form.story_count} />
		</div>
		<div class="field">
			<label for="paper">{t('profile.paper')}</label>
			<select id="paper" bind:value={form.paper}>
				<option value="a4">A4</option>
				<option value="a5">A5</option>
				<option value="a3">A3</option>
			</select>
		</div>
		<div class="field">
			<label for="language">{t('profile.language')}</label>
			<select id="language" bind:value={form.language}>
				<option value="de">Deutsch</option>
				<option value="en">English</option>
			</select>
		</div>
	</div>
	<label class="check"><input type="checkbox" bind:checked={form.paper_tint} />{t('profile.paperTint')}</label>
{/if}

<style>
	.preview {
		margin-top: 0.6rem;
	}
	.theme {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		padding: 0.75rem;
		border: 2px solid var(--line);
		border-radius: var(--radius);
		background: var(--surface);
		cursor: pointer;
		position: relative;
	}
	.theme:has(input:checked) {
		border-color: var(--brand);
		background: var(--brand-tint);
	}
	.theme:has(input:focus-visible) {
		outline: 3px solid var(--focus);
		outline-offset: 2px;
	}
	.theme input {
		position: absolute;
		opacity: 0;
		inset: 0;
		cursor: pointer;
	}
	.theme-name {
		font-weight: 700;
	}
	/* miniature front page; colours are fixed "paper" colours in both themes */
	.sample {
		display: flex;
		flex-direction: column;
		gap: 5px;
		padding: 10px;
		height: 7.5rem;
		border-radius: 6px;
		background: #f9f7f1;
		color: #2f2f2f;
		border: 1px solid #d9d3c4;
		overflow: hidden;
	}
	.sample-mast {
		font-family: 'Chomsky', serif;
		font-size: 1.4rem;
		text-align: center;
		line-height: 1;
	}
	.sample-line {
		border-top: 3px double #2f2f2f;
	}
	.sample-head {
		font-family: var(--font-label);
		font-size: 1rem;
		line-height: 1;
	}
	.sample-text {
		height: 6px;
		background: repeating-linear-gradient(90deg, #8a857a 0 70%, transparent 70% 100%);
		background-size: 24px 6px;
		border-radius: 2px;
		opacity: 0.6;
	}
	.sample-text.short {
		width: 60%;
	}
	.theme-feuilleton .sample-mast {
		font-family: var(--font-display);
		font-style: italic;
		font-weight: 700;
	}
	.theme-feuilleton .sample-head {
		font-family: var(--font-display);
		font-weight: 700;
		font-size: 0.9rem;
	}
	.theme-grossdruck .sample-head {
		font-size: 1.35rem;
	}
	.theme-grossdruck .sample-text {
		height: 9px;
	}
</style>
