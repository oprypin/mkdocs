# Developing Plugins

*A guide to creating MkDocs Plugins.*

Plugins for MkDocs are written in the Python programming language - like MkDocs itself. It is generally expected that
each plugin would be distributed as a separate Python module, although it is
possible to define multiple plugins in the same module. At a minimum, a MkDocs
Plugin must consist of a [`BasePlugin`] subclass and an [entry point] which
points to it.

## Defining the plugin class

A subclass of `mkdocs.plugins.BasePlugin` should define the behavior of the plugin.
The class generally consists of actions to perform on specific events in the build
process as well as a configuration scheme for the plugin.

<a id="config_scheme"></a>

But first, a separate subclass of `mkdocs.config.base.Config` that holds the *configuration* of that plugin should be defined.

NOTE: This class-based approach for configs only became available since MkDocs 1.4, and replaced the old `config_scheme` attribute. See [in release notes](../about/release-notes.md#rework-configoption-schemas-as-class-based-2962) if you need to learn how the old style works.

For example, the following configuration definition has three options: `foo`, which accepts a string; `bar`, which accepts an integer; and `baz`, which accepts a boolean value.

```python
from mkdocs.config import base, config_options as opt
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import BasePlugin

class MyPluginConfig(base.Config):
    foo = opt.Type(str, default='a default value')
    bar = opt.Type(int)  # required
    baz = opt.Type(bool, default=False)

class MyPlugin(BasePlugin[MyPluginConfig]):
    def on_pre_build(self, config: MkDocsConfig, **kwargs):
        if self.config.baz:
            # implement "baz" functionality here...
```

Then for the plugin class itself, notice how we specify in square brackets that it uses `MyPluginConfig` as its config. This means that `MyPlugin` will always be guaranteed to have a validated instance of `MyPluginConfig` populated as its `self.config` member. This member will hold the user-specified options for the plugin. It is populated by MkDocs itself after config validation has completed.

The above example plugin also defines 1 event that accesses an option provided by the user.

#### Examples of config definitions

>! EXAMPLE:
>
> ```python
> from mkdocs.config import base, config_options as opt
>
> class _ValidationOptions(base.Config):
>     enabled = opt.Type(bool, default=True)
>     verbose = opt.Type(bool, default=False)
>     skip_checks = opt.ListOfItems(opt.Choice(('foo', 'bar', 'baz')), default=[])
>
> class MyPluginConfig(base.Config):
>     definition_file = opt.File(exists=True)  # required
>     checksum_file = opt.Optional(opt.File(exists=True))  # can be None but must exist if specified
>     validation = opt.SubConfig(_ValidationOptions)
> ```
>
> From the user's point of view `SubConfig` is similar to `Type(dict)`, it's just that it also retains full ability for validation: you define all valid keys and what each value should adhere to.
>
> And `ListOfItems` is similar to `Type(list)`, but again, we define the constraint that each value must adhere to.
>
> This accepts a config as follows:
>
> ```yaml
> my_plugin:
>   definition_file: configs/test.ini  # relative to mkdocs.yml
>   validation:
>     enabled: !ENV [CI, false]
>     verbose: true
>     skip_checks:
>       - foo
>       - baz
> ```
<!-- -->
>? EXAMPLE:
>
> ```python
> import numbers
> from mkdocs.config import base, config_options as opt
>
> class _Rectangle(base.Config):
>     width = opt.Type(numbers.Real)  # required
>     height = opt.Type(numbers.Real)  # required
>
> class MyPluginConfig(base.Config):
>     add_rectangles = opt.ListOfItems(opt.SubConfig(_Rectangle))  # required
> ```
>
> In this example we define a list of complex items, and that's achieved by passing a concrete `SubConfig` to `ListOfItems`.
>
> This accepts a config as follows:
>
> ```yaml
> my_plugin:
>   add_rectangles:
>     - width: 5
>       height: 7
>     - width: 12
>       height: 2
> ```

When the user's configuration is loaded, the schema defined by these attributes will be used to
validate the configuration and fill in any defaults for settings not
provided by the user. The validation classes may be any of the classes
provided in `mkdocs.config.config_options` or a third party subclass defined
in the plugin.

Any settings provided by the user which fail validation or are not defined
in the `config_scheme` will raise a `mkdocs.config.base.ValidationError`.

All `BasePlugin` subclasses contain the following method(s):

### `load_config(options)`

Loads configuration from a dictionary of options. Returns a tuple of
`(errors, warnings)`. This method is called by MkDocs during configuration
validation and should not need to be called by the plugin.

### `on_<event_name>()`

Optional methods which define the behavior for specific [events]. The plugin
should define its behavior within these methods. Replace `<event_name>` with
the actual name of the event. For example, the `pre_build` event would be
defined in the `on_pre_build` method.

Most events accept one positional argument and various keyword arguments. It
is generally expected that the positional argument would be modified (or
replaced) by the plugin and returned. If nothing is returned (the method
returns `None`), then the original, unmodified object is used. The keyword
arguments are simply provided to give context and/or supply data which may
be used to determine how the positional argument should be modified. It is
good practice to accept keyword arguments as `**kwargs`. In the event that
additional keywords are provided to an event in a future version of MkDocs,
there will be no need to alter your plugin.

For example, the following event would add an additional static_template to
the theme config:

```python
class MyPlugin(BasePlugin):
    def on_config(self, config: MkDocsConfig, **kwargs):
        config.theme.static_templates.add('my_template.html')
        return config
```

Notice also that here we receive the top-level `config` of MkDocs itself, which is different from the current plugin's config - `self.config`.

NOTE: Attribute-based access to config options only became available since MkDocs 1.4. See [in release notes](../about/release-notes.md#rework-configoption-schemas-as-class-based-2962) if you need to learn how the old style works.

## Events

Events are split into these categories: [one-time events](#one-time-events), [global events](#global-events), [page events](#page-events) and [template events](#template-events).

<details class="card" open>
  <summary>
    Diagram of relations between all the plugin events
  </summary>
  <div class="card-body">
    Legend:
    <ul>
      <li>The events themselves are shown in yellow, with their parameters.
      <li>Arrows show the flow of arguments and outputs of each event.
          Sometimes they're omitted.
      <li>The events are chronologically ordered from top to bottom.
      <li>Dotted lines appear at splits from global events to per-page events.
      <li>Click the events' titles to jump to their description.
    </ul>
--8<-- "docs/img/plugin-events.svg"
  </div>
</details>
<br>

### One-time Events

One-time events run once *ever*, until `mkdocs` is re-launched. But the only case where these tangibly differ from [global events](#global-events) is when `mkdocs serve` is used: global events, unlike these, will run once per *build*.

#### on_startup

::: mkdocs.plugins.BasePlugin.on_startup
    options:
        show_root_heading: false
        show_root_toc_entry: false

#### on_shutdown

::: mkdocs.plugins.BasePlugin.on_shutdown
    options:
        show_root_heading: false
        show_root_toc_entry: false

#### on_serve

::: mkdocs.plugins.BasePlugin.on_serve
    options:
        show_root_heading: false
        show_root_toc_entry: false

### Global Events

Global events are called once per build at either the beginning or end of the
build process. Any changes made in these events will have a global effect on the
entire site.

#### on_config

::: mkdocs.plugins.BasePlugin.on_config
    options:
        show_root_heading: false
        show_root_toc_entry: false

#### on_pre_build

::: mkdocs.plugins.BasePlugin.on_pre_build
    options:
        show_root_heading: false
        show_root_toc_entry: false

#### on_files

::: mkdocs.plugins.BasePlugin.on_files
    options:
        show_root_heading: false
        show_root_toc_entry: false

#### on_nav

::: mkdocs.plugins.BasePlugin.on_nav
    options:
        show_root_heading: false
        show_root_toc_entry: false

#### on_env

::: mkdocs.plugins.BasePlugin.on_env
    options:
        show_root_heading: false
        show_root_toc_entry: false

#### on_post_build

::: mkdocs.plugins.BasePlugin.on_post_build
    options:
        show_root_heading: false
        show_root_toc_entry: false

#### on_build_error

::: mkdocs.plugins.BasePlugin.on_build_error
    options:
        show_root_heading: false
        show_root_toc_entry: false

### Template Events

Template events are called once for each non-page template. Each template event
will be called for each template defined in the [extra_templates] config setting
as well as any [static_templates] defined in the theme. All template events are
called after the [env] event and before any [page events](#page-events).

#### on_pre_template

::: mkdocs.plugins.BasePlugin.on_pre_template
    options:
        show_root_heading: false
        show_root_toc_entry: false

#### on_template_context

::: mkdocs.plugins.BasePlugin.on_template_context
    options:
        show_root_heading: false
        show_root_toc_entry: false

#### on_post_template

::: mkdocs.plugins.BasePlugin.on_post_template
    options:
        show_root_heading: false
        show_root_toc_entry: false

### Page Events

Page events are called once for each Markdown page included in the site. All
page events are called after the [on_post_template](#on_post_template) event and before the
[on_post_build](#on_post_build) event.

#### on_pre_page

::: mkdocs.plugins.BasePlugin.on_pre_page
    options:
        show_root_heading: false
        show_root_toc_entry: false

#### on_page_read_source

::: mkdocs.plugins.BasePlugin.on_page_read_source
    options:
        show_root_heading: false
        show_root_toc_entry: false

#### on_page_markdown

::: mkdocs.plugins.BasePlugin.on_page_markdown
    options:
        show_root_heading: false
        show_root_toc_entry: false

#### on_page_content

::: mkdocs.plugins.BasePlugin.on_page_content
    options:
        show_root_heading: false
        show_root_toc_entry: false

#### on_page_context

::: mkdocs.plugins.BasePlugin.on_page_context
    options:
        show_root_heading: false
        show_root_toc_entry: false

#### on_post_page

::: mkdocs.plugins.BasePlugin.on_post_page
    options:
        show_root_heading: false
        show_root_toc_entry: false

## Event Priorities

For each event type, corresponding methods of plugins are called in the order that the plugins appear in the `plugins` [config][].

Since MkDocs 1.4, plugins can choose to set a priority value for their events. Events with higher priority are called first. Events without a chosen priority get a default of 0. Events that have the same priority are ordered as they appear in the config.

### ::: mkdocs.plugins.event_priority

There may also arise a need to register a handler for the same event at multiple different priorities.

`CombinedEvent` makes this possible since MkDocs 1.6.

### ::: mkdocs.plugins.CombinedEvent

## Hooks

The [hooks](../user-guide/configuration.md#hooks) mechanism is a natural extension of plugins. Each hook file is like a plugin that doesn't need to be installed, also it doesn't have its own config, or even a class instance in the first place. So, any advice for plugins that you see in this document can be applied to hooks. In fact, let's write the next section in the "hooks" style - with the plugin class being assumed if you want to use these recipes for permanent plugins.

## Recipes

### Recipes for affecting file content

#### Adding a new Markdown document

Add a new `File` object to the `Files` collection inside the `on_files` event. This is the only way to make a **new** file come into existence **and** have it pass through MkDocs' normal Markdown&rarr;HTML pipeline.

> NOTE: **Event priority and interoperability.**
>
> If you know that other plugins may add files that your plugin would then want to look at, naturally you should probably put the `on_files` event at a later [priority](#mkdocs.plugins.event_priority). The same applies if you find it unlikely that other files would want to look at *your* plugin's modifications to files, if any.



#### Find & replace in existing Markdown documents

#### Adding a new raw file

#### Gather information about other files into a single other document

If this can be done without first passing through the render pipeline (and all the page events), you can simply follow the normal advice about [adding a new Markdown document](#adding-a-new-markdown-document). This is because you can inspect each file's content through `File.content_string` before any page events kick in. You can even write back to this property in order to modify files' content in advance of `on_page_markdown`. But if the render pipeline *is* needed or if you're 

Otherwise, there's a trick - you can ensure that the particular.

#### Gather information about other files into all other documents


## Handling Errors

MkDocs defines four error types:

### ::: mkdocs.exceptions.MkDocsException

### ::: mkdocs.exceptions.ConfigurationError

### ::: mkdocs.exceptions.BuildError

### ::: mkdocs.exceptions.PluginError

Unexpected and uncaught exceptions will interrupt the build process and produce
typical Python tracebacks, which are useful for debugging your code. However,
users generally find tracebacks overwhelming and often miss the helpful error
message. Therefore, MkDocs will catch any of the errors listed above, retrieve
the error message, and exit immediately with only the helpful message displayed
to the user.

Therefore, you might want to catch any exceptions within your plugin and raise a
`PluginError`, passing in your own custom-crafted message, so that the build
process is aborted with a helpful message.

The [on_build_error](#on_build_error) event will be triggered for any exception.

For example:

```python
from mkdocs.exceptions import PluginError
from mkdocs.plugins import BasePlugin


class MyPlugin(BasePlugin):
    def on_post_page(self, output, page, config, **kwargs):
        try:
            # some code that could throw a KeyError
            ...
        except KeyError as error:
            raise PluginError(f"Failed to find the item by key: '{error}'")

    def on_build_error(self, error, **kwargs):
        # some code to clean things up
        ...
```

## Logging in plugins

To ensure that your plugins' log messages adhere with MkDocs' formatting and `--verbose`/`--debug` flags, please write the logs to a logger under the `mkdocs.plugins.` namespace.

> EXAMPLE:
>
> ```python
> import logging
>
> log = logging.getLogger(f"mkdocs.plugins.{__name__}")
>
> log.warning("File '%s' not found. Breaks the build if --strict is passed", my_file_name)
> log.info("Shown normally")
> log.debug("Shown only with `--verbose`")
>
> if log.getEffectiveLevel() <= logging.DEBUG:
>     log.debug("Very expensive calculation only for debugging: %s", get_my_diagnostics())
> ```

`log.error()` is another logging level that is differentiated by its look, but in all other ways it functions the same as `warning`, so it's strange to use it. If your plugin encounters an actual error, it is best to just interrupt the build by raising [`mkdocs.exceptions.PluginError`][] (which will also log an ERROR message).

<!-- -->
> NEW: New in MkDocs 1.5
>
> MkDocs now provides a `get_plugin_logger()` convenience function that returns a logger like the above that is also prefixed with the plugin's name.
>
> ### ::: mkdocs.plugins.get_plugin_logger

## Entry Point

Plugins need to be packaged as Python libraries (distributed on PyPI separate
from MkDocs) and each must register as a Plugin via a setuptools `entry_points`.
Add the following to your `setup.py` script:

```python
entry_points={
    'mkdocs.plugins': [
        'pluginname = path.to.some_plugin:SomePluginClass',
    ]
}
```

The `pluginname` would be the name used by users (in the config file) and
`path.to.some_plugin:SomePluginClass` would be the importable plugin itself
(`from path.to.some_plugin import SomePluginClass`) where `SomePluginClass` is a
subclass of [`BasePlugin`] which defines the plugin behavior. Naturally, multiple
Plugin classes could exist in the same module. Simply define each as a separate
entry point.

```python
entry_points={
    'mkdocs.plugins': [
        'featureA = path.to.my_plugins:PluginA',
        'featureB = path.to.my_plugins:PluginB'
    ]
}
```

Note that registering a plugin does not activate it. The user still needs to
tell MkDocs to use it via the config.

## Publishing a Plugin

You should publish a package on [PyPI], then add it to the [Catalog] for discoverability. Plugins are strongly recommended to have a unique plugin name (entry point name) according to the catalog.

[`BasePlugin`]: #defining-the-plugin-class
[config]: ../user-guide/configuration.md#plugins
[entry point]: #entry-point
[env]: #on_env
[events]: #events
[extra_templates]: ../user-guide/configuration.md#extra_templates
[static_templates]: ../user-guide/configuration.md#static_templates
[catalog]: https://github.com/mkdocs/catalog
[PyPI]: https://pypi.org/
