import asyncio
from ingestion.importer import ingest_pdf
from memory.schema import init_db

init_db()

try:
    result = ingest_pdf("test.pdf", "test.pdf")
    print(result)
except Exception as e:
    import traceback
    traceback.print_exc()
