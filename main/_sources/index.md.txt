---
html_theme.sidebar_secondary.remove: true
---

```{include} ../README.md
:end-before: <!-- README only content
```


How the documentation is structured
-----------------------------------

Documentation is split into [four categories](https://diataxis.fr), also accessible from links in the top bar.

<!-- https://sphinx-design.readthedocs.io/en/latest/grids.html -->

::::{grid} 2
:gutter: 4

:::{grid-item-card} {material-regular}`directions_walk;2em`
```{toctree}
:maxdepth: 2
tutorials
```
+++
Tutorials for installation and typical usage. New users start here.
:::

:::{grid-item-card} {material-regular}`directions;2em`
```{toctree}
:maxdepth: 2
how-to
```
+++
Practical step-by-step guides for the more experienced user.
:::

:::{grid-item-card} {material-regular}`info;2em`
```{toctree}
:maxdepth: 2
explanations
```
+++
Explanations of how it works and why it works that way.
:::

:::{grid-item-card} {material-regular}`menu_book;2em`
```{toctree}
:maxdepth: 2
reference
```
+++
Technical reference material including APIs and release notes.
:::

::::

## API Documentation

Interactive API documentation is available for all SmartEM Decisions services:

::::{grid} 2
:gutter: 4

:::{grid-item-card} {material-regular}`psychology;2em` Athena Decision Service API
:link: api/athena/index.html
:link-type: url

Complete interactive documentation for the Athena Decision Service API, including session management, decision recording, and algorithm results.

**Features:** Sessions • Decisions • Algorithm Results • Area Management • Configuration
:::

:::{grid-item-card} {material-regular}`smart_toy;2em` SmartEM Core API  
:link: api/smartem/index.html
:link-type: url

Documentation for the SmartEM Core API for recording electron microscopy sessions and experimental data.

**Features:** Sessions • Grids • Atlases • Atlas Tiles • Grid Squares • Foil Holes • Micrographs
:::

::::
