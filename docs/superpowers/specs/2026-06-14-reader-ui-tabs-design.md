# Reader UI Tabs Design

## Goal

Redesign the GitHub Pages reader so it feels aligned with `https://foreverhyx.top/articles` while keeping the recommender static, fast, and fully driven by `recommendations.json`, `status.json`, and browser state.

## Requirements

- Keep a floating top navigation island.
- Add top-level tabs by type:
  - `全部`
  - `论文`
  - `仓库`
  - `画像与系统`
- In recommendation tabs, use the articles-page layout pattern: recommendation feed on the left, filtering panel on the right.
- The right panel must include keyword filters with two keyword categories:
  - item-type keywords: `paper`, `repository`
  - content keywords derived from paper/repository content, including categories, repository language/topics, title/summary/abstract terms, and paper links.
- Keep existing controls that matter for daily use: search, section, minimum AI score, code availability, affiliation availability, sorting, and section quick links.
- Move user profile, feedback-learning status, run health, and subsystem/system settings into the `画像与系统` tab instead of mixing them into the recommendation filter sidebar.
- Preserve inline like/dislike behavior, deep links from email, repository cards, original paper links, author-affiliation display, and static Pages deployment.

## Reference UI

The homepage `articles` page uses:

- a centered floating `nav-island`;
- a left article list and right tag sidebar;
- glass-like cards with restrained blue/white transparency;
- chips for tag filtering;
- compact metadata rows and calm typography.

This reader should adapt those patterns without importing the Next.js app or requiring a build step.

## Proposed Approach

Implement the redesign in the existing static files:

- `site/index.html` defines the floating island, tab controls, left feed, and right panels.
- `site/app.js` owns UI state for `activeTab`, section/search/score/sort filters, and keyword chips.
- `site/styles.css` provides the glass/articles-inspired layout and responsive behavior.
- `tests/test_site_contract.py` extends the Node VM contract tests so the layout and filtering behavior are covered.

The keyword system stays client-side. It computes a frequency-sorted vocabulary from currently loaded recommendations, separating item type chips from content chips. Selecting keyword chips filters recommendations by normalized `searchTextFor(paper)`.

## Data Flow

1. Load `recommendations.json`.
2. Render top summary, tab counts, and filter controls.
3. Derive keyword facets from recommendations:
   - item-type chips: `paper`, `repository`;
   - content chips: sections, arXiv categories, repository languages, repository topics, original paper link labels, and selected domain terms found in searchable text.
4. Apply active tab and filters.
5. Render grouped recommendation sections in the left feed.
6. Render profile/system content only when the `画像与系统` tab is selected.

## Error Handling

- If `status.json` is unavailable, keep rendering recommendations and show system status as unavailable.
- If no recommendations match filters, show a clear empty state.
- If keyword derivation has no content terms, show an empty keyword message rather than failing render.
- Inline feedback continues to use Supabase when configured and localStorage fallback otherwise.

## Testing

Contract tests should prove:

- `index.html` contains the floating island, tab bar, recommendation feed, and right keyword panel hooks.
- item-type tabs filter papers vs repositories.
- keyword chips filter by repository/topic/content text.
- profile/system status renders in a separate tab panel.
- existing inline feedback, run health, affiliation, and deep-link behaviors remain intact.

