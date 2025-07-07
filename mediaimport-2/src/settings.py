#
# settings.py
#
# This file implements helper functions to load and store the plugin's settings.
# Settings are made available in Python through the dictionary "settings" defined
# in this file.
# On disk, the settings are stored in two different files:
# - Transient settings, such as the most recent import folder, are stored
#   in ./user_data/transient_settings.json
# - All other settings are passed on to Anki's integrated settings manager.
#   This is mostly useful for debugging, because Anki's debug string indicates
#   if the user changed any default settings.
#   See https://addon-docs.ankiweb.net/addon-config.html
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
#     from .src.settings import settings, initializeSettings, saveSettings
#     initializeSettings()        # initialize the settings dictionary
#     settings["example"] = 42    # modify the settings dictionary
#     saveSettings()              # save the changes to disk
#

import dataclasses
import os
import json
from typing import Dict

try:
    from PyQt6 import QtCore
except ImportError:
    from PyQt5 import QtCore

if __name__ != "__main__":
    from aqt import mw

_pluginFolder = os.path.dirname(os.path.realpath(__file__))
USER_DATA_FOLDER = os.path.join(_pluginFolder, "user_data/")
TRANSIENT_SETTINGS_PATH = os.path.join(USER_DATA_FOLDER, "transient_settings.json")

# The settings will be accessible through the following dictionary.
# Note that this is a global variable that can be imported from other files.
settings = {}

# Note that the type annotations are required for the dataclasses to work.
@dataclasses.dataclass()
class TransientSettings:
    """
    Defines transient settings that are not (directly) set by the user
    """
    # The most recent media import folder used by the user
    loadFolder: str = os.path.expanduser("~")
    includeSubfolders: bool = True
    # For each note type, the most recently used field configurations will be stored
    # in the fieldSettings dictionary.
    # It is structured like this: {Note type -> {Field name -> Configuration}}
    fieldSettings: Dict[str, Dict[str, str]] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass()
class DefaultSettings:
    """
    Defines settings that are directly accessible to the user
    """
    # The suffix used to identify secondary media files
    secondMediaSuffix: str = "_2"
    # Enables the file extension actions
    showExtensionActions: bool = False


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

    defaultTransientSettings = dataclasses.asdict(TransientSettings())
    defaultUserSettings = dataclasses.asdict(DefaultSettings())

    transientSettings = {}
    if os.path.isfile(TRANSIENT_SETTINGS_PATH):
        with open(TRANSIENT_SETTINGS_PATH, "r") as file:
            transientSettings = json.load(file)

    userSettings = {}
    if __name__ != "__main__":
        userSettings = mw.addonManager.getConfig(__name__.split(".")[0])

    # Set all settings that are missing to the default settings
    # See https://stackoverflow.com/a/26853961
    mergedSettings = {**defaultTransientSettings, **defaultUserSettings, **transientSettings, **userSettings}

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

    defaultSettings = dataclasses.asdict(DefaultSettings())
    userSettings = {key: settings[key] for key in defaultSettings.keys()}
    transientSettings = {key: settings[key] for key in settings.keys() if key not in defaultSettings.keys()}

    if __name__ != "__main__":
        mw.addonManager.writeConfig(__name__.split(".")[0], userSettings)

    if not os.path.isdir(USER_DATA_FOLDER):
        os.mkdir(USER_DATA_FOLDER)
    with open(TRANSIENT_SETTINGS_PATH, "w") as file:
        json.dump(transientSettings, file, indent=4)


if __name__ == "__main__":
    initializeSettings()
    print(settings)
