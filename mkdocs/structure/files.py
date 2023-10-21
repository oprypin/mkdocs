from __future__ import annotations

import enum
import fnmatch
import logging
import os
import posixpath
import shutil
import warnings
from functools import cached_property
from pathlib import PurePath
from typing import IO, TYPE_CHECKING, Callable, Iterable, Iterator, Sequence, overload
from urllib.parse import quote as urlquote

import pathspec
import pathspec.gitignore
import pathspec.util

from mkdocs import utils

if TYPE_CHECKING:
    import jinja2.environment

    from mkdocs.config.defaults import MkDocsConfig
    from mkdocs.structure.pages import Page


log = logging.getLogger(__name__)


class InclusionLevel(enum.Enum):
    EXCLUDED = -2
    """The file is excluded from the final site, but will still be populated during `mkdocs serve`."""
    NOT_IN_NAV = -1
    """The file is part of the site, but doesn't produce nav warnings."""
    UNDEFINED = 0
    """Still needs to be computed based on the config. If the config doesn't kick in, acts the same as `included`."""
    INCLUDED = 1
    """The file is part of the site. Documentation pages that are omitted from the nav will produce warnings."""

    def all(self):
        return True

    def is_included(self):
        return self.value > self.EXCLUDED.value

    def is_excluded(self):
        return self.value <= self.EXCLUDED.value

    def is_in_nav(self):
        return self.value > self.NOT_IN_NAV.value

    def is_not_in_nav(self):
        return self.value <= self.NOT_IN_NAV.value


class Files:
    """A collection of [File][mkdocs.structure.files.File] objects."""

    def __init__(self, files: list[File], *, config: MkDocsConfig | None = None) -> None:
        self._files = files
        self._src_uris: dict[str, File] | None = None
        if config is not None:
            self.config = config

    config: MkDocsConfig

    def __iter__(self) -> Iterator[File]:
        """Iterate over the files within."""
        return iter(self._files)

    def __len__(self) -> int:
        """The number of files within."""
        return len(self._files)

    def __contains__(self, path: str) -> bool:
        """Whether the file with this `src_uri` is in the collection."""
        return PurePath(path).as_posix() in self.src_uris

    @property
    def src_paths(self) -> dict[str, File]:
        """Soft-deprecated, prefer `src_uris`."""
        return {file.src_path: file for file in self._files}

    @property
    def src_uris(self) -> dict[str, File]:
        """
        A mapping containing every file, with the keys being their
        [`src_uri`][mkdocs.structure.files.File.src_uri].
        """
        if self._src_uris is None:
            self._src_uris = {file.src_uri: file for file in self._files}
        return self._src_uris

    def get_file_from_path(self, path: str) -> File | None:
        """Return a File instance with File.src_uri equal to path."""
        return self.src_uris.get(PurePath(path).as_posix())

    def append(self, file: File) -> None:
        """Append file to Files collection."""
        self._src_uris = None
        self._files.append(file)

    def remove(self, file: File) -> None:
        """Remove file from Files collection."""
        self._src_uris = None
        self._files.remove(file)

    @overload
    def new_file(
        self,
        src_uri: str,
        *,
        src_dir: str,
        dest_uri: str | None = None,
        inclusion: InclusionLevel = InclusionLevel.UNDEFINED,
        generated: bool = False,
    ) -> File:
        """Create a file entry originating from a physical location '{src_dir}/{path}'."""

    @overload
    def new_file(
        self,
        src_uri: str,
        *,
        content: IO,
        dest_uri: str | None = None,
        inclusion: InclusionLevel = InclusionLevel.UNDEFINED,
        generated: bool = True,
    ) -> File:
        """Create a file entry with in-memory content."""

    def new_file(
        self,
        src_uri: str,
        *,
        content: IO | None = None,
        src_dir: str | None = None,
        dest_uri: str | None = None,
        inclusion: InclusionLevel = InclusionLevel.UNDEFINED,
        generated: bool | None = None,
    ) -> File:
        if generated is None:
            generated = src_dir is None
        generated_by = self.config._current_plugin or '<unknown>' if generated else None
        return File(
            src_uri,
            src_dir=src_dir,
            content=content,
            dest_dir=self.config.site_dir,
            use_directory_urls=self.config.use_directory_urls,
            dest_uri=dest_uri,
            inclusion=inclusion,
            generated_by=generated_by,
        )

    def copy_static_files(
        self,
        dirty: bool = False,
        *,
        inclusion: Callable[[InclusionLevel], bool] = InclusionLevel.is_included,
    ) -> None:
        """Copy static files from source to destination."""
        for file in self:
            if not file.is_documentation_page() and inclusion(file.inclusion):
                file.copy_file(dirty)

    def documentation_pages(
        self, *, inclusion: Callable[[InclusionLevel], bool] = InclusionLevel.is_included
    ) -> Sequence[File]:
        """Return iterable of all Markdown page file objects."""
        return [file for file in self if file.is_documentation_page() and inclusion(file.inclusion)]

    def static_pages(self) -> Sequence[File]:
        """Return iterable of all static page file objects."""
        return [file for file in self if file.is_static_page()]

    def media_files(self) -> Sequence[File]:
        """Return iterable of all file objects which are not documentation or static pages."""
        return [file for file in self if file.is_media_file()]

    def javascript_files(self) -> Sequence[File]:
        """Return iterable of all javascript file objects."""
        return [file for file in self if file.is_javascript()]

    def css_files(self) -> Sequence[File]:
        """Return iterable of all CSS file objects."""
        return [file for file in self if file.is_css()]

    def add_files_from_theme(self, env: jinja2.Environment, config: MkDocsConfig) -> None:
        """Retrieve static files from Jinja environment and add to collection."""

        def filter(name):
            # '.*' filters dot files/dirs at root level whereas '*/.*' filters nested levels
            patterns = ['.*', '*/.*', '*.py', '*.pyc', '*.html', '*readme*', 'mkdocs_theme.yml']
            # Exclude translation files
            patterns.append("locales/*")
            patterns.extend(f'*{x}' for x in utils.markdown_extensions)
            patterns.extend(config.theme.static_templates)
            for pattern in patterns:
                if fnmatch.fnmatch(name.lower(), pattern):
                    return False
            return True

        for path in env.list_templates(filter_func=filter):
            # Theme files do not override docs_dir files
            path = PurePath(path).as_posix()
            if path not in self.src_uris:
                for dir in config.theme.dirs:
                    # Find the first theme dir which contains path
                    if os.path.isfile(os.path.join(dir, path)):
                        self.append(File(path, dir, config.site_dir, config.use_directory_urls))
                        break


