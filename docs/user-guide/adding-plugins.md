# Adding Plugins

*A guide to installing and using MkDocs Plugins.*

---

## Installing Plugins

Before a plugin can be used, it must be installed on the system. If you are
using a plugin which comes with MkDocs, then it was installed when you installed
MkDocs. However, to install third party plugins, you need to determine the
appropriate package name and install it using `pip`:

```bash
pip install mkdocs-foo-plugin
```

WARNING: Installing an MkDocs plugin means installing a Python package and executing any code that the author has put in there. So, exercise the usual caution; there's no attempt at sandboxing.

Once a plugin has been successfully installed, it is ready to use. It just needs
to be [enabled](#using-plugins) in the configuration file. The [Catalog]
repository has a large ranked list of plugins that you can install and use.

## Using Plugins

The [`plugins`][config] configuration option should contain a list of plugins to
use when building the site. Each "plugin" must be a string name assigned to the
plugin (see the documentation for a given plugin to determine its "name"). A
plugin listed here must already be [installed](#installing-plugins).

```yaml
plugins:
  - search
```

Some plugins may provide configuration options of their own. If you would like
to set any configuration options, then you can nest a key/value mapping
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
