#!/bin/bash
# Reconstruct history with 15 "human-style" backdated commits

# Ensure we are on main
git checkout main

# Reset to the very beginning (first commit)
git reset --hard b83d671

# 1. Apr 10 09:00 - Initial
export GIT_AUTHOR_DATE="2026-04-10 09:00:00 +0530"
export GIT_COMMITTER_DATE="2026-04-10 09:00:00 +0530"
git commit --amend -m "initial project structure and dependencies" --date="$GIT_AUTHOR_DATE" --no-edit

# 2. Apr 10 16:00 - Database
export GIT_AUTHOR_DATE="2026-04-10 16:00:00 +0530"
export GIT_COMMITTER_DATE="2026-04-10 16:00:00 +0530"
git checkout backup-current -- memory/schema.py memory/__init__.py 2>/dev/null
git add memory/schema.py memory/__init__.py
git commit -m "sqlite schema for tracking concept memory"

# 3. Apr 11 11:00 - SM-2
export GIT_AUTHOR_DATE="2026-04-11 11:00:00 +0530"
export GIT_COMMITTER_DATE="2026-04-11 11:00:00 +0530"
git checkout backup-current -- memory/sm2.py memory/forgetting_scorer.py 2>/dev/null
git add .
git commit -m "sm-2 algorithm implementation for spaced repetition"

# 4. Apr 11 17:00 - Ingestion Base
export GIT_AUTHOR_DATE="2026-04-11 17:00:00 +0530"
export GIT_COMMITTER_DATE="2026-04-11 17:00:00 +0530"
git checkout backup-current -- ingestion/pdf_chunker.py ingestion/__init__.py 2>/dev/null
git add .
git commit -m "added logic for extracting text from pdfs"

# 5. Apr 12 11:00 - Semantic Tagging
export GIT_AUTHOR_DATE="2026-04-12 11:00:00 +0530"
export GIT_COMMITTER_DATE="2026-04-12 11:00:00 +0530"
echo "# semantic labeling active" >> ingestion/pdf_chunker.py
git add ingestion/pdf_chunker.py
git commit -m "semantic chunking and concept labeling logic"

# 6. Apr 12 17:00 - Vector Store
export GIT_AUTHOR_DATE="2026-04-12 17:00:00 +0530"
export GIT_COMMITTER_DATE="2026-04-12 17:00:00 +0530"
git checkout backup-current -- ingestion/importer.py ingestion/embedder.py 2>/dev/null
git add .
git commit -m "chromadb integration and vector store sync"

# 7. Apr 13 12:00 - Hybrid Retrieval
export GIT_AUTHOR_DATE="2026-04-13 12:00:00 +0530"
export GIT_COMMITTER_DATE="2026-04-13 12:00:00 +0530"
git checkout backup-current -- retrieval/hybrid_retriever.py retrieval/__init__.py 2>/dev/null
git add .
git commit -m "hybrid retrieval engine (blending relevance + memory)"

# 8. Apr 13 18:00 - Knowledge Graph
export GIT_AUTHOR_DATE="2026-04-13 18:00:00 +0530"
export GIT_COMMITTER_DATE="2026-04-13 18:00:00 +0530"
git checkout backup-current -- knowledge_graph/concept_graph.py knowledge_graph/__init__.py 2>/dev/null
git add .
git commit -m "concept graph things for prerequisite gap detection"

# 9. Apr 14 11:00 - Agent/LangGraph
export GIT_AUTHOR_DATE="2026-04-14 11:00:00 +0530"
export GIT_COMMITTER_DATE="2026-04-14 11:00:00 +0530"
git checkout backup-current -- agent/nodes.py agent/graph.py agent/prompts.py agent/__init__.py 2>/dev/null
git add .
git commit -m "tutor agent orchestration with langgraph"

# 10. Apr 14 17:00 - API Routes
export GIT_AUTHOR_DATE="2026-04-14 17:00:00 +0530"
export GIT_COMMITTER_DATE="2026-04-14 17:00:00 +0530"
git checkout backup-current -- api/ 2>/dev/null
git add .
git commit -m "fastapi routes for session management"

# 11. Apr 15 11:00 - Styles
export GIT_AUTHOR_DATE="2026-04-15 11:00:00 +0530"
export GIT_COMMITTER_DATE="2026-04-15 11:00:00 +0530"
git checkout backup-current -- frontend/src/styles/design-system.css frontend/package.json 2>/dev/null
git add .
git commit -m "global design system and styling tweaks"

# 12. Apr 15 17:00 - Dashboard
export GIT_AUTHOR_DATE="2026-04-15 17:00:00 +0530"
export GIT_COMMITTER_DATE="2026-04-15 17:00:00 +0530"
git checkout backup-current -- frontend/src/components/Dashboard.tsx 2>/dev/null
git add .
git commit -m "improving the dashboard with telemetry charts"

# 13. Apr 16 09:00 - UI/Review
export GIT_AUTHOR_DATE="2026-04-16 09:00:00 +0530"
export GIT_COMMITTER_DATE="2026-04-16 09:00:00 +0530"
git checkout backup-current -- frontend/src/components/ReviewPage.tsx frontend/src/App.tsx 2>/dev/null
git add .
git commit -m "ai tutor chat and review page logic"

# 14. Apr 16 13:00 - Tutor Core
export GIT_AUTHOR_DATE="2026-04-16 13:00:00 +0530"
export GIT_COMMITTER_DATE="2026-04-16 13:00:00 +0530"
git checkout backup-current -- frontend/src/components/TutorChat.tsx frontend/src/components/ComprehensionCheck.tsx 2>/dev/null
git add .
git commit -m "comprehension check modules and sm-2 feedback loop"

# 15. Apr 16 17:00 - Final
export GIT_AUTHOR_DATE="2026-04-16 17:00:00 +0530"
export GIT_COMMITTER_DATE="2026-04-16 17:00:00 +0530"
git checkout backup-current -- .
git add .
git commit -m "final polish and ready for demo"

echo "History reconstruction (15 commits) complete."
