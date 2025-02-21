from application.app import app
from chonkie import SentenceChunker
from typing import List, Dict

@app.function_name(name="chunking")
@app.activity_trigger(input_name="document")
def chunking(document: Dict) -> List[str]:
    chunker = SentenceChunker(
        tokenizer="gpt2",
        chunk_size=512,
        chunk_overlap=128,
        min_sentences_per_chunk=1
    )
    only_text_pages = [page for page in document["pages"]]
    all_text = "".join(only_text_pages)
    chunks = chunker.chunk(all_text)
    chunks_with_page_numbers = []
    for chunk in chunks:
        chunks_with_page_numbers.append({
            "filename": document["filename"],
            "url": document["url"],
            "text": chunk.text,
            "start_page": get_page_number(chunk.start_index, only_text_pages),
            "end_page": get_page_number(chunk.end_index, only_text_pages),
            "start_index": chunk.start_index,
            "end_index": chunk.end_index,
            "token_count": chunk.token_count,
        })
    return chunks_with_page_numbers

def get_page_number(position: int, pages: List[str]) -> int:
    position -= 1
    for page_number, page_content in enumerate(pages):
        if position < len(page_content):
            return page_number
        position -= len(page_content)
    raise ValueError("Position out of range")