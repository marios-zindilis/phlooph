import pytest
import unittest
from unittest import mock
import sys
from pathlib import Path, PosixPath, WindowsPath
import datetime

from phlooph.models import Source, Post


FAKE_POST = """---
title: Fake Post Title
first-published: 2020-12-17
tags:
- Fake Tag 1
- Fake Tag 2
---

This is the post excerpt.

<!-- read more -->

This is the post content.
"""

FAKE_POST_TEXT = (
    "---\ntitle: Fake Post Title\nfirst-published: 2020-12-17\ntags:\n- Fake Tag 1\n- Fake Tag 2\n---\n\nThis is the "
    "post excerpt.\n\n<!-- read more -->\n\nThis is the post content."
)

FAKE_POST_LINES = [
    "---",
    "title: Fake Post Title",
    "first-published: 2020-12-17",
    "tags:",
    "- Fake Tag 1",
    "- Fake Tag 2",
    "---",
    "",
    "This is the post excerpt.",
    "",
    "<!-- read more -->",
    "",
    "This is the post content.",
]

FAKE_POST_FRONT_MATTER_TEXT = "title: Fake Post Title\nfirst-published: 2020-12-17\ntags:\n- Fake Tag 1\n- Fake Tag 2"

FAKE_POST_FRONT_MATTER = {
    "title": "Fake Post Title",
    "first-published": datetime.date(2020, 12, 17),
    "tags": ["Fake Tag 1", "Fake Tag 2"],
}

FAKE_POST_TEXT_EXCLUDING_FRONT_MATTER = "\nThis is the post excerpt.\n\n<!-- read more -->\n\nThis is the post content."

FAKE_POST_EXCERPT = "<p>This is the post excerpt.</p>\n"

# example of the text of a post that does not have an exceprt:
FAKE_POST_TEXT_WITHOUT_EXCERPT = (
    "---\ntitle: Fake Post Title\nfirst-published: 2020-12-17\ntags:\n- Fake Tag 1\n- Fake Tag 2\n---\n\nThis is the "
    "post content."
)

FAKE_POST_HTML = "<p>This is the post excerpt.</p>\n\n<!-- read more -->\n\n<p>This is the post content.</p>\n"


@pytest.mark.parametrize(
    "path",
    [
        "/path/to/some/fake/post.md",
        Path("/path/to/some/fake/post.md"),
    ],
)
@unittest.skipIf(sys.platform.startswith("win"), "requires Windows")
def test_post_path_is_posix_path(path):
    """
    The `Post` class can be initialized with either a string or a `Path`, but `Post().path` should always be a
    PosixPath on POSIX platforms.
    """
    post = Post(path)
    assert type(post.path) is PosixPath


@pytest.mark.parametrize(
    "path",
    [
        "/path/to/some/fake/post.md",
        Path("/path/to/some/fake/post.md"),
    ],
)
@unittest.skipUnless(sys.platform.startswith("win"), "requires Windows")
def test_post_path_is_windows_path(path):
    """
    The `Post` class can be initialized with either a string or a `Path`, but `Post().path` should always be a
    WindowsPath on Windows platforms.
    """
    post = Post(path)
    assert type(post.path) is WindowsPath


@mock.patch("phlooph.models.Path.read_text", return_value=FAKE_POST_TEXT)
def test_post_lines(mock_read_text):
    post = Post("some-fake-post.md")
    assert post.lines == FAKE_POST_LINES


@mock.patch("phlooph.models.Path.read_text", return_value=FAKE_POST_TEXT)
def test_post_get_front_matter_text(mock_read_text):
    post = Post("some-fake-post.md")
    assert post._get_front_matter_text() == FAKE_POST_FRONT_MATTER_TEXT


@mock.patch("phlooph.models.Path.read_text", return_value=FAKE_POST_TEXT)
def test_post_front_matter(mock_read_text):
    post = Post("some-fake-post.md")
    assert post.front_matter == FAKE_POST_FRONT_MATTER


@mock.patch("phlooph.models.Path.read_text", return_value=FAKE_POST_TEXT)
def test_post_title(mock_read_text):
    post = Post("some-fake-post.md")
    assert post.title == "Fake Post Title"


@mock.patch("phlooph.models.Path.read_text", return_value=FAKE_POST_TEXT)
def test_post_tags(mock_read_text):
    post = Post("some-fake-post.md")
    assert post.tags == ["fake-tag-1", "fake-tag-2"]


@mock.patch("phlooph.models.Path.read_text", return_value=FAKE_POST_TEXT)
def test_post_date_published(mock_read_text):
    post = Post("some-fake-post.md")
    assert post.date_published == datetime.date(2020, 12, 17)


