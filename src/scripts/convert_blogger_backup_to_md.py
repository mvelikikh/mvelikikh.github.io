"""Convert Blogger's backup to MkDocs material posts.

Restrictions:
    - svg files are processed as images - embedded scripts are not supported.
      For example: ![](../assets/images/test2.svg)
"""

import argparse
import csv
import inspect
import logging
import os.path
import re
import sys
import traceback
import urllib.request
import xml.etree.ElementTree as ElementTree
from collections import namedtuple
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import yaml
from bs4 import BeautifulSoup
from jinja2 import Template

BLOGGER_BACKUP = Path(__file__).parents[0] / "files" / "blogger_backup.xml"
POST_OVERRIDE_PATH = Path(__file__).parents[0] / "files" / "post_meta_override.yml"
POST_OVERRIDE = yaml.load(open(POST_OVERRIDE_PATH), Loader=yaml.FullLoader)
CUTOFF_DATE = datetime(2024, 8, 1)
OUTPUT_DIR = "posts"
SUMMARY_FILE = "summary.csv"
SUMMARY = os.path.join(OUTPUT_DIR, SUMMARY_FILE)
SUMMARY_COLS = ["title", "published", "categories", "tags", "draft"]
IMAGE_DIR = os.path.join(OUTPUT_DIR, "%(filename_noext)s")
MARKDOWN_IMAGE_PATH = "%(filename_noext)s"
NS = "http://www.w3.org/2005/Atom"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
CUSTOM_ATTR_PREFIX = "custom"
COLLAPSIBLE_ATTR = "%s-collapsible" % (CUSTOM_ATTR_PREFIX)
COLLAPSIBLE_ATTR_SUMMARY = "%s-collapsible-summary" % (CUSTOM_ATTR_PREFIX)
ctx = {}
in_table = False
table_row = 0
table_headers = 0
in_ol = False

LOGGER = logging.getLogger(__name__)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] [%(funcName)s] %(message)s",
    level=logging.INFO,
)


def escape_markdown(s):
    """Escape text in markdown."""
    return s.replace("_", "\\_")


#    return (
#        s.replace("#", "\\#")
#        .replace("_", "\\_")
#        .replace("{", "\\{")
#        .replace("}", "\\}")
#        .replace("[", "\\[")
#        .replace("]", "\\]")
#        .replace("-", "\\-")
#        .replace("!", "\\!")
#        .replace("(", "\\(")
#        .replace(")", "\\)")
#        .replace("+", "\\+")
#        .replace("*", "\\*")
#    )


def get_and_create_image_dir():
    """Get and create image directory."""
    image_dir = IMAGE_DIR % ctx
    Path(image_dir).mkdir(exist_ok=True)
    return image_dir


def save_image(url):
    """Save image locally."""
    file_name = os.path.basename(url)
    urllib.request.urlretrieve(url, os.path.join(get_and_create_image_dir(), file_name))


def get_language(data):
    """Determine code block language for highlighting."""
    if "select" in data.lower() or "sql" in data.lower():
        return "sql"


class TagHandler:
    """Generic HTML tag handler."""

    escape_markdown = True

    def __init__(self, attrs):
        self.attrs = dict(attrs)

    def handle_starttag(self):
        raise NotImplementedError()

    def handle_endtag(self):
        raise NotImplementedError()

    def handle_data(self, data):
        LOGGER.debug(data)
        if self.escape_markdown:
            return escape_markdown(data)
        else:
            return data


class HHandler(TagHandler):
    how_many = 0

    def handle_starttag(self):
        return "\n" + "#" * self.how_many + " "

    def handle_endtag(self):
        return "\n"


class OpenCloseHandler(TagHandler):
    markdown = ""

    def handle_starttag(self):
        return self.markdown

    def handle_endtag(self):
        return self.markdown


class OpenHandler(TagHandler):
    markdown = ""

    def handle_starttag(self):
        return self.markdown

    def handle_endtag(self):
        return ""


