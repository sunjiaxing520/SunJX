from typing import Literal, TypeAlias


TempoValue: TypeAlias = Literal["slow", "medium", "fast"]
VocalGenderValue: TypeAlias = Literal["male", "female", "unspecified"]

_TEMPO_ALIASES = {
    "slow": "slow",
    "slow-medium": "medium",
    "medium-slow": "medium",
    "mid": "medium",
    "mid-tempo": "medium",
    "moderate": "medium",
    "medium": "medium",
    "medium-fast": "fast",
    "fast-medium": "fast",
    "upbeat": "fast",
    "fast": "fast",
    "慢": "slow",
    "慢速": "slow",
    "中速": "medium",
    "适中": "medium",
    "中快": "fast",
    "快速": "fast",
    "快": "fast",
}

_VOCAL_GENDER_ALIASES = {
    "male": "male",
    "man": "male",
    "男": "male",
    "男声": "male",
    "female": "female",
    "woman": "female",
    "女": "female",
    "女声": "female",
    "unspecified": "unspecified",
    "any": "unspecified",
    "mixed": "unspecified",
    "不限": "unspecified",
    "不指定": "unspecified",
}


def normalize_tempo(value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip().lower().replace("_", " ").replace(" ", "-")
    return _TEMPO_ALIASES.get(normalized, normalized)


def normalize_vocal_gender(value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip().lower().replace("_", "-")
    return _VOCAL_GENDER_ALIASES.get(normalized, normalized)
