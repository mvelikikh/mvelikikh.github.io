"""Custom hooks."""

from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml
from mkdocs.exceptions import ConfigurationError

ALLOWED_TAGS = set()


def on_config(config, **kwargs):
    """Call on build."""
    config.copyright = f"&copy; 2014-{datetime.now().year} Великих М.А."
    _load_user_config()


def _load_user_config():
    global ALLOWED_TAGS
    user_config_file = Path(__file__).parents[0] / "config" / "config.yml"
    with open(user_config_file, "r") as stream:
        user_config = yaml.load(stream, Loader=yaml.FullLoader)
        tags = user_config["plugins"]["tags"]["tags_allowed"]
        ALLOWED_TAGS = set(
            next(iter(tag.keys())) if isinstance(tag, dict) else tag for tag in tags
        )


def _is_blog_post(page):
    return Path(page.file.src_uri).parents[0] == Path("blog/posts")


def _validate_categories(page, categories):
    if not _is_blog_post(page):
        return

    if not categories:
        raise ConfigurationError("Blog post must have a category")


def _get_first_non_empty_line(content):
    in_frontmatter = False
    in_page_content = False
    frontmatter_separator = "---"
    for line in content.split("\n"):
        if not in_frontmatter and line.startswith(frontmatter_separator):
            in_frontmatter = True
            continue
        if (
            in_frontmatter
            and line.startswith(frontmatter_separator)
            and not in_page_content
        ):
            in_frontmatter = False
            in_page_content = True
            continue
        if in_page_content and line:
            return line


def _validate_blog_post_header(content):
    header_suffix = "#"
    first_line = _get_first_non_empty_line(content)
    if not first_line or not first_line.startswith(header_suffix):
        raise ConfigurationError("The blog post must start with a level 1 header")
    header_level = len(first_line) - len(first_line.lstrip(header_suffix))
    if header_level != 1:
        raise ConfigurationError(
            "The first header must be level 1 header. "
            f"Found level {header_level} header: {first_line}"
        )


def _validate_content(page):
    if not _is_blog_post(page):
        return

    content = page.file.content_string
    if "<!-- more -->" not in content:
        raise ConfigurationError(
            "Blog post must have an excerpt separator <!-- more -->"
        )

    _validate_blog_post_header(content)


def _validate_description(page, description):
    if not _is_blog_post(page):
        return

    if not description:
        raise ConfigurationError("Blog post must have a description")

    if description.endswith("\n"):
        raise ConfigurationError("The description must not end with a newline")


def _validate_tags(page, tags):
    if not tags:
        if not _is_blog_post(page):
            return
        else:
            raise ConfigurationError("Empty tag list for a blog post")

    tags_set = set(tags)
    if not tags_set.issubset(ALLOWED_TAGS):
        raise ConfigurationError(f"Non-allowed tags found: {tags_set - ALLOWED_TAGS}")

    if len(tags_set) != len(tags):
        duplicates = [item for item, count in Counter(tags).items() if count > 1]
        raise ConfigurationError(f"Duplicate tags found: {duplicates}")

    if tags != sorted(tags):
        raise ConfigurationError(f"Tags should be sorted: {tags=}")


def on_page_markdown(markdown, page, config, files):
    """Call after the page's markdown is loaded from a file."""
    _validate_categories(page, page.meta.get("categories"))
    _validate_description(page, page.meta.get("description"))
    _validate_tags(page, page.meta.get("tags"))

    _validate_content(page)
