# Configuration file for the Sphinx documentation builder.

# -- Project information

project = "event-driven-acquisition"
copyright = "2022, Willi L. Stepp"
author = "Willi L. Stepp"

release = "0.2"
version = "0.2.19"

# -- General configuration

import os
import sys


autodoc_mock_imports = [
    "PyQt5",
    "PyQt6",
    "qtpy",
    "numpy",
    "tensorflow",
    "pycromanager",
    "zmq",
    "pyqtgraph",
    "pycromanager",
    "qdarkstyle",
    "qimage2ndarray",
    "tifffile",
    "nidaqmx",
    "skimage",
    "zenodo_get",
    "pymm_eventserver",
    "ome_types",
    "ome_zarr",
    "zarr",
    "json",
    "numcodecs"
]

sys.path.insert(0, "../..")

extensions = [
    "sphinx.ext.duration",
    "sphinx.ext.doctest",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinxcontrib.mermaid",
]

autosummary_generate = True


intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master/", None),
}
intersphinx_disabled_domains = ["std"]

templates_path = ["_templates"]

# -- Options for HTML output

html_theme = "sphinx_rtd_theme"
# html_static_path = ["_static"]
# html_extra_path = ["_static"]

# -- Options for EPUB output
epub_show_urls = "footnote"

# https://stackoverflow.com/questions/2701998/sphinx-autodoc-is-not-automatic-enough/62613202#62613202