class SkipHandler(TagHandler):
    def handle_starttag(self):
        return ""

    def handle_endtag(self):
        return ""

    def handle_data(self, data):
        return ""


class AHandler(TagHandler):
    def __init__(self, attrs):
        super().__init__(attrs)
        self.has_href = "href" in self.attrs
        if self.has_href and self.attrs["href"].startswith("support.oracle.com"):
            self.attrs["href"] = "https://" + self.attrs["href"]

        self.relative_link = (
            self.attrs["href"].startswith(("/", "<$BlogURL$>"))
            if self.has_href
            else False
        )
        self.skip = (
            self.attrs["href"].startswith("https://blogger") if self.has_href else False
        )
        LOGGER.debug(self.attrs["href"] if self.has_href else "no href")
        self.text = ""

    def handle_starttag(self):
        if self.has_href:
            if not self.skip:
                return "["
            else:
                return ""
        else:
            attrs_string = " ".join([f"{k}='{v}'" for k, v in self.attrs.items()])
            return f"<a {attrs_string}>"

    def handle_endtag(self):
        if self.has_href:
            if not self.skip:
                if self.relative_link:
                    return f"]({get_output_file_name(self.text)})"
                else:
                    return f"]({self.attrs['href']})"
            else:
                return ""
        else:
            return "</a>"

    def handle_data(self, data):
        if self.skip:
            return ""
        self.text = data
        return escape_markdown(data)


class BHandler(OpenCloseHandler):
    markdown = "**"


class BLOCKQUOTEHandler(TagHandler):
    def handle_starttag(self):
        return ""

    def handle_endtag(self):
        return ""

    def handle_data(self, data):
        return "> " + super().handle_data(data)


class BRHandler(OpenHandler):
    markdown = "\n"


class CODEHandler(OpenCloseHandler):
    markdown = "`"
    escape_markdown = False


class DIVHandler(OpenCloseHandler):
    markdown = ""


class H1Handler(HHandler):
    how_many = 1


class H2Handler(HHandler):
    how_many = 2


class H3Handler(HHandler):
    how_many = 3


class H4Handler(HHandler):
    how_many = 4


class IMGHandler(TagHandler):
    def handle_starttag(self):
        src = self.attrs["src"]
        if src.startswith("http"):
            save_image(src)
        image_path = Path(
            os.path.join(MARKDOWN_IMAGE_PATH % ctx, os.path.basename(src))
        ).as_posix()
        return f"![]({image_path})"

    def handle_endtag(self):
        return ""


class IHandler(OpenCloseHandler):
    markdown = "*"


class LIHandler(TagHandler):
    def handle_starttag(self):
        global in_ol
        if in_ol:
            return "1. "
        else:
            return "- "

    def handle_endtag(self):
        return "\n"


class OLHandler(TagHandler):
    def handle_starttag(self):
        global in_ol
        in_ol = True
        return ""

    def handle_endtag(self):
        global in_ol
        in_ol = False
        return ""


class TABLEHandler(TagHandler):
    def handle_starttag(self):
        global in_table
        in_table = True
        return ""

    def handle_endtag(self):
        global in_table
        global table_row
        in_table = False
        table_row = 0
        return "\n"


class TBODYHandler(SkipHandler):
    pass


class TRHandler(TagHandler):
    def handle_starttag(self):
        global table_row, table_headers
        table_row += 1
        if table_row == 2:
            output = "| - " * table_headers + "|\n"
            table_headers = 0
            return output
        else:
            return ""

    def handle_endtag(self):
        return "|\n"


class TTHandler(OpenCloseHandler):
    markdown = "`"


class UHandler(OpenCloseHandler):
    markdown = "^^"


class TDHandler(OpenHandler):
    markdown = "|"


class THHandler(OpenHandler):
    markdown = "|"

    def handle_starttag(self):
        global table_headers
        table_headers += 1
        return super().handle_starttag()


