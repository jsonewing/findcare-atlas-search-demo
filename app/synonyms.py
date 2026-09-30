from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


MEDICAL_SYNONYMS: list[dict[str, Any]] = [
    {
        "mappingType": "equivalent",
        "synonyms": ["primary care physician", "family doctor", "general practitioner", "pcp"],
    },
    {
        "mappingType": "equivalent",
        "synonyms": ["ear nose throat doctor", "ent", "otolaryngologist", "otolaryngology"],
    },
    {
        "mappingType": "equivalent",
        "synonyms": ["orthopedic doctor", "orthopedist", "orthopedic surgeon", "bone doctor"],
    },
    {
        "mappingType": "equivalent",
        "synonyms": ["heart doctor", "cardiologist", "cardiology"],
    },
    {
        "mappingType": "equivalent",
        "synonyms": ["skin doctor", "dermatologist", "dermatology"],
    },
    {
        "mappingType": "equivalent",
        "synonyms": ["stomach doctor", "gi doctor", "gastroenterologist", "gastroenterology"],
    },
    {
        "mappingType": "equivalent",
        "synonyms": ["lung doctor", "pulmonologist", "pulmonology"],
    },
    {
        "mappingType": "equivalent",
        "synonyms": ["physical therapy", "physiotherapy", "physical rehabilitation"],
    },
    {
        "mappingType": "equivalent",
        "synonyms": ["walk in clinic", "same day clinic", "urgent care"],
    },
    {
        "mappingType": "equivalent",
        "synonyms": ["magnetic resonance imaging", "mri"],
    },
    {
        "mappingType": "equivalent",
        "synonyms": ["anterior cruciate ligament", "acl"],
    },
    {
        "mappingType": "equivalent",
        "synonyms": ["ob gyn", "obgyn", "obstetrics and gynecology"],
    },
]


def synonym_documents() -> list[dict[str, Any]]:
    return deepcopy(MEDICAL_SYNONYMS)


def is_known_synonym_phrase(query: str) -> bool:
    normalized = " ".join(re.findall(r"[a-z0-9]+", query.lower()))
    return any(
        normalized == " ".join(re.findall(r"[a-z0-9]+", synonym.lower()))
        for mapping in MEDICAL_SYNONYMS
        for synonym in mapping["synonyms"]
    )
