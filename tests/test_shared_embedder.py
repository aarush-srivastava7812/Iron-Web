from concurrent.futures import ThreadPoolExecutor


def test_compatible_engines_share_one_model_and_configuration_is_respected(monkeypatch):
    import memory.embeddings.embedder as module
    calls = []

    class FakeEmbedder:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(module, 'Embedder', FakeEmbedder)
    monkeypatch.setattr(module, '_instances', {})
    with ThreadPoolExecutor(max_workers=8) as executor:
        models = list(executor.map(lambda _: module.get_embedder(use_gpu=False), range(20)))
    assert all(model is models[0] for model in models) and len(calls) == 1
    assert module.get_embedder(use_gpu=False, model_name='another-model') is not models[0]
    assert len(calls) == 2
