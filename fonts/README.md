# fonts/

Drop `.ttf`/`.otf` font files here. Three ways they get used, in priority order:

1. **`--font <path>` on the command line** always wins if given.
2. **`../data/font_map.json`** maps a language code to a font file here --
   `generate_pack.py` picks it up automatically, no flag needed, whenever
   `--font` isn't passed.
3. **`Monocraft.ttf`** specifically, if present, is the default for any
   language with no `font_map.json` entry (i.e. Latin scripts).

Within all of that, `load_font` also checks *actual glyph coverage* (via
`fontTools`, not just "does the file exist") and skips a candidate that's
missing a character the current text needs, falling through to the next
one. This matters even for "Latin" languages: Monocraft has base Greek/
Cyrillic letters but not, for example, precomposed accented Greek vowels
(ά, έ, ή, ...) that appear in nearly every real Greek word -- without this
check, Monocraft being present would silently break Greek even though a
later candidate (Consolas) has full coverage, since it's earlier in
`FONT_CANDIDATES` and "the file exists" used to be the only test.

So for a language already in `font_map.json`, this just works:
```
python generate_pack.py --language ja_jp --version 1.21.4
```

## Already mapped (automatic, no `--font` needed)

| Language | File |
|---|---|
| `ja_jp` (Japanese) | `NotoSansJP-VariableFont_wght.ttf` |
| `zh_cn` (Chinese, Simplified) | `NotoSansSC-VariableFont_wght.ttf` |
| `ko_kr` (Korean) | `NotoSansKR-VariableFont_wght.ttf` |

Also present but not in the map (Latin/Cyrillic/Greek only, so it's not
tied to a specific language -- pass `--font fonts/NotoSansMono-Regular.ttf`
if you want it over the default system-font fallback):
`NotoSansMono-Regular.ttf`.

## Adding a new language

Two steps, and `font_map.json` is deliberately a flat, one-line-per-language
file so this stays easy:

1. Download an open-source font covering the script (see the table below
   for known sources) and save it here.
2. Add one line to `../data/font_map.json`'s `"fonts"` object:
   ```json
   "kn_in": "NotoSansKannada-VariableFont_wdth,wght.ttf"
   ```
   That's it -- `generate_pack.py --language kn_in ...` now picks it up with
   no flag, same as the languages above.

Don't add Latin-script languages (`de_de`, `fr_fr`, `es_es`, ...) to the
map -- they already work via the default system-font fallback, and adding
them there would just override that with no benefit.

**Note:** `zh_tw` (Chinese, Traditional) is deliberately *not* in the map
yet, even though Chinese is otherwise covered -- Simplified and Traditional
share many codepoints but differ in the correct glyph *shape* for some of
them (Han unification), and `NotoSansSC` renders the Simplified-region
shapes. Using it for Traditional text would render subtly wrong strokes for
someone actually learning Traditional Chinese, not just "unsupported" the
way a missing glyph would be. Download Noto Sans TC (table below) and add
its own `zh_tw` entry rather than reusing the Simplified one.

## Where to get fonts for other scripts

No fonts are bundled in this repo besides what's listed above (binary
assets, each with their own license) -- download what you need.

For Latin scripts, nothing is required -- `generate_pack.py` already falls
back to a monospace system font, or use `NotoSansMono-Regular.ttf`.

For everything else, these are all from Google's
[Noto](https://notofonts.github.io/) project (SIL Open Font License 1.1 --
free to use and redistribute), built specifically for broad, reliable
Unicode coverage. Use "Download family" on each font's Google Fonts page.

| Script | Font | Google Fonts |
|---|---|---|
| Chinese (Traditional) | Noto Sans TC | https://fonts.google.com/noto/specimen/Noto+Sans+TC |
| Kannada | Noto Sans Kannada | https://fonts.google.com/noto/specimen/Noto+Sans+Kannada |

For a script not listed here, search "Noto Sans \<script name\>" on Google
Fonts first -- the Noto project covers nearly every script in Unicode.
Whatever the downloaded file is actually named (Google Fonts' "Download
family" zip often names variable fonts oddly, e.g. the
`-VariableFont_wght` suffix on the Japanese/Chinese/Korean ones above --
that's normal, not a mistake), that's the filename to put in `font_map.json`.

Heads up: CJK Noto fonts are large (often 10-16 MB each, since they cover
thousands of glyphs) -- fine to use locally, just something to know before
committing several of them into this repo.

## Complex scripts (Arabic, Devanagari, Hebrew, ...)

Having the right font here only gets the *glyphs* on the page -- correct
rendering (Arabic letter-joining, Devanagari ligatures, right-to-left
ordering) needs more than `font_map.json`; see the "Complex-script text
shaping" entry in [`docs/ideas.md`](../docs/ideas.md). Not done yet, and
adding a font for one of these scripts without that fix would produce
broken-looking, not just unsupported, output.
