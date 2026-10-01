"""Hook for the existing generator's BatchProcessor.

Runs after summaries, worksheets and questions have been stored. The document
argument supplies identity only; grounding always comes back from
``ai.summaries`` and goals always come from ``ai.worksheets`` so CLI and batch
generation use one contract.
"""
from .config import Settings
from .content import open_content
from .llm import OpenRouterLLM
from .pipeline import generate_lesson


def generate_for_document(document_data, storage_db, settings=None, llm=None, *, force=False, progress=None):
    """document_data: the Documents API record the batch is processing. Returns the result dict."""
    s = settings or Settings()
    if s.col_knowledge in {s.col_summaries, s.col_worksheets, s.col_questions, 'mindmaps'}:
        raise ValueError('The knowledge destination must differ from the source collections.')
    identities = (("uuid", document_data.get("uuid")),
                  ("idx", document_data.get("idx")),
                  ("custom_id", document_data.get("custom_id")))
    id_type, lesson_id = next(((kind, str(value)) for kind, value in identities if value not in (None, "")), (None, None))
    if lesson_id is None:
        return {"lesson_id": "", "status": "no_content", "reason": "document has no usable identity"}
    return generate_lesson(lesson_id, id_type, content_src=open_content(s, storage_db),
                           db=storage_db, llm=llm or OpenRouterLLM(s), s=s,
                           force=force, progress=progress)
