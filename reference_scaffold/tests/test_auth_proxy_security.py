from __future__ import annotations

from cafeteria.auth.service import trusted_client_address


def test_exact_trusted_peer_uses_leftmost_validated_forwarded_ip() -> None:
    trusted_peer = '172.31.213.10'
    forwarded = {
        'REMOTE_ADDR': trusted_peer,
        'HTTP_X_FORWARDED_FOR': '203.0.113.44, 198.51.100.9',
    }
    spoofed = {
        'REMOTE_ADDR': '198.51.100.77',
        'HTTP_X_FORWARDED_FOR': '203.0.113.99',
    }

    assert trusted_client_address(forwarded, trusted_peer, (trusted_peer,)) == '203.0.113.44'
    assert trusted_client_address(spoofed, '198.51.100.77', (trusted_peer,)) == '198.51.100.77'