@mock.patch("phlooph.models.Path.read_text", return_value=FAKE_POST_TEXT)
def test_post_text(mock_read_text):
    post = Post("some-fake-post.md")
    assert post.text == FAKE_POST_TEXT_EXCLUDING_FRONT_MATTER


@mock.patch("phlooph.models.Path.read_text", return_value=FAKE_POST_TEXT)
def test_post_excerpt(mock_read_text):
    post = Post("some-fake-post.md")
    assert post.excerpt == FAKE_POST_EXCERPT


@mock.patch("phlooph.models.Path.read_text", return_value=FAKE_POST_TEXT_WITHOUT_EXCERPT)
def test_post_excerpt_without_excerpt(mock_read_text):
    post = Post("some-fake-post.md")
    assert post.excerpt is None


@mock.patch("phlooph.models.config.SOURCE_DIR", Path("/home/user/source-dir"))
def test_post_path_relative_to_source_dir():
    post = Post("/home/user/source-dir/posts/some-post/index.md")
    assert post.path_relative_to_source_dir == Path("posts/some-post/index.md")


@mock.patch("phlooph.models.config.SOURCE_DIR", Path("/home/user/source-dir"))
def test_post_relative_url():
    post = Post("/home/user/source-dir/posts/some-post/index.md")
    assert post.relative_url == "/posts/some-post/"


@mock.patch("phlooph.models.Path.read_text", return_value=FAKE_POST_TEXT)
def test_post_html(mock_read_text):
    post = Post("some-fake-post.md")
    assert post.html == FAKE_POST_HTML


@pytest.mark.parametrize(
    "path, mock_path_is_dir_return_value, expected_is_dir, expected_is_md",
    [
        ("/var/log", True, True, False),
        ("/path/to/posts/post.md", False, False, True),
        ("/post/to/some/image/image.png", False, False, False),
    ],
)
@mock.patch("phlooph.models.Path.is_dir")
def test_source_type(mock_path_is_dir, path, mock_path_is_dir_return_value, expected_is_dir, expected_is_md):
    mock_path_is_dir.return_value = mock_path_is_dir_return_value
    source = Source(path)
    assert source.is_dir is expected_is_dir
    assert source.is_md is expected_is_md


@pytest.mark.parametrize(
    "path, expected_destination",
    [
        ("/home/user/source-dir/some-other-dir/", Path("/home/user/destination-dir/some-other-dir/")),
        ("/home/user/source-dir/posts/post.md", Path("/home/user/destination-dir/posts/index.html")),
        ("/home/user/source-dir/images/image.png", Path("/home/user/destination-dir/images/image.png")),
    ],
)
@mock.patch("phlooph.models.config.DESTINATION_DIR", Path("/home/user/destination-dir"))
@mock.patch("phlooph.models.config.SOURCE_DIR", Path("/home/user/source-dir"))
def test_source_destination(path, expected_destination):
    source = Source(path)
    assert source.destination == expected_destination


@pytest.mark.parametrize(
    "path, expected_parent_directory",
    [
        ("/home/user/source-dir/some-other-dir/", Path("/home/user/destination-dir/")),
        ("/home/user/source-dir/posts/post.md", Path("/home/user/destination-dir/posts/")),
        ("/home/user/source-dir/images/image.png", Path("/home/user/destination-dir/images/")),
    ],
)
@mock.patch("phlooph.models.config.DESTINATION_DIR", Path("/home/user/destination-dir"))
@mock.patch("phlooph.models.config.SOURCE_DIR", Path("/home/user/source-dir"))
def test_source_parent_directory(path, expected_parent_directory):
    source = Source(path)
    assert source.parent_directory == expected_parent_directory


@mock.patch.object(Source, "parent_directory")
@mock.patch.object(Source, "destination")
@mock.patch.object(Source, "is_dir", True)
def test_source_mkdir_when_source_is_dir(mock_source_destination, mock_source_parent_directory):
    source = Source("some-fake-path")
    source.mkdir()
    mock_source_destination.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    mock_source_parent_directory.assert_not_called()


@mock.patch.object(Source, "parent_directory")
@mock.patch.object(Source, "destination")
@mock.patch.object(Source, "is_dir", False)
def test_source_mkdir_when_source_is_not_dir(mock_source_destination, mock_source_parent_directory):
    source = Source("some-fake-path")
    source.mkdir()
    mock_source_destination.mkdir.assert_not_called()
    mock_source_parent_directory.mkdir.assert_called_once_with(parents=True, exist_ok=True)
