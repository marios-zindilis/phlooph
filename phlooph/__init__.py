import argparse
import datetime
import functools
import inspect
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Optional
import fnmatch

import markdown2
from jinja2 import Environment, FileSystemLoader
from ruamel.yaml import YAML

HOME = Path.home()
SOURCE_DIR = HOME / "Code" / "website-sources"
DESTINATION_DIR = HOME / "Code" / "marios-zindilis.github.io"
POSTS_DIR = SOURCE_DIR / "posts"
EXCERPT_SEPARATOR = "<!-- read more -->"  # separates the excerpt from the rest of the content
POSTS_PER_PAGE = 10  # used to paginate posts into pages
IGNORE = [  # list of files to be ignored during rendering, relative to SOURCE_DIR, passed to fnmatch.fnmatch()
    "README.md",
    "test",
    "LICENSE",
    ".git",
    ".git/*",
]

logger = logging.getLogger(__name__)


def get_args():
    argument_parser = argparse.ArgumentParser(prog="phlooph")
    argument_parser.add_argument(
        "--verbose",
        "-v",
        dest="verbosity",
        action="count",
        default=0,
        help="-v logs informational messages, -vv logs debug as well",
    )
    argument_parser.add_argument("--dry-run", "-d", action="store_true", default=False)
    return argument_parser.parse_args()


def _get_logging_level_by_verbosity(verbosity):
    if verbosity == 0:
        return logging.ERROR
    if verbosity == 1:
        return logging.INFO
    return logging.DEBUG


def setup_logging(verbosity: int = 0) -> None:
    level = _get_logging_level_by_verbosity(verbosity)
    logging.basicConfig(stream=sys.stdout, level=level)


def log(message: str, verbosity: int = 0) -> None:
    """
    Log a message. The behaviour is different depending on the verbosity:

    *   If the verbosity is not passed, the default value of 0 results in calling `logger.warning`, which essentially
        doesn"t log anything because we either set the log level to `INFO` or `DEBUG` in `setup_logging`.
    *   If the verbosity is 1, this calls `logger.info`.
    *   If the verbosity is 2, this calls `logger.debug`.
    *   If the verbosity is equal to or greater than 3, this still calls `logger.DEBUG`, but the calling function is
        logged as well.
    """
    if verbosity == 0:
        logger.warning(message)
    elif verbosity == 1:
        logger.info(message)

    calling_function = f"[{inspect.stack()[1].function}] " if verbosity >= 3 else ""
    logger.debug(f"{calling_function}{message}")


@functools.lru_cache(maxsize=512)  # don"t read from disk twice for the same source
def get_source_lines(source) -> List[str]:
    """
    Given the path of a source file, return its contents as a list of lines.
    """
    text = source.read_text()
    return text.splitlines()


def get_front_matter_text(source: Path) -> str:
    """
    Given the path of a source file, return the part of the text that is the front matter.
    """
    lines = get_source_lines(source)
    line_is_front_matter = False
    front_matter = []
    for line in lines:
        line = line.strip()
        if line == "---" and not line_is_front_matter:
            line_is_front_matter = True
            continue
        if line != "---" and line_is_front_matter:
            front_matter.append(line)
        if line == "---" and line_is_front_matter:
            break
    return "\n".join(front_matter)


def get_front_matter(source) -> dict:
    """
    Given the path of a source file, return its front matter as a dictionary.
    """
    front_matter_lines = get_front_matter_text(source)
    yaml = YAML()
    return yaml.load(front_matter_lines)


def get_source_text_excluding_front_matter(source: Path) -> str:
    """
    Return the part of the source file excluding the front matter, to be used for rendering.
    """
    lines = get_source_lines(source)
    lines_excluding_front_matter = []
    line_is_front_matter = False
    for line in lines:
        stripped_line = line.strip()
        if stripped_line == "---" and not line_is_front_matter:
            line_is_front_matter = True
            continue
        if stripped_line != "---" and line_is_front_matter:
            continue
        if stripped_line == "---" and line_is_front_matter:
            line_is_front_matter = False
            continue
        lines_excluding_front_matter.append(line)
    return "\n".join(lines_excluding_front_matter)


def get_post_excerpt(source: Path) -> str:
    """
    Given the path of a source file, get its exceprt, i.e. the text before the EXCERPT_SEPARATOR string.
    """
    source_text_excluding_front_matter = get_source_text_excluding_front_matter(source)

    if EXCERPT_SEPARATOR in source_text_excluding_front_matter:
        # return the text from the beginning until the position of the EXCERPT_SEPARATOR:
        separator_position = source_text_excluding_front_matter.find(EXCERPT_SEPARATOR)
        return source_text_excluding_front_matter[:separator_position]


