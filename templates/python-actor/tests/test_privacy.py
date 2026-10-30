from my_actor.privacy import REDACTED, clean, normalise_key


def test_drops_personal_fields_at_any_depth():
    removed = set()
    item = {
        'title': 'Senior Engineer',
        'company': 'Acme',
        'reviewerName': 'Jane Doe',
        'contact': {'email': 'jane@acme.com', 'office': 'Berlin'},
        'reviews': [{'rating': 5, 'author': 'Bob', 'text': 'Great'}],
    }
    assert clean(item, removed) == {
        'title': 'Senior Engineer',
        'company': 'Acme',
        'reviews': [{'rating': 5, 'text': 'Great'}],
    }
    assert removed == {'reviewerName', 'contact', 'author'}


def test_blanks_contact_details_in_text_but_not_dates_or_prices():
    text = 'Write to jobs@acme.com or call +49 30 1234 5678. Posted 2026-10-24, salary 85,000-95,000 EUR, id 123456789.'
    cleaned = clean(text)
    assert 'jobs@acme.com' not in cleaned and '+49 30 1234 5678' not in cleaned
    assert cleaned.count(REDACTED) == 2
    assert '2026-10-24' in cleaned and '85,000-95,000' in cleaned and '123456789' in cleaned


def test_keys_are_normalised():
    assert normalise_key('reviewerName') == 'reviewer_name'
    assert normalise_key('Profile-URL') == 'profile_url'
    assert normalise_key('first name') == 'first_name'


def test_non_text_values_pass_through():
    assert clean({'price': 9.99, 'inStock': True, 'tags': None}) == {'price': 9.99, 'inStock': True, 'tags': None}


def test_user_supplied_fields_pass_unchanged_and_nothing_else_does(monkeypatch):
    # A tool returning text from the user's own PDF keeps it as supplied (QUESTIONS Q24).
    monkeypatch.setattr('my_actor.privacy.USER_SUPPLIED_KEYS', frozenset({'page_text'}))
    item = {'pageText': 'Invoice for Jane Doe, jane@example.com', 'source_url': 'mailto:jane@example.com', 'email': 'x@y.z'}
    assert clean(item) == {'pageText': 'Invoice for Jane Doe, jane@example.com', 'source_url': f'mailto:{REDACTED}'}
