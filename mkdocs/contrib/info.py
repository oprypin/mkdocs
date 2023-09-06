from __future__ import annotations

import dataclasses
import inspect
import sys
from typing import TYPE_CHECKING, Iterator

import click
import markdown.util

from mkdocs.plugins import BasePlugin

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig

if sys.version_info >= (3, 10):
    from importlib.metadata import entry_points
else:
    from importlib_metadata import entry_points


# Markdown


@dataclasses.dataclass
class MarkdownItem:
    priority: float
    key: str
    processor: type
    extension: type | None
    deregistered: bool = False


KNOWN_ORIGINS = {
    'build_preprocessors': 'preprocessors',
    'build_block_parser': 'blockprocessors',
    'build_treeprocessors': 'treeprocessors',
    'build_inlinepatterns': 'inlinepatterns',
    'build_postprocessors': 'postprocessors',
}

captured_items: dict[list[MarkdownItem]] = {
    'preprocessors': [],
    'blockprocessors': [],
    'treeprocessors': [],
    'inlinepatterns': [],
    'postprocessors': [],
}


class CapturingRegistry(markdown.util.Registry):
    def __init__(self):
        for f in inspect.stack():
            if f.function == 'build_parser':
                break
            prev_func = f.function
        self.__captured_items = captured_items[KNOWN_ORIGINS[prev_func]]
        super().__init__()

    def register(self, item, name, priority) -> None:
        super().register(item, name, priority)
        etyp = None
        for f in inspect.stack():
            if f.function == 'extendMarkdown':
                etyp = type(f.frame.f_locals["self"])
                break
            if f.function == 'build_parser':
                etyp = markdown
        self.__captured_items.append(
            MarkdownItem(priority, name, type(item), etyp),
        )

    def deregister(self, name, strict=True):
        super().deregister(name, strict=strict)
        for item in self.__captured_items:
            if item.key == name:
                item.deregistered = True


def get_section_info(items: dict[list[MarkdownItem]]):
    for item in sorted(items, key=lambda item: item.priority, reverse=True):
        style = {}
        prio = f'{item.priority:>5.1f}'
        prio = f"{prio.rstrip('0'):<5}"
        if item.deregistered:
            prio = click.style(prio, strikethrough=True, reset=False)
            style['fg'] = 'white'
        procname = f'{item.processor.__module__}:{item.processor.__qualname__}'
        k = f'{item.key!r:<25}'
        msg = f'{prio} {k}← {procname:<60}'
        if item.extension is markdown:
            style.setdefault('fg', 'blue')
        elif item.extension:
            if not item.extension.__module__.startswith('markdown.'):
                style['bold'] = True
            clsname = f'{item.extension.__module__}:{item.extension.__qualname__}'
            entry = '???'
            for ep in entry_points(group='markdown.extensions'):
                try:
                    mod, cls = ep.value.split(':')
                    if getattr(sys.modules[mod], cls) == item.extension:
                        entry = repr(ep.name)
                        break
                except (KeyError, ValueError, AttributeError):
                    pass
            else:
                try:
                    sys.modules[item.extension.__module__].makeExtension  # noqa: B018
                except (KeyError, AttributeError):
                    pass
                else:
                    entry = repr(item.extension.__module__)
            msg += f'← {clsname:<55}← {entry}'
        else:
            msg += '← ???'

        if style:
            msg = click.style(msg, **style)
        yield msg

        if procname == 'markdown.treeprocessors:InlineProcessor':
            for line in get_section_info(captured_items['inlinepatterns']):
                yield '    ' + line


def get_markdown_info() -> Iterator[str]:
    for name in 'preprocessors', 'blockprocessors', 'treeprocessors', 'postprocessors':
        items = captured_items[name]
        if items:
            yield f'---------- {name.upper()} ----------'
        yield from get_section_info(items)


# MkDocs


def print_mkdocs_info(config: MkDocsConfig) -> None:
    pass  # for event_name, config.plugins.events


class InfoPlugin(BasePlugin):
    """Dumps event priorities."""

    def __init__(self):
        self.printed: bool = False

    def on_startup(self, *args, **kwargs):
        pass

    def on_page_markdown(self, *args, **kwargs):
        markdown.util.Registry = CapturingRegistry

    def on_page_content(self, html: str, *, config: MkDocsConfig, **kwargs) -> str | None:
        if not self.printed:
            for line in get_markdown_info():
                print(line)  # noqa: T201
            print_mkdocs_info(config)
            self.printed = True
