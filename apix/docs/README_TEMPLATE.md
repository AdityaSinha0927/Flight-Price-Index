# README_TEMPLATE.md

This is not the final README — it's a template. Once the project is built,
generate the actual `README.md` at the project root using this structure,
filled in with real details from what was actually built.

## Required sections

1. **Project name and one-line description**
2. **Problem statement reference** — SIH Statement ID 26056, one-paragraph
   summary (pull from PROJECT_BRIEF.md)
3. **What this prototype does** — pull from SCOPE.md's "Definition of done"
4. **Architecture diagram** — reuse the diagram from ARCHITECTURE.md
5. **Tech stack** — table from ARCHITECTURE.md
6. **Setup instructions**
   - Python version required
   - `pip install -r requirements.txt`
   - Playwright browser install command (`playwright install`)
   - How to initialize the SQLite DB (`schema.sql`)
7. **How to run**
   - How to run the scraper manually (single run)
   - How to start the scheduler
   - How to run the cleaning pipeline
   - How to run the index engine
   - How to start the FastAPI server
   - How to start the Streamlit dashboard
8. **How to run tests** — `pytest` command
9. **Known limitations** — explicitly list simplifications made per SCOPE.md
   (2 routes, 2 sources, 3 windows, equal route weighting if DGCA traffic
   share wasn't available, estimated tax split where sites didn't break it
   out, etc.)
10. **Back-test results** — summary/chart of how the index compared to DGCA
    published data
11. **Ethical scraping note** — summary of the rules from SCRAPER_SPEC.md
    that were actually implemented
12. **Team / credits**