def get_title(source: Path) -> str:
    """Given the path of a source file, get its title from the front matter."""
    front_matter = get_front_matter(source)
    return front_matter.get("title", None)


def get_rendered_markdown(source: Path) -> str:
    """Given the path of a source file, return it rendered as HTML."""
    file_system_loader = FileSystemLoader("templates")
    environment = Environment(loader=file_system_loader)
    template = environment.get_template("post.html")
    text = get_source_text_excluding_front_matter(source)
    title = get_title(source)
    return template.render(
        content=markdown2.markdown(text, extras=["fenced-code-blocks"]),
        title=title,
        date_published=get_date_published(source),
        tags=sorted(get_posts_by_tag().keys()),
    )


def get_date_published(source) -> datetime.datetime:
    """Get the date on which a page was first published."""
    front_matter = get_front_matter(source)
    return front_matter.get("first-published", None)


def get_tags(source):
    """Given the path of a source files, returns its tags from the front matter."""
    front_matter = get_front_matter(source)
    tags = []
    for tag in front_matter.get("tags", []):
        tags.append(tag.lower().replace(" ", "-"))  # e.g "Django Rest Framework" -> "django-rest-framework"
    return tags


def get_url(source: Path) -> str:
    """Given the path of a source file, return its relative URL."""
    source_path_relative_to_source_dir = get_source_path_relative_to_source_dir(source)
    url_parts = str(source_path_relative_to_source_dir).split("/")[:-1]
    url = "/".join(url_parts)
    return f"/{url}/"


def get_source_path_relative_to_source_dir(source: Path) -> Path:
    """Return the part of the source that is relative to the SOURCE_DIR. For example, assuming that SOURCE_DIR is
    `~/Code/website-sources/`, then for this source file:

        ~/Code/website-sources/docs/more-docs/even-more-docs/file.txt

    ...the part that is relative to SOURCE_DIR is:

        docs/more-docs/even-more-docs/file.txt
    """
    source_parts_after_source_dir = source.parts[len(SOURCE_DIR.parts) :]  # noqa: E203
    source_path_after_source_dir = "/".join(source_parts_after_source_dir)
    return Path(source_path_after_source_dir)


def get_posts_by_publication_date() -> dict:
    """
    Iterate through all posts in `POSTS_DIR` and return a dictionary where the keys are publication dates, and the
    values are lists of posts published on that date.
    """
    posts_by_publication_date = defaultdict(list)
    for post in POSTS_DIR.glob("**/*.md"):
        date_first_published = get_date_published(post)
        posts_by_publication_date[date_first_published].append(post)
    return posts_by_publication_date


def get_posts_by_page_number():
    """Sort all posts by publication date and then bundle them in groups of POSTS_PER_PAGE."""
    posts_by_publication_date = get_posts_by_publication_date()
    publication_dates = sorted(posts_by_publication_date, reverse=True)
    pages = defaultdict(list)
    page_index = 0

    for publication_date in publication_dates:
        for post in posts_by_publication_date[publication_date]:

            if len(pages[page_index]) == POSTS_PER_PAGE:
                page_index += 1  # next page

            pages[page_index].append(post)

    return pages


def get_destination(source: Path) -> Path:
    """Given the path of a source file, return the destination path."""
    source_path_relative_to_source_dir = get_source_path_relative_to_source_dir(source)
    destination_path = DESTINATION_DIR / source_path_relative_to_source_dir
    if source.match("*.md"):
        return destination_path.with_name("index.html")
    return destination_path


def get_post_image(source: Path) -> Optional[str]:
    """Given the path of a source file, return its associated image, if one exists."""
    source_directory = source.parents[0]
    for image_file in ("index.jpg", "index.jpeg", "index.png"):
        image_path = source_directory / image_file
        if image_path.is_file():
            return str(image_path)


def get_posts_by_tag() -> dict:
    """Return a dictionary where the keys are tags and the values are lists of posts with that tag."""
    posts_by_tag = defaultdict(list)
    for post in POSTS_DIR.glob("**/*.md"):
        tags = get_tags(post)
        for tag in tags:
            posts_by_tag[tag].append(post)
    return posts_by_tag


def create_page_per_tag(posts_by_tag: dict, dry_run: bool) -> None:
    """Given a dictionary of {tag: [posts]}, create one page for each tag with its posts."""
    for tag, tagged_posts in posts_by_tag.items():
        posts = []
        for tagged_post in tagged_posts:
            posts.append({"title": get_title(tagged_post), "url": get_url(tagged_post)})

        tag_path = DESTINATION_DIR / "tags" / tag / "index.html"
        # now render a jinja template with the context
        file_system_loader = FileSystemLoader("templates")
        environment = Environment(loader=file_system_loader)
        template = environment.get_template("tag.html")
        if not dry_run:
            tag_path.parents[0].mkdir(parents=True, exist_ok=True)
            tag_path.write_text(template.render(posts=posts, tag=tag))


