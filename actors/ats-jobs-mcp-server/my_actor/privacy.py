"""Keep personal data out of the output.

The factory only builds Actors whose useful data holds no personal data, and
this guard is the last line of defence: every item passes through clean()
before it is pushed. It drops fields whose names point at a person, and
blanks e-mail addresses and international phone numbers found in any text.
Add field names to EXTRA_FORBIDDEN_KEYS for a niche; never remove defaults.
"""

from __future__ import annotations

import re
from typing import Any

FORBIDDEN_KEYS = frozenset({
    'email', 'emails', 'email_address', 'phone', 'phones', 'phone_number', 'mobile', 'fax', 'whatsapp',
    'first_name', 'last_name', 'full_name', 'person_name', 'contact_name', 'contact_person', 'contact',
    'author', 'author_name', 'authors', 'username', 'user_name', 'user', 'handle', 'nickname',
    'reviewer', 'reviewer_name', 'poster', 'posted_by', 'owner_name', 'recruiter', 'recruiter_name',
    'profile', 'profile_url', 'avatar', 'avatar_url', 'photo', 'photo_url', 'birthday', 'date_of_birth',
    'home_address', 'personal_address', 'ip', 'ip_address',
})
# Niche-specific additions go here.
EXTRA_FORBIDDEN_KEYS: frozenset[str] = frozenset()

REDACTED = '[removed]'
_EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
# Only numbers written in international form (+country code) count as phone numbers, so dates,
# prices and IDs are left alone.
_PHONE = re.compile(r'\+\d{1,3}[\s.-]?(?:\(\d{1,4}\)[\s.-]?)?\d{2,4}(?:[\s.-]?\d{2,4}){1,4}')
_CAMEL = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')


def normalise_key(key: str) -> str:
    """'reviewerName', 'Reviewer-Name' and 'reviewer name' all become 'reviewer_name'."""
    return re.sub(r'[^a-z0-9]+', '_', _CAMEL.sub('_', key).lower()).strip('_')


def clean(item: Any, removed: set[str] | None = None) -> Any:
    """A copy of `item` without personal-data fields and with contact details blanked.

    Names of dropped fields are added to `removed`, so the caller can log them once.
    """
    forbidden = FORBIDDEN_KEYS | EXTRA_FORBIDDEN_KEYS
    if isinstance(item, dict):
        result = {}
        for key, value in item.items():
            if normalise_key(str(key)) in forbidden:
                if removed is not None:
                    removed.add(str(key))
                continue
            result[key] = clean(value, removed)
        return result
    if isinstance(item, list):
        return [clean(value, removed) for value in item]
    if isinstance(item, str):
        return _PHONE.sub(REDACTED, _EMAIL.sub(REDACTED, item))
    return item
