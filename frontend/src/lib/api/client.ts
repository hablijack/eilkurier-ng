import createClient from 'openapi-fetch';
import type { components, paths } from './schema';

export type Reader = components['schemas']['ReaderOut'];
export type ReaderIn = components['schemas']['ReaderIn'];
export type Interest = components['schemas']['InterestIO'];
export type Source = components['schemas']['SourceOut'];
export type SourceIn = components['schemas']['SourceIn'];
export type CatalogEntry = components['schemas']['CatalogEntry'];
export type EditionSummary = components['schemas']['EditionSummary'];
export type Edition = components['schemas']['EditionOut'];
export type Letter = components['schemas']['LetterOut'];
export type SystemStatus = components['schemas']['StatusOut'];

/** Typed client generated from the backend's OpenAPI document (`npm run api`). */
export const api = createClient<paths>({ baseUrl: '', credentials: 'same-origin' });

/** Unwrap an openapi-fetch result or throw a readable error. */
export async function unwrap<T>(
	promise: Promise<{ data?: T; error?: unknown; response: Response }>
): Promise<T> {
	const { data, error, response } = await promise;
	if (response.status === 401) {
		window.dispatchEvent(new CustomEvent('eilkurier:unauthorized'));
	}
	if (error !== undefined || !response.ok) {
		const detail = (error as { detail?: unknown })?.detail;
		throw new Error(typeof detail === 'string' ? detail : `HTTP ${response.status}`);
	}
	return data as T;
}
