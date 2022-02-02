from setuptools import setup, find_packages

packages = find_packages()
print(packages)

setup(
    name="eda_plugin",
    version="0.1",
    packages=packages,
    author="Willi L. Stepp",
    author_email="willi.stepp@epfl.ch",
)