def create_tag_index(posts_by_tag: dict, dry_run: bool) -> None:
    """Given a dictionary of {tag: [posts]}, create a page with an index of all tags."""
    tags_path = DESTINATION_DIR / "tags" / "index.html"
    file_system_loader = FileSystemLoader("templates")
    environment = Environment(loader=file_system_loader)
    template = environment.get_template("tags.html")
    if dry_run:
        tags_path.parents[0].mkdir(parents=True, exist_ok=True)
        tags_path.write_text(template.render(tags=posts_by_tag.keys()))


def tag(dry_run: bool) -> None:
    posts_by_tag = get_posts_by_tag()
    create_page_per_tag(posts_by_tag, dry_run)
    create_tag_index(posts_by_tag, dry_run)


def create_directory(source: Path, destination: Path, dry_run: bool) -> None:
    """When we find directories in the source path, we simply created them in the destination path."""
    log(f"From source directory {source} creating destination {destination}.", 1)
    if not dry_run:
        destination.mkdir(parents=True, exist_ok=True)


def create_page_from_markdown(source: Path, destination: Path, dry_run: bool) -> None:
    """What we find markdown files in the source path, we render them into HTML."""
    log(f"From markdown source {source} creating destination {destination}.", 1)
    rendered_markdown = get_rendered_markdown(source)
    if not dry_run:
        destination.parents[0].mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered_markdown)


def copy_verbatim(source: Path, destination: Path, dry_run: bool) -> None:
    """When we find non-markdown files in the source path, we just copy them over to the destination."""
    log(f"From source file {source} creating destination {destination}.", 1)
    if not dry_run:
        destination.write_bytes(source.read_bytes())


def is_source_ignored(source: Path) -> bool:
    """Check if a source path should be ignored from processing."""
    source_path_relative_to_source_dir = get_source_path_relative_to_source_dir(source)
    for ignore_match in IGNORE:
        if fnmatch.fnmatch(str(source_path_relative_to_source_dir), ignore_match):
            return True
    return False


def process(source: Path, dry_run: bool) -> None:
    """Route each source file to its corresponding handler."""
    if is_source_ignored(source):
        log(f"Ignoring source {source}")
        return
    destination = get_destination(source)
    if source.is_dir():
        create_directory(source, destination, dry_run)
    elif source.match("*.md"):
        create_page_from_markdown(source, destination, dry_run)
    else:
        copy_verbatim(source, destination, dry_run)


def render(dry_run: bool = False) -> None:
    """Get a list of source files, and call process() for each one."""
    for source in SOURCE_DIR.glob("**/*"):
        process(source=source, dry_run=dry_run)


def paginate(dry_run: bool) -> None:
    posts_by_page_number = get_posts_by_page_number()
    posts_by_tag = get_posts_by_tag()
    tags = sorted(posts_by_tag.keys())

    for page, posts in posts_by_page_number.items():
        if page == 0:
            page_path = DESTINATION_DIR / "index.html"
            title = "Marios Zindilis"
        else:
            page_path = DESTINATION_DIR / "pages" / str(page) / "index.html"
            title = f"Marios Zindilis - Page {page}"

        context = []
        for post in posts:
            text = get_source_text_excluding_front_matter(post)
            excerpt = get_post_excerpt(post)
            context.append(
                {
                    "title": get_title(post),
                    "date_published": get_date_published(post),
                    "content": markdown2.markdown(text, extras=["fenced-code-blocks"]),
                    "url": get_url(post),
                    "excerpt": markdown2.markdown(excerpt) if excerpt else None,
                    "image": get_post_image(post),
                    "tags": get_tags(post),
                }
            )

        # now render a jinja template with the context
        file_system_loader = FileSystemLoader("templates")
        environment = Environment(loader=file_system_loader)
        template = environment.get_template("page.html")

        if not dry_run:
            page_path.parents[0].mkdir(parents=True, exist_ok=True)
            page_path.write_text(
                template.render(
                    posts=context,
                    current_page=page,
                    pages=posts_by_page_number.keys(),
                    tags=tags,
                    title=title,
                )
            )


def main():
    args = get_args()

    setup_logging(args.verbosity)

    render(args.dry_run)
    paginate(args.dry_run)
    tag(args.dry_run)
