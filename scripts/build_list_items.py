#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov 12 23:50:38 2025

@author: leefeinman

Insert list/link items on the three main pages for built blog posts.

- Operates ONLY on posts with blog_built: true AND list_built is missing/false.
- Section routing:
    policy         -> append in climate-policy.astro (timeline end)
    misinformation -> prepend in climate-misinformation.astro (newest first, renumber existing)
    education      -> prepend in climate-education.astro (newest first)
- Uses front matter: title, short_description, keywords, image, date, blog_slug, blog_number
- Marks each processed post with: list_built: true, list_built_at: "<ISO min>"

Run from repo root.
"""

from pathlib import Path
import re
from datetime import datetime
import frontmatter
from slugify import slugify

ROOT = Path(__file__).resolve().parents[1]
MD_ROOT = ROOT / "src" / "content" / "posts"
PAGES_DIR = ROOT / "src" / "pages"

FILES = {
    "policy":         PAGES_DIR / "climate-policy.astro",
    "misinformation": PAGES_DIR / "climate-misinformation.astro",
    "education":      PAGES_DIR / "climate-education.astro",
}

# Managed regions (we insert markers if missing for policy/misinfo/edu)
MARKERS = {
    "policy":         ("<!-- LIST:POLICY:START -->",  "<!-- LIST:POLICY:END -->"),
    "misinformation": ("<!-- LIST:MISINFO:START -->", "<!-- LIST:MISINFO:END -->"),
    "education":      ("<!-- LIST:EDU:START -->",     "<!-- LIST:EDU:END -->"),
}

# Container OPEN patterns where we add markers if missing
CONTAINER_OPEN = {
    "policy":         r'(<div\s+class="step-right[^"]*">)',
    "misinformation": r'(<div\s+role="list"\s+class="w-dyn-items">)',
    "education":      r'(<div[^>]*class="[^"]*blog-coll-grid[^"]*w-dyn-items[^"]*"[^>]*>)',
}

def load_candidates():
    for section in ("policy", "misinformation", "education"):
        d = MD_ROOT / section
        if not d.exists():
            continue
        for p in d.glob("*.md"):
            post = frontmatter.load(p)
            if str(post.get("blog_built")).lower() != "true":
                continue
            if str(post.get("list_built")).lower() == "true":
                continue
            yield section, p, post

def fmt_date(val):
    if not val: return "", ""
    s = str(val).strip()
    year = s[:4] if re.match(r'^\d{4}', s) else ""
    return s, year

def esc_html(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

# ---------------- POLICY helpers ----------------

POLICY_LINE_BAR_RE = re.compile(
    r'(<div\s+class="step-line">\s*<div\s+class="step-line-bar"></div>\s*</div>)',
    re.IGNORECASE
)
POLICY_LAST_POINT_RE = re.compile(
    r'(<div\s+class="step-point\s+(_[^"]+)">\s*<div\s+class="step-count">\s*(\d{2})\s*</div>\s*</div>)',
    re.IGNORECASE
)

def policy_get_last_point(page_text: str):
    """
    Return (full_match, class_suffix, count_str, start_idx, end_idx) for the point
    immediately preceding the step-line-bar. If none found, return None.
    """
    line_bar = POLICY_LINE_BAR_RE.search(page_text)
    if not line_bar:
        return None
    before = page_text[:line_bar.start()]
    # find the last step-point before the line bar
    last = None
    for m in POLICY_LAST_POINT_RE.finditer(before):
        last = m
    if not last:
        return None
    return (last.group(1), last.group(2), last.group(3), last.start(), last.end(), line_bar.start(), line_bar.end())

def policy_insert_new_points(page_text: str, how_many: int):
    """
    Insert 'how_many' new step-point blocks immediately before the step-line-bar.
    Each new block copies the previous class suffix and increments the step-count.
    Returns (new_text, added_counts_list)
    """
    if how_many <= 0:
        return page_text, []

    added_counts = []
    text = page_text
    for _ in range(how_many):
        found = policy_get_last_point(text)
        if not found:
            # Cannot locate structure; bail without changes
            return text, added_counts
        full, cls_sfx, count_str, pt_start, pt_end, bar_start, bar_end = found
        n = int(count_str)
        n_next = n + 1
        added_counts.append(n_next)
        new_point = f'<div class="step-point {cls_sfx}"><div class="step-count">{n_next:02d}</div></div>\n'
        # Insert just before the line bar
        text = text[:bar_start] + new_point + text[bar_start:]
    return text, added_counts

# ---------------- BUILDERS ----------------

def build_policy_item(post, display_number: int) -> str:
    """Policy: whole card clickable; number comes from step-line wrap increment."""
    title = esc_html(post.get("title") or "")
    short = esc_html(post.get("short_description") or "")
    date_s, year = fmt_date(post.get("date"))
    slug = post.get("blog_slug") or f'policy_{post.get("blog_number") or 0}_{slugify(title)}'
    head = f"{year} — {title}" if year else title
    href = f"/{slug}"

    return f'''\
<a class="step-card step-card-link" href="{href}">
  <div class="step-number">{display_number:02d}</div>
  <h3 class="step-title">{head}</h3>
  <p class="step-content">{short}</p>
</a>'''

def build_misinfo_item(post) -> str:
    title = esc_html(post.get("title") or "")
    short = esc_html(post.get("short_description") or "")
    num = post.get("blog_number") or 0
    slug = post.get("blog_slug") or f'misinformation_{num}_{slugify(title)}'
    href = f"/{slug}"

    return f'''\
<div role="listitem" class="w-dyn-item">
  <div class="service-item">
    <div class="service-item-left">
      <div class="service-number">01</div>
      <a href="{href}" class="service-title">"{title}"</a>
      <div class="service-info">
        <p class="service-summary">{short}</p>
      </div>
    </div>
  </div>
</div>'''

def build_education_item(post) -> str:
    title = esc_html(post.get("title") or "")
    short = esc_html(post.get("short_description") or "")
    date_s, _ = fmt_date(post.get("date"))
    kws = post.get("keywords") or []
    cat = esc_html(str(kws[0])) if kws else "Education"
    img = post.get("image") or "https://placehold.co/800x500/jpg"
    num = post.get("blog_number") or 0
    slug = post.get("blog_slug") or f'education_{num}_{slugify(title)}'
    href = f"/{slug}"

    return f'''\
<div role="listitem" class="blog-coll-item w-dyn-item">
  <article class="blog-item">
    <div class="blog-thumb-wrap">
      <img alt="{title}" loading="lazy" src="{img}" class="blog-thumb" />
    </div>
    <div class="blog-meta">
      <a href="#" class="blog-category-link">{cat}</a>
      <div class="blog-date">{esc_html(date_s)}</div>
    </div>
    <a href="{href}" class="blog-title">{title}</a>
    <p class="blog-excerpt">{short}</p>
  </article>
</div>'''

# ---------------- Region utilities ----------------

def ensure_markers(section: str, page_text: str) -> str:
    start, end = MARKERS[section]
    if start in page_text and end in page_text:
        return page_text
    open_re = CONTAINER_OPEN[section]
    open_m = re.search(open_re, page_text)
    if not open_m:
        raise SystemExit(f"Could not find insertion OPEN container for {section} in its .astro page.")
    insert_pos = open_m.end()
    # For policy, we want markers inside .step-right; putting them after the open is fine.
    marker_block = f"\n  {start}\n  {end}\n"
    return page_text[:insert_pos] + marker_block + page_text[insert_pos:]

def insert_items(section: str, page_text: str, items_html: list[str]) -> str:
    start, end = MARKERS[section]
    if start not in page_text or end not in page_text:
        page_text = ensure_markers(section, page_text)

    head, body = page_text.split(start, 1)
    region, tail = body.split(end, 1)

    region_content = region.strip("\n")
    block = "\n".join(items_html)

    if section == "policy":
        # APPEND within region
        new_region_inner = (region_content + ("\n" if region_content else "") + block).strip("\n")
    else:
        # PREPEND within region
        new_region_inner = (block + ("\n" if region_content else "") + region_content).strip("\n")

    new_region = "\n  " + "\n  ".join([ln for ln in new_region_inner.splitlines()]) + "\n"
    return head + start + new_region + end + tail

# ---------- MISINFO renumber inside actual container ----------

MISINFO_CONTAINER_OPEN_RE = re.compile(
    r'<div[^>]*\brole=["\']list["\'][^>]*\bclass=["\'][^"\']*\bw-dyn-items\b[^"\']*["\'][^>]*>',
    re.IGNORECASE
)

SERVICE_NUM_FLEX_RE = re.compile(
    r'(?P<prefix><div[^>]*\bclass=["\'][^"\']*\bservice-number\b[^"\']*["\'][^>]*>\s*(?:<span[^>]*>\s*)?)'
    r'(?P<num>\d+)'  # the number we’ll replace
    r'(?P<suffix>\s*(?:</span>)?\s*</div>)',
    re.IGNORECASE
)

def _find_matching_div_close(html: str, start_index: int) -> int:
    """
    From start_index (right after an opening <div ...>), walk forward and return the
    index where the matching closing </div> starts. Returns -1 if not found.
    """
    tag_re = re.compile(r'<div\b[^>]*>|</div>', re.IGNORECASE)
    depth = 1
    for m in tag_re.finditer(html, start_index):
        tok = m.group(0).lower()
        if tok.startswith('<div'):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return m.start()
    return -1

def renumber_misinfo_in_container(page_text: str) -> str:
    """
    Find <div role="list" class="w-dyn-items"> ... </div> and renumber all service-number
    divs inside sequentially: 01, 02, 03, ...
    """
    open_m = MISINFO_CONTAINER_OPEN_RE.search(page_text)
    if not open_m:
        # No container found; bail quietly
        return page_text

    open_start = open_m.start()
    open_end   = open_m.end()
    close_start = _find_matching_div_close(page_text, open_end)
    if close_start == -1:
        # Couldn’t match closing </div>; bail quietly
        return page_text

    container_open = page_text[open_start:open_end]
    container_inner = page_text[open_end:close_start]
    container_close = '</div>'

    # Renumber inside the container_inner
    idx = 0
    def repl(m):
        nonlocal idx
        idx += 1
        return f'{m.group("prefix")}{idx:02d}{m.group("suffix")}'

    inner_new = SERVICE_NUM_FLEX_RE.sub(repl, container_inner)

    # Reassemble
    return page_text[:open_start] + container_open + inner_new + container_close + page_text[close_start+len(container_close):]


# ---------------- MAIN ----------------

def main():
    grouped = {"policy": [], "misinformation": [], "education": []}
    for section, p, post in load_candidates():
        grouped[section].append((p, post))

    total = sum(len(v) for v in grouped.values())
    print(f"Found {total} post(s) needing list entries.")

    # POLICY — compute display numbers from step-line, then append
    if grouped["policy"]:
        page_path = FILES["policy"]
        page_text = page_path.read_text(encoding="utf-8")
        page_text = ensure_markers("policy", page_text)

        # For stable list order, sort by blog_number (older first), we append in that order.
        items = sorted(grouped["policy"], key=lambda t: (t[1].get("blog_number") or 0))

        # For each new item, insert one new step-point and record the number assigned
        assigned_numbers = []
        for _ in items:
            page_text, added = policy_insert_new_points(page_text, how_many=1)
            if not added:
                raise SystemExit("Policy structure not found (no step-line / step-point to extend).")
            assigned_numbers.append(added[0])

        # Build snippets using assigned numbers
        snippets = [build_policy_item(post, num) for (_, post), num in zip(items, assigned_numbers)]
        page_text = insert_items("policy", page_text, snippets)

        page_path.write_text(page_text, encoding="utf-8")

        # mark md as list_built
        for md_path, post in items:
            post.metadata["list_built"] = True
            post.metadata["list_built_at"] = datetime.now().isoformat(sep="_", timespec="minutes")
            md_path.write_text(frontmatter.dumps(post), encoding="utf-8")

        rel = lambda p: (p.relative_to(ROOT) if p.is_relative_to(ROOT) else p)
        print(f"✓ Updated policy: {rel(page_path)}  (+{len(items)} items)")

    # MISINFORMATION — prepend then renumber container
    if grouped["misinformation"]:
        page_path = FILES["misinformation"]
        page_text = page_path.read_text(encoding="utf-8")
        page_text = ensure_markers("misinformation", page_text)
        items = grouped["misinformation"]  # newest first in our region (prepend)

        snippets = [build_misinfo_item(post) for _, post in items]
        page_text = insert_items("misinformation", page_text, snippets)
        page_text = renumber_misinfo_in_container(page_text)

        # Now renumber all visible service-number values inside the list container
        page_text = renumber_misinfo_in_container(page_text)

        page_path.write_text(page_text, encoding="utf-8")

        for md_path, post in items:
            post.metadata["list_built"] = True
            post.metadata["list_built_at"] = datetime.now().isoformat(sep="_", timespec="minutes")
            md_path.write_text(frontmatter.dumps(post), encoding="utf-8")

        rel = lambda p: (p.relative_to(ROOT) if p.is_relative_to(ROOT) else p)
        print(f"✓ Updated misinformation: {rel(page_path)}  (+{len(items)} items)")

    # EDUCATION — unchanged from your working version (prepend inside markers)
    if grouped["education"]:
        page_path = FILES["education"]
        page_text = page_path.read_text(encoding="utf-8")
        page_text = ensure_markers("education", page_text)
        items = grouped["education"]
        snippets = [build_education_item(post) for _, post in items]
        page_text = insert_items("education", page_text, snippets)
        page_path.write_text(page_text, encoding="utf-8")

        for md_path, post in items:
            post.metadata["list_built"] = True
            post.metadata["list_built_at"] = datetime.now().isoformat(sep="_", timespec="minutes")
            md_path.write_text(frontmatter.dumps(post), encoding="utf-8")

        rel = lambda p: (p.relative_to(ROOT) if p.is_relative_to(ROOT) else p)
        print(f"✓ Updated education: {rel(page_path)}  (+{len(items)} items)")

    if total == 0:
        print("Nothing to do — all built posts already have list entries.")

if __name__ == "__main__":
    main()
