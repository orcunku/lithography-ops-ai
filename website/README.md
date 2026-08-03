# LithoOps AI — Landing Page

A single-file "wow" landing page for the project. No build step, no dependencies.

## What to edit before publishing
Open `index.html` and replace these placeholders (they appear as `href` values):
- `#GITHUB_URL`  -> your GitHub repo URL
- `#DEMO_URL`    -> your live Streamlit demo URL (or the repo if not deployed yet)
- `#REPORT_URL`  -> a link to the PDF report (e.g. the file in /docs on GitHub)

Use Find & Replace in any text editor. Each appears 2-3 times.

## How to view locally
Just double-click `index.html` — it opens in your browser. That's it.

## How to publish free (GitHub Pages)
1. Put the whole project on GitHub.
2. Repo -> Settings -> Pages -> Source: "Deploy from a branch" -> branch `main`, folder `/root` (or move index.html to the repo root / a `/docs` folder).
3. Your page goes live at https://<your-username>.github.io/<repo-name>/
