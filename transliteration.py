"""Per-language transliteration/romanization for generate_pack.py's
--transliterate flag: pinyin for Chinese, romaji for Japanese, Revised
Romanization for Korean.

Each language's function imports its own library lazily, inside the
function body, not at module load time. That's what makes the dependency
truly optional (see pyproject.toml's [project.optional-dependencies]) --
importing this module, or generating a German pack, never touches pypinyin/
pykakasi/korean-romanizer at all. The import only happens, and can only
fail, when a block actually needs transliterating.
"""


class MissingTransliterationDependency(Exception):
    def __init__(self, extra: str, package: str):
        super().__init__(
            f"Transliteration for this language needs '{package}', which isn't installed.\n"
            f"Run: pip install -e \".[{extra}]\""
        )


def to_pinyin(text: str) -> str:
    """Chinese (zh_cn, zh_tw) -> pinyin with tone marks, e.g. 石 -> shí."""
    try:
        from pypinyin import Style, pinyin
    except ImportError as e:
        raise MissingTransliterationDependency("zh", "pypinyin") from e
    syllables = pinyin(text, style=Style.TONE)
    return " ".join(syllable[0] for syllable in syllables)


_kakasi = None  # lazily-created, reused across calls -- construction has real setup cost


def to_romaji(text: str) -> str:
    """Japanese (ja_jp) -> Hepburn romaji, e.g. 石 -> ishi."""
    global _kakasi
    try:
        import pykakasi
    except ImportError as e:
        raise MissingTransliterationDependency("ja", "pykakasi") from e
    if _kakasi is None:
        _kakasi = pykakasi.kakasi()
    return " ".join(chunk["hepburn"] for chunk in _kakasi.convert(text))


def to_korean_romanization(text: str) -> str:
    """Korean (ko_kr) -> Revised Romanization, e.g. 돌 -> dol."""
    try:
        from korean_romanizer.romanizer import Romanizer
    except ImportError as e:
        raise MissingTransliterationDependency("ko", "korean-romanizer") from e
    return Romanizer(text).romanize()


TRANSLITERATORS = {
    "zh_cn": to_pinyin,
    "zh_tw": to_pinyin,
    "ja_jp": to_romaji,
    "ko_kr": to_korean_romanization,
}


def get_transliterator(language: str):
    """Returns a `str -> str` function for `language`, or None if this
    project doesn't have one -- --transliterate is a no-op (word only) for
    any language not in TRANSLITERATORS, not an error."""
    return TRANSLITERATORS.get(language)
