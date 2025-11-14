#!/usr/bin/env python3
"""
Build NEW blog posts only (no args).

- Looks under: src/content/posts/{policy,misinformation,education}/*.md
- Skips files whose front matter has blog_built: true
- For each new .md:
    * assigns/persists blog_number per section (stable)
    * renders Markdown -> Astro using your Site layout + elements structure
    * writes to: src/pages/blog/<section>_<num>_<slug>.astro
    * writes back to the .md front matter:
        - blog_built: true
        - blog_built_at: ISO timestamp
        - blog_slug: "<section>_<num>_<slugified-title>"

Run from repo root or ensure cwd is repo root.
"""

from pathlib import Path
import re
from datetime import datetime, timezone
import frontmatter
from slugify import slugify
from markdown_it import MarkdownIt

# ---------------- Paths ----------------
ROOT = Path(__file__).resolve().parents[1]
MD_ROOT = ROOT / "src" / "content" / "posts"
ASTRO_OUT = ROOT / "src" / "pages"   # <— you set this; pages are written here

SECTIONS = ("policy", "misinformation", "education")

# ---------------- Markdown renderer ----------------
md = (
    MarkdownIt(
        "commonmark",
        {"html": True, "linkify": True, "typographer": True}
    )
    .enable("table")
    .enable("strikethrough")
)

# ---------------- Astro template ----------------
ASTRO_POST_TEMPLATE = """---
import Site from "../layouts/Site.astro";
---
<Site title="{title}">
  <main class="main-wrap">
    <section class="blog-detail">
      <div class="w-layout-blockcontainer container w-container">
        <div class="blog-details-wrap">
          {date_block}{author_block}
          <h1 class="heading-six pt-10">{title}</h1>
          {hero_block}
          <div class="rich-text w-richtext">
{html_body_indented}
          </div>
        </div>
      </div>
    </section>
  </main>
</Site>
"""

# ---------------- Helpers ----------------
def sanitize_md_file(path: Path):
    raw = path.read_bytes()
    # Strip BOM
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    text = raw.decode('utf-8', errors='replace')
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Normalize first delimiter
    lines = text.split('\n')
    if lines and lines[0].replace('\u00a0', ' ').strip() == '---':
        lines[0] = '---'
        text = '\n'.join(lines)
    path.write_text(text, encoding='utf-8')

def read_candidate_markdown():
    """Yield (path, Post) for .md files that are NOT yet blog_built."""
    for sec in SECTIONS:
        sec_dir = MD_ROOT / sec
        if not sec_dir.exists():
            continue
        for p in sec_dir.glob("*.md"):
            try:
                sanitize_md_file(p)
                post = frontmatter.load(p)              # keep the Post object
            except Exception as e:
                raise SystemExit(f"Front matter parse error in: {p}\n→ {e!r}")

            # tolerant boolean: True / "true" / "True"
            flag = post.get("blog_built")
            if isinstance(flag, str):
                flag = flag.strip().lower() == "true"
            if flag is True:
                continue  # skip already-built

            yield p, post                               # yield inside the loop

def collect_existing_numbers(section: str) -> set[int]:
    """Collect existing numbers from already-built Astro pages for stable numbering."""
    nums = set()
    for p in ASTRO_OUT.glob(f"{section}_*_*.astro"):
        m = re.match(rf"{re.escape(section)}_(\d+)_", p.stem)
        if m:
            nums.add(int(m.group(1)))
    return nums

# --- NEW: overwrite-by-title support ---------------------------------
def find_existing_number_for_slug(section: str, title: str) -> int | None:
    """
    If a page already exists for this section+title slug, return its number.
    Warn if multiple matches (shouldn't happen).
    """
    slug = slugify(title)
    matches = list(ASTRO_OUT.glob(f"{section}_*_{slug}.astro"))
    if not matches:
        return None
    if len(matches) > 1:
        print(f"⚠️  Found multiple pages for slug '{section}_{slug}'; "
              f"reusing lowest number. ({[m.name for m in matches]})")
    # pick the lowest number among matches
    nums = []
    for p in matches:
        m = re.match(rf"{re.escape(section)}_(\d+)_", p.stem)
        if m:
            nums.append(int(m.group(1)))
    return min(nums) if nums else None

def assign_or_reuse_number(section: str, title: str, post: frontmatter.Post) -> int:
    """
    Reuse number if an existing page with the same section+title slug exists.
    Otherwise keep a valid blog_number if provided, else assign next available.
    """
    reuse = find_existing_number_for_slug(section, title)
    if isinstance(reuse, int) and reuse > 0:
        post.metadata["blog_number"] = reuse
        return reuse

    existing = post.get("blog_number")
    if isinstance(existing, int) and existing > 0:
        return existing

    used = collect_existing_numbers(section)
    next_num = max(used) + 1 if used else 1
    post.metadata["blog_number"] = next_num
    return next_num
# ---------------------------------------------------------------------

def render_astro_page(section: str, title: str, date_s: str, author: str, image: str, html_body: str) -> str:
    html_indented = "\n".join(("            " + ln if ln.strip() else "") for ln in html_body.splitlines())
    date_block = f'<div class="blog-date">{date_s}</div>' if date_s else ""
    author_block = f'<div class="blog-date">{author}</div>' if author else ""
    hero_block = f'<img src="{image}" alt="{title}" class="blog-detail-thumb"/>' if image else ""
    return ASTRO_POST_TEMPLATE.format(
        title=title,
        date_block=date_block,
        author_block=author_block,
        hero_block=hero_block,
        html_body_indented=html_indented,
    )

def process_one(md_path: Path, post: frontmatter.Post):
    section = (post.get("section") or "").strip().lower()
    title   = (post.get("title") or "").strip()
    if section not in SECTIONS:
        raise SystemExit(f"{md_path}: front matter 'section' must be one of {SECTIONS}")
    if not title:
        raise SystemExit(f"{md_path}: front matter 'title' is required")

    # NEW: reuse number if same section+title exists, else assign next
    num = assign_or_reuse_number(section, title, post)

    html = md.render(post.content or "")
    html = re.sub(r'<img(?![^>]*class=)', r'<img class="blog-inline-image"', html)


    slug = slugify(title)
    out_name = f"{section}_{num}_{slug}.astro"
    out_path = ASTRO_OUT / out_name
    ASTRO_OUT.mkdir(parents=True, exist_ok=True)

    date_s = (str(post.get("date")) or "").strip()
    author = (post.get("author") or "").strip()
    image  = (post.get("image") or "").strip()
    astro  = render_astro_page(section, title, date_s, author, image, html)
    out_path.write_text(astro, encoding="utf-8")

    # Mark as built in front matter (idempotent)
    post.metadata["blog_built"] = True
    post.metadata["blog_built_at"] = datetime.now().isoformat(sep="_", timespec="minutes")
    post.metadata["blog_slug"] = f"{section}_{num}_{slug}"
    post.metadata["blog_number"] = num
    md_path.write_text(frontmatter.dumps(post), encoding="utf-8")

    rel = lambda p: (p.relative_to(ROOT) if p.is_relative_to(ROOT) else p)
    print(f"✓ Built/updated: {rel(out_path)}  | marked built in: {rel(md_path)}")

def main():
    ASTRO_OUT.mkdir(parents=True, exist_ok=True)
    any_built = False
    candidates = list(read_candidate_markdown())
    print(f"Found {len(candidates)} new/edited candidate post(s).")
    for md_path, post in candidates:
        process_one(md_path, post)
        any_built = True
    if not any_built:
        print("No new markdown posts to build (all are already blog_built).")

if __name__ == "__main__":
    main()