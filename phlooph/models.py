import functools
from pathlib import Path
from typing import List, Union
from ruamel.yaml import YAML
import datetime
import markdown2

from phlooph import config


class Source:
    """Represents a source that can be either a directory or a file."""

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)

    @property
    def path_relative_to_source_dir(self) -> Path:
        """Return the part of the path that is relative to the `SOURCE_DIR`. For example, assuming that `SOURCE_DIR` is
        `~/Code/website-sources/`, then for this source file:

            ~/Code/website-sources/docs/more-docs/even-more-docs/file.txt

        ...the part that is relative to `SOURCE_DIR` is:

            docs/more-docs/even-more-docs/file.txt
        """
        path_parts = self.path.parts
        source_dir_parts = config.SOURCE_DIR.parts

        source_parts_after_source_dir = path_parts[len(source_dir_parts) :]  # noqa: E203
        source_path_after_source_dir = "/".join(source_parts_after_source_dir)
        return Path(source_path_after_source_dir)

    @property
    def is_dir(self) -> bool:
        return self.path.is_dir()

    @property
    def is_md(self) -> bool:
        return self.path.match("*.md")

    @property
    def destination(self):
        _destination = config.DESTINATION_DIR / self.path_relative_to_source_dir
        if self.is_md:
            return _destination.with_name("index.html")
        return _destination


class Post(Source):
    """Represents a blog post, written in Markdown."""

    @functools.lru_cache(maxsize=512)  # don"t read from disk twice for the same source
    def _get_lines(self):
        text = self.path.read_text()
        return text.splitlines()

    @property
    def lines(self) -> List[str]:
        """Return the contents of a post as a list of lines."""
        return self._get_lines()

    def _get_front_matter_text(self) -> str:
        """Return the front matter of a post as a string."""
        line_is_front_matter = False
        front_matter_lines = []
        for line in self.lines:
            line = line.strip()
            if line == "---" and not line_is_front_matter:
                line_is_front_matter = True
                continue
            if line != "---" and line_is_front_matter:
                front_matter_lines.append(line)
            if line == "---" and line_is_front_matter:
                break
        return "\n".join(front_matter_lines)

    @property
    def front_matter(self) -> dict:
        """Return the front matter of a post as a dictionary."""
        yaml = YAML()
        return yaml.load(self._get_front_matter_text())

    @property
    def title(self) -> str:
        """
        Return the post title from the front matter.

        :raises: `IndexError` if there is no title.
        """
        return self.front_matter["title"]

    @property
    def tags(self) -> List[str]:
        _tags = []
        for tag in self.front_matter.get("tags", []):
            _tags.append(tag.lower().replace(" ", "-"))  # e.g "Django Rest Framework" -> "django-rest-framework"
        return _tags

    @property
    def date_published(self) -> datetime.date:
        """
        Return the date that a post was first published.

        :raises: `IndexError` if there is no first publication date.
        """
        return self.front_matter["first-published"]

    @property
    def text(self) -> str:
        """
        Return the main text of a Post, excluding the front matter. This will be used for rendering.
        """
        lines_excluding_front_matter = []
        line_is_front_matter = False
        for line in self.lines:
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

    @property
    def excerpt(self) -> Union[str, None]:
        """
        Return the post exceprt (i.e. the text before the `EXCERPT_SEPARATOR` string) rendered as HTML.

        :return: The excerpt if there is one, otherwise `None`.
        """
        if config.EXCERPT_SEPARATOR not in self.text:
            return None

        # return the text from the beginning until the position of the EXCERPT_SEPARATOR:
        separator_position = self.text.find(config.EXCERPT_SEPARATOR)
        _excerpt = self.text[:separator_position]
        return markdown2.markdown(_excerpt, extras=["fenced-code-blocks"])

    @property
    def relative_url(self) -> str:
        url_parts = str(self.path_relative_to_source_dir).split("/")[:-1]  # e.g. ["posts", "some-post"]
        url = "/".join(url_parts)
        return f"/{url}/"

    @property
    def html(self) -> str:
        """Return the post's Markdown text, rendered as HTML."""
        return markdown2.markdown(self.text, extras=["fenced-code-blocks"])
