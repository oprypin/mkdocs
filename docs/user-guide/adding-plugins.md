# Adding Plugins

*A guide to installing and using MkDocs Plugins.*

---

## Installing Plugins

In order to use a third-party plugin, it needs to be *both* installed and added to `mkdocs.yml`.

So, first you need to determine the name of the package that contains it and install it using `pip`:

```bash
pip install mkdocs-foo-plugin
```

WARNING: Installing an MkDocs plugin means installing a Python package and executing any code that the author has put in there. So, exercise the usual caution; there's no attempt at sandboxing.

Once a plugin has been successfully installed, it is ready to use. It just needs
to be [enabled](#using-plugins) in the configuration file. The [catalog]
repository has a large ranked list of plugins that you can install and use.

## Using Plugins

The [`plugins`][config] configuration option should contain a list of plugins to
use when building the site. Each plugin entry must be a string name assigned to the
plugin (see the documentation of a given plugin to determine its "name", or look it up in the [catalog]). A
plugin listed here must already be [installed](#installing-plugins).

```yaml
plugins:
  - search
  - foo
```

NOTE: The 'search' plugin is built-in, so it's the only plugin that *doesn't* need to be installed. But, you should always list it in the `plugins` config, otherwise the search function will not work.

Some plugins provide configuration options of their own. If you would like
to set any options, then you can nest a key/value mapping
(`option_name: option value`) of any options that a given plugin supports. Note
that a colon (`:`) must follow the plugin name and then on a new line the option
name and value must be indented and separated by a colon. If you would like to
define multiple options for a single plugin, each option must be defined on a
separate line.

```yaml
plugins:
  - search:
      lang: en
      foo: bar
```

For information regarding the configuration options available for a given plugin,
see that plugin's documentation.

For a list of default plugins and how to override them, see the
[configuration][config] documentation.

[catalog]: https://github.com/mkdocs/catalog
[config]: ../user-guide/configuration.md#plugins
