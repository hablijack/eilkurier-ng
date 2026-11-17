// The edition document: the contract between the editorial desk and typesetting
// (reference: layout/sample/edition.json in the repository).

export interface StoryItem {
	section?: string;
	size?: 'lead' | 'large' | 'medium' | 'small';
	headline: string;
	subhead?: string | null;
	body: string[];
	source: string;
	published?: string;
	url?: string | null;
	teaser_only?: boolean;
	excerpt?: boolean;
	background?: string[];
}

export interface EditionPayload {
	masthead: { title: string; slogan: string; region: string; since: string };
	edition: { number: number; date: string; date_label: string; reader: string; lang: string };
	style?: { theme: string };
	weather?: { place: string; summary: string; temp_min: number; temp_max: number; wind: string };
	sections: string[];
	lead?: StoryItem;
	stories?: StoryItem[];
	briefs?: { headline: string; text: string; source: string }[];
	calendar?: { when: string; what: string }[];
	family?: { from: string; text: string }[];
	almanac?: Record<string, string>;
}
