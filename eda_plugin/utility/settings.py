"""Utility for the settings file. And other module wide settings."""

import json
import logging
import logging.handlers
import os


def get_settings(calling_class=None, name=None):
    """Get the settings from the settings.json file and extract a module if defined."""
    try:
        with open(os.path.dirname(__file__) + "/../settings.json", "r") as j:
            contents = json.loads(j.read())
        if calling_class is None:
            return contents
        else:
            trace = calling_class.__module__.split(".")
            for module in trace:
                contents = contents[module]
            if name:
                contents = contents[name]
            return contents
    except json.JSONDecodeError:
        print("WARNING: settings could not be loaded", calling_class)
        return {}


def set_settings(value, calling_class):
    settings_file = os.path.dirname(__file__) + "/../settings.json"
    try:
        with open(settings_file, "r") as j:
            contents = json.loads(j.read())
    except json.JSONDecodeError:
        contents = {}

    def nested_set(dic, keys, value):
        for key in keys[:-1]:
            dic = dic.setdefault(key, {})
        dic[keys[-1]] = value

    trace = calling_class.__module__.split(".")
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

    # handler = logging.handlers.SysLogHandler(address=('localhost', 514))
    # logger.addHandler(handler)


def install_mm_plugins():
    """Transfer the .jar files to the folder in the Micro-Manager installation."""
    from qtpy import QtWidgets
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
