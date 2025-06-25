#
# settings.py
#
# This file implements helper functions to load and store the plugin's settings.
# Settings are made available in Python through the dictionary "settings" defined
# in this file.
#
# The following requirements are met:
# - Save and load settings to a JSON file on disk
# - Missing top-level keys are set to their default values. This means that
#   existing older settings.json files will automatically be updated to
#   work with newer plugin versions.
# - Only modules from Python's standard library are used, because external
#   modules are not available in Anki's Python environment.
#
# Known limitations are:
# - Non-top-level settings are not checked / initialized with their default
#   values if missing. The application logic has to manually check them
#   before using them.
#
#
# Usage example:
#     from .settings import settings, initializeSettings, saveSettings
#     initializeSettings()        # initialize the settings dictionary
#     settings["example"] = 42    # modify the settings dictionary
#     saveSettings()              # save the changes to disk
#

import dataclasses
import os.path
import json
from typing import Dict

try:
    from PyQt6 import QtCore
except ImportError:
    from PyQt5 import QtCore

_pluginFolder = os.path.dirname(os.path.realpath(__file__))
SETTINGS_PATH = os.path.join(_pluginFolder, "settings.json")

# The settings will be accessible through the following dictionary.
# Note that this is a global variable that can be imported from other files.
settings = {}

# Note that the type annotations are required for the dataclass to work.
@dataclasses.dataclass()
class DefaultSettings:
    # The most recent media import folder used by the user
    loadFolder: str = os.path.expanduser("~")
    # The suffix used to identify secondary images
    secondImageSuffix: str = "_2"
    # For each note type, the most recently used field configurations will be stored
    # in the fieldSettings dictionary.
    # It is structured like this: {Note type -> {Field name -> Configuration}}
    fieldSettings: Dict[str, Dict[str, str]] = dataclasses.field(default_factory=dict)


def initializeSettings():
    """
    Initializes the settings dictionary. Must be called once before the
    settings dictionary can be used.

    If an attribute defined in the DefaultSettings class is missing from the
    settings.json file, it will be initialized to its default value.

    If the settings.json file is missing, all top-level settings will
    be initialized to their default values.
    :return: None
    """
    global settings

    loadedSettings = {}
    if os.path.isfile(SETTINGS_PATH):
        with open(SETTINGS_PATH, "r") as file:
            loadedSettings = json.load(file)

    defaultSettings = dataclasses.asdict(DefaultSettings())

    # Set all settings that are missing to the default settings
    # See https://stackoverflow.com/a/26853961
    mergedSettings = {**defaultSettings, **loadedSettings}

    # insert item-by-item, so that the dict pointer stays the same
    for key in mergedSettings.keys():
        settings[key] = mergedSettings[key]


def saveSettings():
    """
    Must be called after modifying the global "settings" dictionary.
    Writes all settings to disk.
    :return: None
    """
    global settings

    with open(SETTINGS_PATH, "w") as file:
        json.dump(settings, file, indent=4)


if __name__ == "__main__":
    initializeSettings()
    print(settings)
