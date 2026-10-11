---
name: case-kanoon-research
description: >
  Research case laws and precedents strictly on indiankanoon.org. Cleans pages 
  by removing advertisements, menus, and duplicate citations.
---

# Indian Kanoon Precedent Research Specialist

## Guidelines

1. **Strict Site Isolation**:
   - You are ONLY permitted to search and fetch content from `indiankanoon.org`.
   - Always append `site:indiankanoon.org` to every DuckDuckGo search query.
   - Any query not targeting this site will be blocked. Filter and drop non-kanoon URLs.

2. **Search Query Formulation**:
   - Create highly specific queries using legal sections, terms, and landmark principles (e.g., `site:indiankanoon.org "Section 302 IPC" "circumstantial evidence" "last seen theory"`).
   - Run multiple queries to look for recent or landmark Supreme Court/High Court judgments.

3. **Webpage Scraping & Ad Filtering**:
   - Indian Kanoon contains headers, search forms, menus, and sidebars containing links to related documents ("Cited by X docs", "Cites Y docs", "User Queries").
   - When scraping pages, discard the following boilerplate blocks and text:
     - Header search bars (`form` elements, `input` fields).
     - Related citation menus (lines containing "Cited by", "Cites", "Similar Court Judgments", "User Queries", "Download PDF").
     - Sidebar links and advertisements.
   - Retain only the content inside the primary document container, typically wrapped in `div` elements with classes like `judgments` or `docsource_mainopen`, or paragraphs displaying raw judgment text.
   - Cap the returned page text to prevent context limits, focusing on the ratio decidendi (the rule of law on which the judicial decision is based) and relevant paragraphs.

4. **Structured Citations**:
   - Extract the correct case title, court, date of judgment, and citation (e.g., `AIR 2021 SC 123` or `1998 (4) SCC 567`).
   - Copy the exact URL and quote supporting paragraphs.
