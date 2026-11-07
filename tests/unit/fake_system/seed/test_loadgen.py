import random

from fake_system.checkout.app.main import CheckoutRequest
from fake_system.seed.loadgen import next_request


def _sample(n=500, seed=0):
    rng = random.Random(seed)
    return [next_request(rng) for _ in range(n)]


def test_same_seed_gives_same_traffic():
    assert _sample(seed=1) == _sample(seed=1)
    assert _sample(seed=1) != _sample(seed=2)


def test_bodies_are_valid_checkout_requests():
    for method, path, body in _sample():
        if path == "/checkout":
            assert method == "POST"
            CheckoutRequest.model_validate(body)


def test_mix_contains_all_three_kinds():
    reqs = _sample()
    assert any(p == "/health" for _, p, _ in reqs)
    assert any(b and b["sku"] == "sku-cherry" for _, _, b in reqs)
    assert sum(1 for _, p, b in reqs if b and b["sku"] != "sku-cherry") > 350