class File:
    """
    A MkDocs File object.

    Points to the source and destination locations of a file.

    The `path` argument must be a path that exists relative to `src_dir`.

    The `src_dir` and `dest_dir` must be absolute paths on the local file system.

    The `use_directory_urls` argument controls how destination paths are generated. If `False`, a Markdown file is
    mapped to an HTML file of the same name (the file extension is changed to `.html`). If True, a Markdown file is
    mapped to an HTML index file (`index.html`) nested in a directory using the "name" of the file in `path`. The
    `use_directory_urls` argument has no effect on non-Markdown files.

    File objects have the following properties, which are Unicode strings:
    """

    src_uri: str
    """The pure path (always '/'-separated) of the source file relative to the source directory."""

    use_directory_urls: bool
    """Whether directory URLs ('foo/') should be used or not ('foo.html')."""

    src_dir: str | None
    """The OS path of the source directory (top-level docs_dir) that the source file originates from."""

    dest_dir: str
    """The OS path of the destination directory (top-level site_dir) that the file should be copied to."""

    inclusion: InclusionLevel = InclusionLevel.UNDEFINED
    """Whether the file will be excluded from the built site."""

    generated_by: str | None = None
    """If not None, indicates that a plugin generated this file on the fly.

    The value is the plugin's entrypoint name and can be used to find the plugin by key in the PluginCollection."""

    content: IO | None = None
    """If set, the file's content will be read from here.

    This logic is handled by `get_content`, which should be used instead of accessing this attribute."""

    @property
    def src_path(self) -> str:
        """Same as `src_uri` (and synchronized with it) but will use backslashes on Windows. Discouraged."""
        return os.path.normpath(self.src_uri)

    @src_path.setter
    def src_path(self, value):
        self.src_uri = PurePath(value).as_posix()

    @property
    def dest_path(self) -> str:
        """Same as `dest_uri` (and synchronized with it) but will use backslashes on Windows. Discouraged."""
        return os.path.normpath(self.dest_uri)

    @dest_path.setter
    def dest_path(self, value):
        self.dest_uri = PurePath(value).as_posix()

    page: Page | None = None

    def __init__(
        self,
        path: str,
        src_dir: str | None,
        dest_dir: str,
        use_directory_urls: bool,
        *,
        content: IO | None = None,
        dest_uri: str | None = None,
        inclusion: InclusionLevel = InclusionLevel.UNDEFINED,
        generated_by: str | None = None,
    ) -> None:
        if (src_dir is None) == (content is None):
            raise TypeError("File must have one of 'src_dir' or 'content'")
        self.src_path = path
        self.src_dir = src_dir
        self.dest_dir = dest_dir
        self.use_directory_urls = use_directory_urls
        self.content = content
        if dest_uri is not None:
            self.dest_uri = dest_uri
        self.inclusion = inclusion
        if generated_by is not None:
            self.generated_by = generated_by

    def __repr__(self):
        return f"{type(self).__name__}(src_uri={self.src_uri!r}, dest_uri={self.dest_uri!r}, name={self.name!r}, url={self.url!r})"

    @utils.weak_property
    def edit_uri(self) -> str | None:
        return self.src_uri if self.generated_by is not None else None

    def _get_stem(self) -> str:
        """Soft-deprecated, do not use."""
        filename = posixpath.basename(self.src_uri)
        stem, ext = posixpath.splitext(filename)
        return 'index' if stem == 'README' else stem

    name = cached_property(_get_stem)
    """Return the name of the file without its extension."""

    def _get_dest_path(self, use_directory_urls: bool | None = None) -> str:
        """Soft-deprecated, do not use."""
        if self.is_documentation_page():
            parent, filename = posixpath.split(self.src_uri)
            if use_directory_urls is None:
                use_directory_urls = self.use_directory_urls
            if not use_directory_urls or self.name == 'index':
                # index.md or README.md => index.html
                # foo.md => foo.html
                return posixpath.join(parent, self.name + '.html')
            else:
                # foo.md => foo/index.html
                return posixpath.join(parent, self.name, 'index.html')
        return self.src_uri

    dest_uri = cached_property(_get_dest_path)
    """The pure path (always '/'-separated) of the destination file relative to the destination directory."""

    def _get_url(self, use_directory_urls: bool | None = None) -> str:
        """Soft-deprecated, do not use."""
        url = self.dest_uri
        dirname, filename = posixpath.split(url)
        if use_directory_urls is None:
            use_directory_urls = self.use_directory_urls
        if use_directory_urls and filename == 'index.html':
            url = (dirname or '.') + '/'
        return urlquote(url)

    url = cached_property(_get_url)
    """The URI of the destination file relative to the destination directory as a string."""

    @cached_property
    def abs_src_path(self) -> str | None:
        """
        The absolute concrete path of the source file. Will use backslashes on Windows.

        Note: do not use this path to read the file, instead use `get_content()`.
        """
        if self.src_dir is None:
            return None
        return os.path.normpath(os.path.join(self.src_dir, self.src_uri))

    @cached_property
    def abs_dest_path(self) -> str:
        """The absolute concrete path of the destination file. Will use backslashes on Windows."""
        return os.path.normpath(os.path.join(self.dest_dir, self.dest_uri))

    def url_relative_to(self, other: File | str) -> str:
        """Return url for file relative to other file."""
        return utils.get_relative_url(self.url, other.url if isinstance(other, File) else other)

    def get_content(self) -> IO:
        """Get the contents of this file as a read-only file-like object."""
        if (content := self.content) is not None:
            try:
                content.seek(0)
            except OSError:
                pass
            return content
        else:
            assert self.abs_src_path is not None
            return open(self.abs_src_path, 'rb')

    def get_source(self) -> str:
        """Get the contents of this file as a string. Assumes UTF-8 encoding."""
        if self.content is not None:
            with self.get_content() as f:
                source = f.read()
            if isinstance(source, bytes):
                source = source.decode('utf-8-sig', errors='strict')
            return source
        else:
            assert self.abs_src_path is not None
            with open(self.abs_src_path, encoding='utf-8-sig', errors='strict') as f:
                return f.read()

    def copy_file(self, dirty: bool = False) -> None:
        """Copy source file to destination, ensuring parent directories exist."""
        if dirty and not self.is_modified():
            log.debug(f"Skip copying unmodified file: '{self.src_uri}'")
        else:
            log.debug(f"Copying media file: '{self.src_uri}'")
            self._copy_to(self.abs_dest_path)

    def _copy_to(self, output_path: str) -> None:
        output_path = self.abs_dest_path
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if self.content is not None:
            with self.get_content() as input_file, open(self.abs_dest_path, 'wb') as output_file:
                shutil.copyfileobj(input_file, output_file)
        else:
            assert self.abs_src_path is not None
            try:
                utils.copy_file(self.abs_src_path, self.abs_dest_path)
            except shutil.SameFileError:
                pass  # Let plugins write directly into site_dir.

    def is_modified(self) -> bool:
        if self.content is not None:
            return True
        assert self.abs_src_path is not None
        if os.path.isfile(self.abs_dest_path):
            return os.path.getmtime(self.abs_dest_path) < os.path.getmtime(self.abs_src_path)
        return True

    def is_documentation_page(self) -> bool:
        """Return True if file is a Markdown page."""
        return utils.is_markdown_file(self.src_uri)

    def is_static_page(self) -> bool:
        """Return True if file is a static page (HTML, XML, JSON)."""
        return self.src_uri.endswith(('.html', '.htm', '.xml', '.json'))

    def is_media_file(self) -> bool:
        """Return True if file is not a documentation or static page."""
        return not (self.is_documentation_page() or self.is_static_page())

    def is_javascript(self) -> bool:
        """Return True if file is a JavaScript file."""
        return self.src_uri.endswith(('.js', '.javascript', '.mjs'))

    def is_css(self) -> bool:
        """Return True if file is a CSS file."""
        return self.src_uri.endswith('.css')


