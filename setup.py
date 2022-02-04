from setuptools import setup, find_packages

packages = find_packages()
print(packages)

setup(
    name="eda_plugin",
    version="0.1",
    # packages=["eda_plugin"],
    # package_data={"eda_plugin": ["actuators/*", "examples/*"]},
    package_data={"": ["settings.json"]},
    include_package_data=True,
    author="Willi L. Stepp",
    author_email="willi.stepp@epfl.ch",
)
