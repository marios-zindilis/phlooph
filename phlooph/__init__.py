import argparse
import datetime
import inspect
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Dict
import fnmatch

from jinja2 import Environment, FileSystemLoader, Template

from phlooph.models import Source, Post
from phlooph import config


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
    argument_parser.add_argument("--skip-rendering", "-r", action="store_true", default=False)
    argument_parser.add_argument("--skip-pagination", "-p", action="store_true", default=False)
    argument_parser.add_argument("--skip-tagging", "-t", action="store_true", default=False)
    argument_parser.add_argument("--skip-feed", "-f", action="store_true", default=False)
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


def get_template(template: str) -> Template:
    file_system_loader = FileSystemLoader("templates")
    environment = Environment(loader=file_system_loader)
    return environment.get_template(template)


def get_rendered_markdown(path: Path) -> str:
    """Given the path of a source file, return it rendered as HTML."""
    template = get_template("post.html")
    post = Post(path)
    return template.render(post=post)


def get_posts_by_publication_date() -> dict:
    """
    Iterate through all posts in `POSTS_DIR` and return a dictionary where the keys are publication dates, and the
    values are lists of posts published on that date.
    """
    posts_by_publication_date = defaultdict(list)
    for post in config.POSTS_DIR.glob("**/*.md"):
        _post = Post(post)
        date_first_published = _post.date_published
        posts_by_publication_date[date_first_published].append(post)
    return posts_by_publication_date


def get_posts_by_page_number() -> Dict[datetime.date, List[Post]]:
    """Sort all posts by publication date and then bundle them in groups of POSTS_PER_PAGE."""
    posts_by_publication_date = get_posts_by_publication_date()
    publication_dates = sorted(posts_by_publication_date, reverse=True)
    pages = defaultdict(list)
    page_index = 0

    for publication_date in publication_dates:
        for post in posts_by_publication_date[publication_date]:

            if len(pages[page_index]) == config.POSTS_PER_PAGE:
                page_index += 1  # next page

            pages[page_index].append(post)

    return pages


def get_posts_for_feed() -> List[Post]:
    """Get the latest posts to be used in rendering the feed."""
    posts_by_publication_date = get_posts_by_publication_date()
    publication_dates = sorted(posts_by_publication_date, reverse=True)
    posts_for_feed = []

    for publication_date in publication_dates:
        if len(posts_for_feed) >= config.POSTS_IN_FEED:
            return posts_for_feed
        for post in posts_by_publication_date[publication_date]:
            posts_for_feed.append(Post(post))


def get_posts_by_tag() -> Dict[str, List[Path]]:
    """Return a dictionary where the keys are tags and the values are lists of posts with that tag."""
    posts_by_tag = defaultdict(list)
    for post in config.POSTS_DIR.glob("**/*.md"):
        _post = Post(post)
        tags = _post.tags
        for tag in tags:
            posts_by_tag[tag].append(post)
    return posts_by_tag


def create_page_per_tag(posts_by_tag: dict, dry_run: bool) -> None:
    """Given a dictionary of {tag: [posts]}, create one page for each tag with its posts."""
    template = get_template("tag.html")
    for tag, tagged_posts in posts_by_tag.items():
        posts = []
        for tagged_post in tagged_posts:
            post = Post(tagged_post)
            posts.append(post)

        tag_path = config.DESTINATION_DIR / "tags" / tag / "index.html"
        # now render a jinja template with the context
        if not dry_run:
            tag_path.parents[0].mkdir(parents=True, exist_ok=True)
            tag_path.write_text(template.render(posts=posts, tag=tag))


def create_tag_index(posts_by_tag: dict, dry_run: bool) -> None:
    """Given a dictionary of {tag: [posts]}, create a page with an index of all tags."""
    tags_path = config.DESTINATION_DIR / "tags" / "index.html"
    template = get_template("tags.html")
    if dry_run:
        tags_path.parents[0].mkdir(parents=True, exist_ok=True)
        tags_path.write_text(template.render(tags=posts_by_tag.keys()))


def tag(dry_run: bool) -> None:
    posts_by_tag = get_posts_by_tag()
    create_page_per_tag(posts_by_tag, dry_run)
    create_tag_index(posts_by_tag, dry_run)


