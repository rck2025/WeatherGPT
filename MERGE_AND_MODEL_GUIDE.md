# WeatherGPT — Merge Guide, Branch Management & Gemini Model Reference

This document summarizes the full discussion regarding merging `feature/refactor-modular-backend` into `main`, Git branching best practices, missing file requirements, and Gemini model/API key configurations.

---

## 1. Step-by-Step Merge Process (`feature/refactor-modular-backend` $\rightarrow$ `main`)

### Exact Commands:
```bash
# 1. Ensure you are on main and up-to-date
git checkout main
git pull origin main

# 2. Fetch the latest changes from the remote feature branch
git fetch origin feature/refactor-modular-backend

# 3. Merge the feature branch (creates the new folders and files)
git merge --no-ff origin/feature/refactor-modular-backend -m "Merge feature/refactor-modular-backend into main"

# 4. Add the missing __init__.py files so Python recognizes packages
touch "backend/services/api/__init__.py"
touch "backend/services/api/v1/__init__.py"
touch "backend/services/ingestion/__init__.py"

# 5. Commit the package init files
git add backend/services/api/__init__.py backend/services/api/v1/__init__.py backend/services/ingestion/__init__.py
git commit -m "Add missing __init__.py for api and ingestion packages"

# 6. Push local main to GitHub
git push origin main
```

---

## 2. Git Concepts & FAQ Summary

### Q: Do I need to `git pull` the feature branch first?
* **No.** You do not need to check out the feature branch locally. `git fetch origin <branch>` downloads the remote references, allowing you to merge `origin/feature/refactor-modular-backend` directly into `main`.

### Q: Does the feature branch still exist after merging?
* **Yes.** Merging simply copies the commit history into `main`. The feature branch remains untouched on GitHub until explicitly deleted.

### Q: Can I amend the commit message before pushing?
* **Yes.** As long as the commit has not been pushed to the remote repository, you can safely run:
  ```bash
  git commit --amend -m "Your new message"
  ```

### Q: Should I reuse the same branch name for future work?
* **Best Practice:** No. Once a branch is merged, create a fresh branch off `main` for new tasks (e.g., `feature/rag-enhancements`).

### Q: Do local and remote branch names have to match?
* **Technically no, but convention is yes.** Running `git push origin main` is shorthand for `git push origin main:main`.

---

## 3. Ingestion Pipeline Architecture & `UniversalScraper`

* **Location:** `backend/services/ingestion/scraper.py`
* **Role:** Extracts raw text strings from diverse sources (URLs, PDFs, DOCX, XLSX, JSON, TXT).
* **Pipeline Flow:**
  ```
  Source (URL / File) ──> UniversalScraper.extract_text() ──> WeatherAlertAdapter.adapt() ──> WeatherAlert Schema
  ```

---

## 4. Gemini Model Configuration & API Keys

### Model Configuration Location:
* **File:** [`backend/services/rag/service.py`](file:///Users/riyajkhan/Desktop/SIH%202026/WeatherGPT/backend/services/rag/service.py) (Lines 31–36)
  ```python
  class WeatherGPTBrain:
      def __init__(
          self,
          db_path: Path | str = DB_DIR,
          llm_model: str = "gemini-flash-latest",            # <--- Line 33: LLM Model
          embedding_model: str = "models/gemini-embedding-001", # <--- Line 34: Embedding Model
      ) -> None:
  ```

### Are API Keys Model-Specific?
* **No.** An API Key (`GEMINI_API_KEY`) represents your **account-level identity pass**.
* A single key in `backend/.env` can authenticate requests for:
  - `gemini-flash-latest`
  - `gemini-1.5-flash`
  - `gemini-1.5-pro`
  - `models/gemini-embedding-001`
* To switch models, you only change the `llm_model` string in `service.py`. No code refactoring or new API keys are required.
