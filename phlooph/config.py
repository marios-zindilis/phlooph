from pathlib import Path


HOME = Path.home()
SOURCE_DIR = HOME / "Code" / "zindilis.com" / "website-sources"
DESTINATION_DIR = HOME / "Code" / "zindilis.com" / "marios-zindilis.github.io"
POSTS_DIR = SOURCE_DIR / "posts"
FEED_PATH = DESTINATION_DIR / "feeds" / "feed.xml"

IGNORE = [  # list of files to be ignored during rendering, relative to SOURCE_DIR, passed to fnmatch.fnmatch()
    "README.md",
    "test",
    "LICENSE",
    ".git",
    ".git/*",
    "drafts",
    "drafts/*",
]

POSTS_IN_FEED = 20  # used to generate the RSS feed

POSTS_PER_PAGE = 10  # used to paginate posts into pages

EXCERPT_SEPARATOR = "<!-- read more -->"  # separates the excerpt from the rest of the content

POST_IMAGE_FILES = ("index.jpg", "index.jpeg", "index.png")