def create_page_from_markdown(source: Source, dry_run: bool) -> None:
    """When we find markdown files in the source path, we render them into HTML."""
    log(f"From markdown source {source.path} creating destination {source.destination}.", 1)
    rendered_markdown = get_rendered_markdown(source.path)
    if not dry_run:
        source.mkdir()
        source.destination.write_text(rendered_markdown)


def copy_verbatim(source: Source, dry_run: bool) -> None:
    """When we find non-markdown files in the source path, we just copy them over to the destination."""
    log(f"From source file {source.path} creating destination {source.destination}.", 1)
    if not dry_run:
        source.mkdir()
        source.destination.write_bytes(source.path.read_bytes())


def is_path_ignored(path: Path) -> bool:
    """Check if a source path should be ignored from processing."""
    source = Source(path)
    for ignore_match in config.IGNORE:
        if fnmatch.fnmatch(str(source.path_relative_to_source_dir), ignore_match):
            return True
    return False


def process(path: Path, dry_run: bool) -> None:
    """Route each source file to its corresponding handler."""
    if is_path_ignored(path=path):
        log(f"Ignoring source path {path}")
        return
    source = Source(path)
    if source.is_dir:
        if not dry_run:
            log(f"From source directory {source.path} creating destination {source.destination}.", 1)
            source.mkdir()
    elif source.is_md:
        create_page_from_markdown(source, dry_run)
    else:
        copy_verbatim(source, dry_run)


def render(dry_run: bool = False) -> None:
    """Get a list of source files, and call process() for each one."""
    for path in config.SOURCE_DIR.glob("**/*"):
        process(path=path, dry_run=dry_run)


def paginate(dry_run: bool) -> None:
    posts_by_page_number = get_posts_by_page_number()
    posts_by_tag = get_posts_by_tag()
    tags = sorted(posts_by_tag.keys())
    template = get_template("page.html")

    for page, posts in posts_by_page_number.items():
        if page == 0:
            page_path = config.DESTINATION_DIR / "index.html"
            title = "Marios Zindilis"
        else:
            page_path = config.DESTINATION_DIR / "pages" / str(page) / "index.html"
            title = f"Marios Zindilis - Page {page}"

        context = []
        for post in posts:
            _post = Post(post)
            context.append(_post.context)

        # now render a jinja template with the context
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


def generate_main_feed(dry_run: bool) -> None:
    template = get_template("feed.xml")

    if not dry_run:
        config.FEED_PATH.parents[0].mkdir(parents=True, exist_ok=True)
        config.FEED_PATH.write_text(
            template.render(
                name="feed",
                last_build_date=datetime.datetime.now(),
                posts=get_posts_for_feed(),  # list of Post objects
            )
        )


def generate_feed_per_tag(dry_run: bool) -> None:
    posts_by_tag = get_posts_by_tag()
    template = get_template("feed.xml")
    for tag, posts in posts_by_tag.items():
        feed_path = config.DESTINATION_DIR / "feeds" / f"{tag}.xml"
        context = []
        for post in posts:
            _post = Post(post)
            context.append(_post)
        # now render a jinja template with the context
        if not dry_run:
            log(f"Writing feed for tag {tag} at {feed_path}", 1)
            feed_path.parents[0].mkdir(parents=True, exist_ok=True)
            feed_path.write_text(
                template.render(
                    name=tag,
                    last_build_date=datetime.datetime.now(),
                    posts=context,
                )
            )


def generate_feed_index(dry_run: bool) -> None:
    tags = sorted(get_posts_by_tag().keys())
    template = get_template("feeds.html")
    path = config.DESTINATION_DIR / "feeds" / "index.html"
    if not dry_run:
        path.parents[0].mkdir(parents=True, exist_ok=True)
        path.write_text(template.render(tags=tags))


def generate_feeds(dry_run: bool) -> None:
    generate_main_feed(dry_run)
    generate_feed_per_tag(dry_run)
    generate_feed_index(dry_run)


def main():
    args = get_args()

    setup_logging(args.verbosity)

    if args.skip_rendering:
        log("Skipping Rendering", 1)
    else:
        render(args.dry_run)

    if args.skip_pagination:
        log("Skipping Pagination", 1)
    else:
        paginate(args.dry_run)

    if args.skip_tagging:
        log("Skipping Tagging", 1)
    else:
        tag(args.dry_run)

    if args.skip_feed:
        log("Skipping Feed", 1)
    else:
        generate_feeds(args.dry_run)
