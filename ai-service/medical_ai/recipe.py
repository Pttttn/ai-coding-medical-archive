"""Processing recipe: every version and setting that can change a stage result, with a canonical hash.

The hash is recomputed by the backend (same canonical JSON as source IR), so the recipe holds only
strings, integers, booleans, null and nested objects: floats would serialize differently in Python/JS.
"""
from .chunking import SPLITTER_VERSION
from .extraction import PROMPT_VERSION, SCHEMA_VERSION
from .laboratory import LAB_PROJECTION_VERSION, LAB_VERSION
from .source_ir import IR_VERSION, NORMALIZER_VERSION, canonical_hash
from .visit import VISIT_PROMPT_VERSION, VISIT_VERSION
from .visit_review import REVIEW_PROMPT_VERSION, REVIEW_VERSION

RECIPE_VERSION = 'processing-recipe-v1'


def _hashed(body: dict) -> dict:
    def check(value):
        if isinstance(value, float):
            raise ValueError('Recipe values must not be floats')
        if isinstance(value, dict):
            for item in value.values():
                check(item)
        if isinstance(value, list):
            for item in value:
                check(item)
    check(body)
    return {**body, 'recipeHash': canonical_hash(body)}


def parse_recipe(parser_version: str) -> dict:
    """Deterministic stage before any model call: parser, source IR and normalizer."""
    return _hashed({'recipeVersion': RECIPE_VERSION, 'stage': 'SOURCE_ONLY', 'parserVersion': parser_version,
                    'sourceIRVersion': IR_VERSION, 'normalizerVersion': NORMALIZER_VERSION})


def _digest(models, name):
    return next((m.get('digest') for m in models if isinstance(m, dict) and m.get('name') in {name, name + ':latest'}), None)


def index_settings(settings, models) -> dict:
    """Settings that shape a document's chunks and vectors; the indexer reports the ones it actually used."""
    return {'chunkerVersion': SPLITTER_VERSION, 'chunkSize': settings.chunk_size, 'chunkOverlap': settings.chunk_overlap,
            'embeddingModel': settings.embedding_model, 'embeddingDigest': _digest(models, settings.embedding_model)}


def processing_recipe(settings, provider, parser_version: str, method: str) -> dict:
    """Full recipe of one extraction run. `method` is the path actually taken for this document:
    'lab' (deterministic rows), 'visit', 'visit-review' or 'legacy' (LLM facts)."""
    models = provider.health().get('models', [])
    deterministic = method == 'lab'
    annotation = {
        'lab': {'annotationVersion': LAB_VERSION, 'projectionVersion': LAB_PROJECTION_VERSION, 'promptVersion': None},
        'visit': {'annotationVersion': VISIT_VERSION, 'projectionVersion': None, 'promptVersion': VISIT_PROMPT_VERSION},
        'visit-review': {'annotationVersion': REVIEW_VERSION, 'projectionVersion': None, 'promptVersion': REVIEW_PROMPT_VERSION},
        'legacy': {'annotationVersion': None, 'projectionVersion': None, 'promptVersion': PROMPT_VERSION},
    }[method]
    options = None if deterministic or not hasattr(provider, 'generation_options') else provider.generation_options('TASK: extraction')
    return _hashed({
        'recipeVersion': RECIPE_VERSION,
        'profile': settings.extraction_profile,
        'method': method,
        'parse': parse_recipe(parser_version),
        # Flat keys kept for the existing document API and evaluation reports.
        'sourceIRVersion': IR_VERSION, 'normalizerVersion': NORMALIZER_VERSION,
        'model': None if deterministic else settings.llm_model,
        'modelDigest': None if deterministic else _digest(models, settings.llm_model),
        'generationOptions': options,
        'annotation': {**annotation, 'factSchemaVersion': SCHEMA_VERSION,
                       'maxFactsPerBatch': None if method != 'legacy' else settings.extraction_max_facts_per_batch},
        # Expected index settings; the indexer confirms the ones it used in the revision's index manifest.
        'index': index_settings(settings, models),
    })

