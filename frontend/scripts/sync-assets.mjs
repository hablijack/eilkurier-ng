// Copies brand assets and fonts from the repository's single source (assets/) into static/.
import { cpSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const target = join(root, 'frontend', 'static');
mkdirSync(join(target, 'fonts'), { recursive: true });
for (const font of ['Chomsky.otf', 'BebasNeue-Regular.ttf']) {
	cpSync(join(root, 'assets', 'fonts', font), join(target, 'fonts', font));
}
cpSync(join(root, 'assets', 'fonts', 'PlayfairDisplay[wght].ttf'), join(target, 'fonts', 'PlayfairDisplay.ttf'));
cpSync(join(root, 'assets', 'brand', 'rider.svg'), join(target, 'rider.svg'));
