from setuptools import setup, find_packages

packages = find_packages()

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="eda_plugin",
    version="0.2.3",
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
    package_data={"": ["settings.json", "utility/*.jar"]},
    include_package_data=True,
    install_requires=[
        "pyqt5",
        "pycromanager",
        "pyqtgraph",
        "qimage2ndarray",
        "qdarkstyle",
        "tifffile",
    ],
    author="Willi L. Stepp",
    author_email="willi.stepp@epfl.ch",
    python_requires=">=3.8",
)
