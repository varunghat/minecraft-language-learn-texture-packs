# fonts/

Drop `.ttf`/`.otf` font files here. Two ways they get used:

1. **`Monocraft.ttf`** (see below) is checked automatically by
   `generate_pack.py` -- if present, it's used for every language, no flags
   needed.
2. **Everything else** needs to be pointed at explicitly with
   `--font fonts/<filename>`, e.g.:
   ```
   python generate_pack.py --language ja_jp --version 1.21.4 --font fonts/NotoSansJP.ttf
   ```
   Auto-detection can't guess which script you need, so it only ever falls
   back to Latin-script system fonts (Consolas/Courier New/Lucida Console on
   Windows) -- fine for Spanish, French, German, etc., but they don't have
   CJK/Kannada/Cyrillic/etc. glyphs, so text in those scripts would render as
   blank boxes without `--font`.

No fonts are bundled in this repo (they're binary assets with their own
licenses) -- download the ones you need from the links below and save them
here with these names so the commands above work as written.

## Latin scripts (Spanish, French, German, ...)

Nothing required -- `generate_pack.py` already falls back to a monospace
system font. Optionally, for a look closer to Minecraft's own typeface:

- **Monocraft** -- https://github.com/IdreesInc/Monocraft (open source, MIT
  license) -- download the `.ttf` from its Releases page, save as
  `fonts/Monocraft.ttf`.

## Other scripts

All of these are from Google's [Noto](https://notofonts.github.io/) project
(SIL Open Font License 1.1 -- free to use and redistribute), built
specifically for broad, reliable Unicode coverage. On each font's Google
Fonts page, use "Download family" (gives a `.zip` with multiple weights --
pick the Bold `.ttf`, it reads better with this project's text outline) or
grab a single weight from the linked GitHub repo's `full/` folder.

| Script | Font | Google Fonts | Suggested filename |
|---|---|---|---|
| Chinese (Simplified) | Noto Sans SC | https://fonts.google.com/noto/specimen/Noto+Sans+SC | `fonts/NotoSansSC.ttf` |
| Chinese (Traditional) | Noto Sans TC | https://fonts.google.com/noto/specimen/Noto+Sans+TC | `fonts/NotoSansTC.ttf` |
| Japanese | Noto Sans JP | https://fonts.google.com/noto/specimen/Noto+Sans+JP | `fonts/NotoSansJP.ttf` |
| Korean | Noto Sans KR | https://fonts.google.com/noto/specimen/Noto+Sans+KR | `fonts/NotoSansKR.ttf` |
| Kannada | Noto Sans Kannada | https://fonts.google.com/noto/specimen/Noto+Sans+Kannada | `fonts/NotoSansKannada.ttf` |
| Other Latin/Cyrillic/Greek needing wider coverage than the system fonts | Noto Sans | https://fonts.google.com/noto/specimen/Noto+Sans | `fonts/NotoSans.ttf` |

For a script not listed here, search "Noto Sans \<script name\>" on Google
Fonts first -- the Noto project covers nearly every script in Unicode.

Heads up: CJK Noto fonts are large (often 10-16 MB each, since they cover
thousands of glyphs) -- fine to use locally, just something to know before
committing several of them into this repo.