class PHandler(OpenCloseHandler):
    markdown = ""


class PREHandler(TagHandler):
    first_data_block = True
    collapsible = None
    indent = ""

    def handle_starttag(self):
        self.collapsible = self.attrs.get(COLLAPSIBLE_ATTR) == "true"
        LOGGER.debug(f"{self.collapsible=}")
        output = ""
        if self.collapsible:
            self.indent = " " * 4
            output += "\n??? %s\n%s```" % (
                self.attrs[COLLAPSIBLE_ATTR_SUMMARY],
                self.indent,
            )
        else:
            output = "\n```"
        return output

    def handle_endtag(self):
        if self.collapsible:
            return "\n%s```\n\n" % (self.indent)
        else:
            return "\n```\n\n"

    def get_code_attributes(self, data):
        language = get_language(data)
        output = ""
        if language:
            output += language
        if "class" in self.attrs and "highlight" in self.attrs["class"]:
            code_attrs = dict(
                v.strip().split(":") for v in self.attrs["class"].split(";") if v
            )
            highlight_lines = (
                code_attrs["highlight"]
                .replace("[", "")
                .replace("]", "")
                .replace(",", " ")
                .strip()
            )
            output += f' hl_lines="{highlight_lines}"'
        return output

    def handle_data(self, data):
        output = ""
        if self.first_data_block:
            output += self.get_code_attributes(data) + "\n"
            self.first_data_block = False

        if self.collapsible:
            LOGGER.debug(f"{self.collapsible=}")
            output += "\n".join([self.indent + line for line in data.split("\n")])
        else:
            output += data
        return output


class StrongHandler(OpenCloseHandler):
    markdown = "**"


class StyleHandler(SkipHandler):
    pass


class ULHandler(OpenCloseHandler):
    markdown = ""


TAG_HANDLERS = {}


def load_tag_handlers():
    """Load tag handlers dynamically."""
    for name, obj in inspect.getmembers(sys.modules[__name__]):
        if inspect.isclass(obj):
            if name.endswith("Handler"):
                tag = name[:-7].lower()
                TAG_HANDLERS[tag] = obj
            LOGGER.debug(name)
            LOGGER.debug(obj)


class HTMLToMarkdownParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.markdown = ""
        self.handlers = []

    def handle_starttag(self, tag, attrs):
        LOGGER.debug(f"Start tag: {tag} {attrs}")
        handler = TAG_HANDLERS[tag](attrs)
        self.handlers.append(handler)
        self.markdown += self.handler.handle_starttag()

    def handle_endtag(self, tag):
        LOGGER.debug(f"End tag  {tag}")
        LOGGER.debug(self.handler)
        self.markdown += self.handler.handle_endtag()
        self.handlers.pop()

    def handle_data(self, data):
        self.markdown += self.handler.handle_data(data)

    @property
    def handler(self):
        return self.handlers[-1] if self.handlers else TagHandler([])


def convert_html_to_markdown(html):
    """HTML to markdown conversion."""
    parser = HTMLToMarkdownParser()
    parser.feed(html)
    return parser.markdown


def get_output_file_name_noext(title):
    """Get output file name without extension."""
    file_name = get_output_file_name(title)
    file_name_noext = Path(file_name).stem
    return file_name_noext


def get_output_file_name(title):
    """Construct output file name from post's title."""
    file_name = (
        title.replace(" ", "-")
        .replace("$", "")
        .replace("(", "")
        .replace(")", "")
        .replace("*", "")
        .replace(",", "")
        .replace("/", "")
        .replace(":", "")
        .replace("[", "")
        .replace("]", "")
        .replace('"', "")
        .lower()
        + ".md"
    )
    file_name = re.sub(r"-+", "-", file_name)
    return file_name


