# fonts/

Drop `.ttf`/`.otf` font files here. Two ways they get used:

1. **`Monocraft.ttf`** specifically is checked automatically by
   `generate_pack.py` -- if present, it's used for every language, no flags
   needed.
2. **Everything else** needs to be pointed at explicitly with `--font`,
   pointing at the exact filename (Google Fonts downloads often aren't named
   the way you'd expect -- see below):
   ```
   python generate_pack.py --language ja_jp --version 1.21.4 --font fonts/NotoSansJP-VariableFont_wght.ttf
   ```
   Auto-detection can't guess which script you need, so it only ever falls
   back to Latin-script system fonts (Consolas/Courier New/Lucida Console on
   Windows) -- fine for Spanish, French, German, etc., but they don't have
   CJK/Kannada/Cyrillic/etc. glyphs, so text in those scripts would render as
   blank boxes without `--font`.

## Already in this repo

| File | Use it for | How |
|---|---|---|
| `Monocraft.ttf` | Any Latin-script language, for a look closer to Minecraft's own typeface | Automatic, no flag needed |
| `NotoSansJP-VariableFont_wght.ttf` | Japanese | `--font fonts/NotoSansJP-VariableFont_wght.ttf` |
| `NotoSansMono-Regular.ttf` | Latin/Cyrillic/Greek, as a fixed alternative to relying on whatever system fonts happen to be installed (e.g. on macOS/Linux, where the default candidates are Windows-only paths) | `--font fonts/NotoSansMono-Regular.ttf` |

The `-VariableFont_wght` naming on the Japanese one is just what Google
Fonts' "Download family" zip names it -- it's a variable font (one file
covering multiple weights), not a mistake. `--font` works with it exactly
like any other `.ttf`.

## Getting fonts for other scripts

No other fonts are bundled here (binary assets, each with their own
license) -- download what you need and save it in this folder.

For Latin scripts, nothing is required -- `generate_pack.py` already falls
back to a monospace system font, or use `NotoSansMono-Regular.ttf` above.

For everything else, these are all from Google's
[Noto](https://notofonts.github.io/) project (SIL Open Font License 1.1 --
free to use and redistribute), built specifically for broad, reliable
Unicode coverage. Use "Download family" on each font's Google Fonts page.

| Script | Font | Google Fonts |
|---|---|---|
| Chinese (Simplified) | Noto Sans SC | https://fonts.google.com/noto/specimen/Noto+Sans+SC |
| Chinese (Traditional) | Noto Sans TC | https://fonts.google.com/noto/specimen/Noto+Sans+TC |
| Korean | Noto Sans KR | https://fonts.google.com/noto/specimen/Noto+Sans+KR |
| Kannada | Noto Sans Kannada | https://fonts.google.com/noto/specimen/Noto+Sans+Kannada |

For a script not listed here, search "Noto Sans \<script name\>" on Google
Fonts first -- the Noto project covers nearly every script in Unicode.
Whatever the downloaded file is actually named, just point `--font` at it.

Heads up: CJK Noto fonts are large (often 10-16 MB each, since they cover
thousands of glyphs) -- fine to use locally, just something to know before
committing several of them into this repo.
