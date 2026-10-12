"""Document dictionaries backed by the canonical benchmark adapters."""

from memory.evaluation.harness.locomo_adapter import LoCoMoAdapter
from memory.evaluation.harness.longmemeval_adapter import LongMemEvalAdapter


def _convert(documents, examples):
    return (
        [
            dict(
                id=d.doc_id,
                text=d.text,
                metadata=dict(d.metadata, timestamp=d.timestamp),
            )
            for d in documents
        ],
        [
            dict(
                query_id=e.example_id,
                text=e.query,
                ground_truth_ids=e.ground_truth_ids,
                answer=e.gold_answer,
                metadata=e.metadata,
            )
            for e in examples
        ],
    )


def load_official_locomo():
    adapter = LoCoMoAdapter()
    return _convert(adapter.load_documents(), adapter.load_examples())


def load_official_longmemeval(question_limit=50):
    if question_limit < 1:
        raise ValueError("Question limit must be positive.")
    adapter = LongMemEvalAdapter()
    all_documents, all_examples = adapter.load_documents(), adapter.load_examples()
    examples = all_examples[:question_limit]
    ids = {mid for example in examples for mid in example.metadata["corpus_ids"]}
    documents = [d for d in all_documents if d.doc_id in ids]
    corpus, queries = _convert(documents, examples)
    return corpus, queries, len(all_examples)