def render_post(data):
    """Create an MkDocs post from markdown."""
    template = Template(
        """---
{% if categories %}
categories:
{%   for category in categories %}
  - {{ category }}
{%   endfor %}
{% endif %}
date:
  created: {{ created }}
{% if updated %}
  updated: {{ updated }}
{% endif %}
{% if draft %}
draft: true
{% endif %}
{% if tags %}
tags:
{%   for tag in tags %}
  - {{ tag }}
{%   endfor %}
{% endif %}
title: "{{ title }}"
---

# {{ title }}

{{ content }}
""",
        trim_blocks=True,
    )
    tags = data.get("tags")
    return template.render(
        categories=sorted(data["categories"]),
        created=data["published"].strftime(DATE_FORMAT),
        updated=data["updated"].strftime(DATE_FORMAT) if "updated" in data else None,
        draft=data.get("draft", False),
        tags=sorted(tags) if tags else None,
        title=data["title"].replace('"', '\\"'),
        content=data["markdown"],
    )


def save_svg(svg, file_name):
    """Save svg data to file."""
    with open(os.path.join(get_and_create_image_dir(), file_name), "w") as fd:
        fd.write(svg)


def replace_svg_with_img(html, title):
    """Change SVG tags with the equivalent IMG tags."""
    soup = BeautifulSoup(html, "html.parser")
    img_counter = 0
    for svg in soup.findAll("svg"):
        img_counter += 1
        filename_noext = get_output_file_name_noext(title)
        svg_file_name = f"{filename_noext}-{img_counter}.svg"
        save_svg(str(svg), svg_file_name)
        img_tag = soup.new_tag("img", src=svg_file_name)
        svg.replace_with(img_tag)
        LOGGER.debug("replaced svg tag")
    return str(soup)


def replace_collapsible(html):
    """Collapsible sections are replaced for further processing."""
    soup = BeautifulSoup(html, "html.parser")
    for div in soup.find_all("div"):
        LOGGER.debug(div)
        if div.input and div.input["value"] == "Show":
            nested_div = div.div
            LOGGER.debug("found")
            if nested_div is not None:
                LOGGER.debug(nested_div)
                children = nested_div.findChildren()
                if len(children) > 1:
                    raise ValueError("Unexpected child length")
                first_child = children[0]
                child_name = first_child.name
                if child_name != "pre":
                    raise ValueError("Unexpected child name: %r" % (child_name))
                first_child[COLLAPSIBLE_ATTR] = "true"
                first_child[COLLAPSIBLE_ATTR_SUMMARY] = "Show"
                div.replace_with(first_child)
                LOGGER.debug("replaced")
    LOGGER.debug(str(soup))
    return str(soup)


def get_custom_categories(title):
    """Get categories for a post."""
    if "categories" in POST_OVERRIDE["posts"][title]:
        return POST_OVERRIDE["posts"][title]["categories"]
    else:
        return POST_OVERRIDE["posts"]["default"]["categories"]


def get_custom_tags(title):
    """Use overriding tags if available."""
    if title in POST_OVERRIDE["posts"]:
        return POST_OVERRIDE["posts"][title]["tags"]


