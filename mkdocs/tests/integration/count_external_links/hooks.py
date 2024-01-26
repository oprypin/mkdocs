from __future__ import annotations

from markdown.extensions import Extension


def on_config(config, **kwargs):
    config.markdown_extensions.append(MyExtension())


class MyExtension(Extension):
    def __init__(self):
        self.links: list[str] = []

    def extendMarkdown(self, md):
        md.preprocessors.register(MyTreeprocessor(links), "my_treeprocessor", priority=0)


class MyTreeprocessor(Preprocessor):
    def __init__(self, links: list[str]):
        self.links = links

    def run(self, root: etree.Element) -> None:
        ...


def on_files(files):
    f = files.get_file_from_path("external-links.md")
    if f is None:
        f = File.generated(config)
