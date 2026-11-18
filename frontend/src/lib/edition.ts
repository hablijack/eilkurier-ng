// The edition document: the contract between the editorial desk and typesetting
// (reference: layout/sample/edition.json in the repository).

export interface Picture {
	/** Stored picture, served at /api/v1/images/{id} (the sample edition uses `file` instead). */
	id?: number;
	file?: string;
	width: number;
	height: number;
	alt: string;
	credit?: string | null;
}

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
	/** Only on the lead and large stories. */
	image?: Picture;
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
