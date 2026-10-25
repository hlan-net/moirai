"""Shared fixtures for the unit test suite."""

import pytest

from api.llm import catalog

_real_fetch_catalog_doc = catalog._fetch_catalog_doc


@pytest.fixture
def real_fetch_catalog_doc():
    """The un-patched CouchDB fetch, for tests of the fetch itself."""
    return _real_fetch_catalog_doc


@pytest.fixture(autouse=True)
def no_catalog_document(monkeypatch):
    """Unit tests never reach CouchDB for the admin-edited model catalog."""
    monkeypatch.setattr(catalog, "_fetch_catalog_doc", lambda: None)
    catalog.invalidate_catalog_cache()
    yield
    catalog.invalidate_catalog_cache()