def convert_post_to_md(entry):
    """Convert Blogger post to markdown."""
    app_ns = "http://purl.org/atom/app#"
    data = {}
    for attr in ["published", "updated", "title"]:
        data[attr] = entry.find(f"{{{NS}}}{attr}").text
    for attr in ["published", "updated"]:
        data[attr] = datetime.strptime(data[attr][:19], DATE_FORMAT)
    if data["updated"] > CUTOFF_DATE:
        data.pop("updated")
    if "updated" in data:
        time_diff = data["updated"] - data["published"]
        if time_diff.total_seconds() < 86400:
            data.pop("updated")
    data["categories"] = get_custom_categories(data["title"])
    if tags := get_custom_tags(data["title"]):
        data["tags"] = tags
    else:
        for c in entry.findall(
            f"{{{NS}}}category[@scheme='http://www.blogger.com/atom/ns#']"
        ):
            if not data.get("tags"):
                data["tags"] = set()
            data["tags"].add(c.get("term"))
    draft = entry.find("control/draft", namespaces={"": app_ns})
    if draft is not None and draft.text == "yes":
        data["draft"] = True
    content = entry.find(f"{{{NS}}}content").text
    content = replace_svg_with_img(content, data["title"])
    content = replace_collapsible(content)
    data["markdown"] = convert_html_to_markdown(content)
    # this is unsafe because of the code blocks and hl_lines
    # data["markdown"] = re.sub("\n{2,}", "\n\n", data["markdown"]).rstrip()
    data["markdown"] = data["markdown"].rstrip()
    if "```" not in data["markdown"]:
        data["markdown"] = re.sub("\n{2,}", "\n\n", data["markdown"])
    LOGGER.debug(data)
    LOGGER.debug(data["markdown"])
    output_file_name = get_output_file_name(data["title"])
    LOGGER.debug(f"{output_file_name=}")
    with open(
        os.path.join(OUTPUT_DIR, output_file_name),
        mode="w",
        encoding="utf-8",
        newline="\n",
    ) as fd:
        fd.write(render_post(data))
    return data


def get_entry_type(e):
    """Determine Blogger entry type."""
    c = e.find(f"{{{NS}}}category[@scheme='http://schemas.google.com/g/2005#kind']")
    if c is not None:
        return c.get("term").split("#")[-1]

    raise ValueError(
        "Couldn't find the entry type (blogger setting/blogger comment/blogger post)"
    )


def create_output_dir():
    """Create output directory."""
    Path(OUTPUT_DIR).mkdir(exist_ok=True)


def set_global_context(title):
    """Set global context variable to be used in other functions."""
    ctx["title"] = title
    ctx["filename_noext"] = get_output_file_name_noext(title)


def write_summary(posts):
    """Generate summary report."""
    with open(SUMMARY, "w", newline="\n", encoding="utf-8") as fd:
        writer = csv.DictWriter(fd, fieldnames=SUMMARY_COLS)
        writer.writeheader()
        for post in sorted(posts, key=lambda p: (p.published, p.title)):
            writer.writerow(post._asdict())
    LOGGER.info(f"Summary report: {SUMMARY}")


def convert_blogger_backup_to_md(backup_file, summary):
    """Convert Blogger backup to MkDocs material markdown."""
    root = ElementTree.parse(backup_file).getroot()
    PostMeta = namedtuple("PostMeta", SUMMARY_COLS)
    posts = []
    for entry in root.findall(f"{{{NS}}}entry"):
        type_ = get_entry_type(entry)
        if type_ == "post":
            title = entry.find(f"{{{NS}}}title").text
            LOGGER.info(f"Processing post: {title}")
            set_global_context(title)
            post_data = convert_post_to_md(entry)
            if summary:
                post_meta = PostMeta(
                    post_data["title"],
                    post_data["published"],
                    ", ".join(sorted(post_data.get("categories", ""))),
                    ", ".join(sorted(post_data.get("tags", ""))),
                    post_data.get("draft"),
                )
                posts.append(post_meta)
        else:
            LOGGER.debug(f"Skipping {type_}")
    if summary:
        write_summary(posts)


def cli_main():
    """Command line entry point."""
    try:
        parser = argparse.ArgumentParser(
            prog="convert-blogger-backup-to-md", description=__doc__
        )
        parser.add_argument(
            "file",
            help="Blogger backup file",
            default=BLOGGER_BACKUP,
            nargs="?",
        )
        parser.add_argument(
            "--without-summary",
            help=f"Do not generate summary report {SUMMARY_FILE}",
            dest="summary",
            action="store_false",
        )
        args = parser.parse_args()
        load_tag_handlers()
        create_output_dir()
        convert_blogger_backup_to_md(args.file, args.summary)
        return 0
    except Exception:
        sys.stderr.write(traceback.format_exc())
        return 255


if __name__ == "__main__":
    sys.exit(cli_main())
