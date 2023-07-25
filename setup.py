from traceback import extract_stack
from setuptools import setup, find_packages

packages = find_packages()

print(packages)
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

version = "0.2.25"

setup(
    name="eda_plugin",
    version=version,
    description="Event-driven acquisition",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/wl-stepp/eda_plugin",
    project_urls={
        "Bug Tracker": "https://github.com/wl-stepp/eda_plugin/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
    packages=packages,
    package_data={"": ["settings.json", "utility/*.jar", "utility/models/*"]},
    include_package_data=True,
    install_requires=[
        "qtpy",
        "pycromanager<0.26",
        "pyqtgraph",
        "qimage2ndarray",
        "qdarkstyle",
        "tifffile",
        "zenodo_get",
        "docstring_inheritance",
        "zarr",
        "ome_zarr",
        "pymm_eventserver",
        "ome-types",
    ],
    extras_require={'pyqt5': ['PyQt5'], 'pyqt6': ['PyQt6']},
    author="Willi L. Stepp",
    author_email="willi.stepp@epfl.ch",
    python_requires=">=3.7",
)
