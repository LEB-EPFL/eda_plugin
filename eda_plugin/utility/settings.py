"""Utility for the settings file. And other module wide settings."""

import json
import logging
import os


def get_settings(calling_class=None):
    """Get the settings from the settings.json file and extract a module if defined."""
    with open(os.path.dirname(__file__) + "/../settings.json", "r") as j:
        contents = json.loads(j.read())
    if calling_class is None:
        return contents
    else:
        trace = calling_class.__module__.split(".")
        for module in trace:
            contents = contents[module]
        return contents


def set_settings(name: str, value, calling_class=None):
    settings_file = os.path.dirname(__file__) + "/../settings.json"
    with open(settings_file, "r") as j:
        contents = json.loads(j.read())

    def nested_set(dic, keys, value):
        for key in keys[:-1]:
            dic = dic.setdefault(key, {})
        dic[keys[-1]] = value

    if calling_class is None:
        contents[name] = value
    else:
        trace = calling_class.__module__.split(".")
        trace = trace + [name]
        nested_set(contents, trace, value)
    with open(settings_file, "w") as fp:
        json.dump(contents, fp, indent=4)


def setup_logging():
    """Set up the logging for the project."""
    logger = logging.getLogger("EDA")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def install_mm_plugins():
    """Transfer the .jar files to the folder in the Micro-Manager installation."""
    from PyQt5 import QtWidgets
    import shutil
    import sys

    app = QtWidgets.QApplication(sys.argv)
    # app.exec()
    mm_folder = QtWidgets.QFileDialog.getExistingDirectory(
        caption="Choose the Micro-Manager main folder"
    )
    plugin_folder = os.path.join(mm_folder, "mmplugins")
    directory = os.path.dirname(__file__)
    files = ["ImageInjector.jar"]
    for file in files:
        print("src: ", os.path.join(directory, file))
        print("dst: ", os.path.join(plugin_folder, file))
        shutil.copyfile(
            os.path.join(directory, file), os.path.join(plugin_folder, file)
        )


if __name__ == "__main__":
    install_mm_plugins()
