"""Offline test suite: network access is hard-blocked for every test."""

from __future__ import annotations

import socket

import pytest

from locale_invoice_check.corpus import generate_corpus


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    """Raise on any socket creation so accidental network use fails loudly."""

    def _blocked(*args, **kwargs):
        raise OSError("network access is blocked in offline tests")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked, raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)


@pytest.fixture(scope="session")
def corpus(tmp_path_factory):
    """Small deterministic corpus (4 invoices x 3 locales) built once."""
    root = tmp_path_factory.mktemp("fixtures")
    generate_corpus(root, count=4, seed=7)
    return root