_default_exclude = pathspec.gitignore.GitIgnoreSpec.from_lines(['.*', '/templates/'])


def _set_exclusions(files: Iterable[File], config: MkDocsConfig) -> None:
    """Re-calculate which files are excluded, based on the patterns in the config."""
    exclude: pathspec.gitignore.GitIgnoreSpec | None = config.get('exclude_docs')
    exclude = _default_exclude + exclude if exclude else _default_exclude
    nav_exclude: pathspec.gitignore.GitIgnoreSpec | None = config.get('not_in_nav')

    for file in files:
        if file.inclusion == InclusionLevel.UNDEFINED:
            if exclude.match_file(file.src_uri):
                file.inclusion = InclusionLevel.EXCLUDED
            elif nav_exclude and nav_exclude.match_file(file.src_uri):
                file.inclusion = InclusionLevel.NOT_IN_NAV
            else:
                file.inclusion = InclusionLevel.INCLUDED


def get_files(config: MkDocsConfig) -> Files:
    """Walk the `docs_dir` and return a Files collection."""
    files: list[File] = []
    conflicting_files: list[tuple[File, File]] = []
    for source_dir, dirnames, filenames in os.walk(config['docs_dir'], followlinks=True):
        relative_dir = os.path.relpath(source_dir, config['docs_dir'])
        dirnames.sort()
        filenames.sort(key=_file_sort_key)

        files_by_dest: dict[str, File] = {}
        for filename in filenames:
            file = File(
                os.path.join(relative_dir, filename),
                config['docs_dir'],
                config['site_dir'],
                config['use_directory_urls'],
            )
            # Skip README.md if an index file also exists in dir (part 1)
            prev_file = files_by_dest.setdefault(file.dest_uri, file)
            if prev_file is not file:
                conflicting_files.append((prev_file, file))
            files.append(file)
            prev_file = file

    _set_exclusions(files, config)
    # Skip README.md if an index file also exists in dir (part 2)
    for a, b in conflicting_files:
        if b.inclusion.is_included():
            if a.inclusion.is_included():
                log.warning(
                    f"Excluding '{a.src_uri}' from the site because it conflicts with '{b.src_uri}'."
                )
            try:
                files.remove(a)
            except ValueError:
                pass  # Catching this to avoid errors if attempting to remove the same file twice.
        else:
            try:
                files.remove(b)
            except ValueError:
                pass

    return Files(files, config=config)


def _file_sort_key(f: str):
    """Always sort `index` or `README` as first filename in list."""
    return (os.path.splitext(f)[0] not in ('index', 'README'), f)


def _sort_files(filenames: Iterable[str]) -> list[str]:
    return sorted(filenames, key=_file_sort_key)


def _filter_paths(basename: str, path: str, is_dir: bool, exclude: Iterable[str]) -> bool:
    warnings.warn(
        "_filter_paths is not used since MkDocs 1.5 and will be removed soon.", DeprecationWarning
    )
    for item in exclude:
        # Items ending in '/' apply only to directories.
        if item.endswith('/') and not is_dir:
            continue
        # Items starting with '/' apply to the whole path.
        # In any other cases just the basename is used.
        match = path if item.startswith('/') else basename
        if fnmatch.fnmatch(match, item.strip('/')):
            return True
    return False
