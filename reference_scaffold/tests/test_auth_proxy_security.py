from __future__ import annotations

from cafeteria.auth.service import trusted_client_address


def test_exact_trusted_peer_uses_rightmost_untrusted_forwarded_ip() -> None:
    """Test rightmost-untrusted rule: walk from right, skip trusted peers, return first untrusted."""
    trusted_peer = '10.213.0.10'
    
    # Case 1: Multiple IPs in chain; rightmost untrusted IP wins
    forwarded = {
        'REMOTE_ADDR': trusted_peer,
        'HTTP_X_FORWARDED_FOR': '203.0.113.44, 198.51.100.9',
    }
    # Socket peer is trusted (10.213.0.10), chain is [203.0.113.44, 198.51.100.9]
    # Walk right to left: 198.51.100.9 (not trusted) -> return it
    assert trusted_client_address(forwarded, trusted_peer, (trusted_peer,)) == '198.51.100.9'
    
    # Case 2: Non-trusted socket peer ignores XFF
    spoofed = {
        'REMOTE_ADDR': '198.51.100.77',
        'HTTP_X_FORWARDED_FOR': '203.0.113.99',
    }
    # Socket peer is not trusted, return socket peer directly
    assert trusted_client_address(spoofed, '198.51.100.77', (trusted_peer,)) == '198.51.100.77'


def test_chain_attacker_real_from_trusted_peer() -> None:
    """Chain 'attacker, real' from trusted peer -> 'real' wins (rightmost untrusted)."""
    trusted_peer = '10.213.0.10'
    attacker = '203.0.113.1'  # Would be leftmost
    real_client = '203.0.113.99'  # Rightmost untrusted
    
    environ = {
        'REMOTE_ADDR': trusted_peer,
        'HTTP_X_FORWARDED_FOR': f'{attacker}, {real_client}',
    }
    # Walk right to left: real_client (not trusted) -> return it
    assert trusted_client_address(environ, trusted_peer, (trusted_peer,)) == real_client


def test_chain_with_trusted_peers_only() -> None:
    """Chain consisting only of trusted peers -> socket peer wins."""
    trusted_peer_1 = '10.213.0.10'
    trusted_peer_2 = '10.213.0.1'
    
    environ = {
        'REMOTE_ADDR': trusted_peer_1,
        'HTTP_X_FORWARDED_FOR': f'{trusted_peer_2}, {trusted_peer_1}',
    }
    # All entries in chain are trusted, return socket peer
    assert trusted_client_address(
        environ, trusted_peer_1, (trusted_peer_1, trusted_peer_2)
    ) == trusted_peer_1


def test_single_entry_chain_unchanged() -> None:
    """Single-entry chain with untrusted IP is returned unchanged."""
    trusted_peer = '10.213.0.10'
    single_client = '203.0.113.77'
    
    environ = {
        'REMOTE_ADDR': trusted_peer,
        'HTTP_X_FORWARDED_FOR': single_client,
    }
    # Only one entry (not trusted), return it
    assert trusted_client_address(environ, trusted_peer, (trusted_peer,)) == single_client


def test_single_entry_chain_trusted() -> None:
    """Single-entry chain with trusted IP -> socket peer (chain all trusted)."""
    trusted_peer = '10.213.0.10'
    other_trusted = '10.213.0.1'
    
    environ = {
        'REMOTE_ADDR': trusted_peer,
        'HTTP_X_FORWARDED_FOR': other_trusted,
    }
    # Single entry is trusted, return socket peer
    assert trusted_client_address(
        environ, trusted_peer, (trusted_peer, other_trusted)
    ) == trusted_peer


def test_invalid_entry_fallback_to_socket_peer() -> None:
    """Invalid entry in chain -> fall back to socket peer (current behavior)."""
    trusted_peer = '10.213.0.10'
    
    environ = {
        'REMOTE_ADDR': trusted_peer,
        'HTTP_X_FORWARDED_FOR': 'not-an-ip, 203.0.113.44',
    }
    # Invalid entry found, return socket peer
    assert trusted_client_address(environ, trusted_peer, (trusted_peer,)) == trusted_peer
