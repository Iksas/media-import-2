# -*- coding: utf-8 -*-
# Version: 3.1.1
#
# This is an Anki add-on for creating notes by importing media files from a
# user-selected folder. The user is able to map properties of the imported
# file to fields in a note type. For example, a user can map the media file
# to the 'Front' field and the file name to the 'Back' field and generate new
# cards from a folder of media files following this pattern. It can create
# decks recursively and with a hierarchical tag structure.
#
# See GitHub page to report issues or to contribute:
# https://github.com/Iksas/media-import-2

import time
import re
from enum import Enum

from aqt import editor, mw
from aqt.utils import tooltip
from aqt.qt import *
from anki import notes

try:
    from PyQt6 import QtCore
except ImportError:
    from PyQt5 import QtCore

from .src.settings import settings, initializeSettings, saveSettings
from .src import dialog

# Support the same media types as the Editor
AUDIO = editor.audio
IMAGE = editor.pics

# Possible field mappings
class Actions(str, Enum):
    nothing = ""
    media = "Media"
    media_2 = "Media_2"
    file_name = "File Name"
    file_name_full = "File Name (full)"
    extension = "Extension"
    extension_case_sensitive = "Extension (case-sensitive)"
    sequence = "Sequence"
    folder_tags_individual = "Subfolder tags (individual)"
    folder_tags_hierarchical = "Subfolder tag (hierarchical)"


# Tooltips for the dropdown menu
ACTION_TOOLTIPS = {
    Actions.nothing: "Nothing",
    Actions.media: "The media file\n(image / audio etc.)",
    Actions.media_2: 'The secondary media file\nThis file is denoted by a suffix ("_2" by default).\ne.g. primary file: "image.jpg" -> secondary file: "image_2.jpg"',
    Actions.file_name: 'The file name without extension\n(e.g. "image.JPG" -> "image")',
    Actions.file_name_full: 'The file name with extension\n(e.g. "image.JPG" -> "image.JPG")',
    Actions.extension: 'The lower-case file extension\n(e.g. "image.JPG" -> "jpg")',
    Actions.extension_case_sensitive: 'The file extension\n(e.g. "image.JPG" -> "JPG")',
    Actions.sequence: 'An increasing number\n("0", "1", "2", ...)',
    Actions.folder_tags_individual: 'Creates one tag for each subfolder\n(e.g. "./f1/f2/f3/image.JPG" -> [f1] [f2] [f3])',
    Actions.folder_tags_hierarchical: 'Creates a single tag from the subfolder path\n(e.g. "./f1/f2/f3/image.JPG" -> [f1::f2::f3])',
}

# Note items that we can import into that are not note fields
SPECIAL_FIELDS = ["Tags"]


def doMediaImport():
    initializeSettings()

    # Raise the main dialog for the add-on and retrieve its result when closed.
    (path, recursive, model, fieldList, ok) = ImportSettingsDialog().getDialogResult()
    if not ok:
        return

    start_time = time.monotonic()
    # Get the MediaImport deck id (auto-created if it doesn't exist)
    did = mw.col.decks.id("MediaImport")

    # Check if secondary media files are used at all
    file_pairs_used = False
    for _, action, _ in fieldList:
        if action == Actions.media_2:
            file_pairs_used = True

    # Walk through the entire directory tree
    newCount = 0
    failure = False
    fileCount = sum([len(files) for _, _, files in os.walk(path)])
    mw.progress.start(max=fileCount, parent=mw, immediate=True)

    for root, dirs, files in os.walk(path):
        # Don't import subfolders if the user disabled them
        if not recursive:
            dirs[:] = []

        # Index primary and secondary files in this folder
        file_pair_suffix = settings["secondImageSuffix"]
        # This dict maps from file names to file names with extensions
        # For example: "image" -> "image.jpg"
        # This avoids a nested loop, and ensures a run time of = O(n*log(n)).
        file_ending_index = {}
        # The two lists will be used to temporarily store file names without extensions.
        primary_media = []
        secondary_media = []
        # Stores if a certain secondary media name has been matched
        # e.g. "image_2" -> True
        secondary_media_matched = {}
        # This dict will map from full primary file names to full secondary file names.
        # e.g. "image.jpg" -> "image_2.png"
        # It will be used by the card creation loop.
        file_pair_index = {}
        if file_pairs_used:
            for fileName in files:
                # Populate the file ending index
                mediaName, ext = os.path.splitext(fileName)
                ext = ext[1:].lower()
                if ext is None or ext not in AUDIO + IMAGE:
                    # Skip files with no extension and non-media files
                    continue
                # TODO: abort on duplicate media names
                file_ending_index[mediaName] = fileName

                # Mark all trivial primary files as primary files
                # This includes all file names that don't end in the file_pair_suffix
                if re.search(f".{re.escape(file_pair_suffix)}$", mediaName, re.MULTILINE):
                    secondary_media.append(mediaName)
                else:
                    primary_media.append(mediaName)

            # Match all trivial primary files with their secondary files
            for pf in primary_media:
                primary_filename = file_ending_index[pf]
                # TODO: abort on nonexistent secondary file
                secondary_filename = file_ending_index[pf + file_pair_suffix]

                file_pair_index[primary_filename] = secondary_filename
                secondary_media_matched[pf + file_pair_suffix] = True

            # Match previously unmatched secondary media with each other
            # e.g. this matches the media "image_2" with "image_2_2"
            #
            # The following steps are taken:
            # - Sort the secondary media names, so that shorter media names are checked first
            # - For each sorted secondary media name:
            #   - Check if the name has been matched
            #   - If not, try to match it
            secondary_media.sort(key=len)
            for pf in secondary_media:
                if pf not in secondary_media_matched:
                    primary_filename = file_ending_index[pf]
                    # TODO: abort on nonexistent secondary file
                    secondary_filename = file_ending_index[pf + file_pair_suffix]

                    file_pair_index[primary_filename] = secondary_filename
                    secondary_media_matched[pf + file_pair_suffix] = True

            files = list(file_pair_index.keys())

        for i, fileName in enumerate(files):
            note = notes.Note(mw.col, model)
            note.note_type()["did"] = did
            mediaName, ext = os.path.splitext(fileName)
            ext = ext[1:].lower()
            filePath = os.path.join(root, fileName)
            if ext is None or ext not in AUDIO + IMAGE:
                # Skip files with no extension and non-media files
                continue

            # Add the file(s) to the media collection and get its name
            internalFileName = mw.col.media.add_file(filePath)
            internalFileName_2 = ""
            if file_pairs_used:
                filePath_2 = os.path.join(root, file_pair_index[fileName])
                internalFileName_2 = mw.col.media.add_file(filePath_2)

            # Now we populate each field according to the mapping selected
            for field, action, special in fieldList:
                if action == Actions.nothing:
                    continue
                elif action == Actions.media:
                    if ext in AUDIO:
                        data = "[sound:%s]" % internalFileName
                    elif ext in IMAGE:
                        data = '<img src="%s">' % internalFileName
                    else:
                        continue
                elif action == Actions.media_2:
                    if ext in AUDIO:
                        data = "[sound:%s]" % internalFileName_2
                    elif ext in IMAGE:
                        data = '<img src="%s">' % internalFileName_2
                    else:
                        continue
                elif action == Actions.file_name:
                    data = mediaName
                elif action == Actions.file_name_full:
                    data = fileName
                elif action == Actions.extension:
                    data = ext
                elif action == Actions.extension_case_sensitive:
                    data = os.path.splitext(mediaName)[1][1:]
                elif action == Actions.sequence:
                    data = str(i)
                elif action == Actions.folder_tags_individual:
                    relative_path = os.path.relpath(root, path)
                    data = relative_path.split(os.sep)
                    if "." in data:
                        data.remove(".")
                elif action == Actions.folder_tags_hierarchical:
                    relative_path = os.path.relpath(root, path)
                    data = relative_path.split(os.sep)
                    if "." in data:
                        data.remove(".")
                    data = "::".join(data)
                else:
                    continue

                if special and field == "Tags":
                    if type(data) is not list:
                        data = [data]
                    for tag in data:
                        note.tags.append(tag.replace(" ", "_"))
                else:
                    if type(data) is list:
                        data = " ".join(data)
                    note[field] = data

            if not mw.col.addNote(note):
                # No cards were generated - probably bad template.
                # No point trying to import anymore.
                failure = True
                break
            newCount += 1
            mw.progress.update(value=newCount)
        if failure:
            break

    mw.progress.finish()
    end_time = time.monotonic()
    tooltip(f"Created {newCount} cards in {end_time - start_time:.2f} seconds.")
    mw.deckBrowser.refresh()
    if failure:
        showFailureDialog()
    else:
        showCompletionDialog(newCount)


class ImportSettingsDialog(QDialog):
    def __init__(self):
        # The path to the media folder chosen by user
        if os.path.isdir(settings["loadFolder"]):
            self.mediaDir = settings["loadFolder"]
        else:
            self.mediaDir = os.path.expanduser("~")
            settings["loadFolder"] = self.mediaDir

        QDialog.__init__(self, mw)
        self.form = dialog.Ui_Form()
        self.form.setupUi(self)
        self.form.buttonBox.accepted.connect(self.accept)
        self.form.buttonBox.rejected.connect(self.reject)
        self.form.browse.clicked.connect(self.onBrowse)
        self.form.recursiveCheckbox.clicked.connect(self.recursiveCheckboxClicked)
        self.recursive = settings["includeSubfolders"]
        # The number of fields in the note type we are using
        self.fieldCount = 0

        # Temporarily stores the field settings for each note type
        # the user edits in the current session.
        # Will not be stored to disk. Only the field settings the user actually
        # uses when starting a media import will be stored to disk.
        self.sessionSettings = {}
        # When no field settings exist for a note type, this default is used
        self.defaultSettings = {"Front": Actions.media, "Image": Actions.media,
                                "Back": Actions.file_name, "Back Extra": Actions.file_name,
                                "Text": Actions.file_name}

        self.populateModelList()
        try:
            self.exec_()
        except AttributeError:
            self.exec()

    def populateModelList(self):
        """Fill in the list of available note types to select from."""
        # TODO: Use the native note type picker instead
        models = mw.col.models.all()
        for m in models:
            item = QListWidgetItem(m["name"])
            # Put the model in the widget to conveniently fetch later
            item.model = m
            self.form.modelList.addItem(item)
        self.form.modelList.sortItems()

        self.form.modelList.currentRowChanged.connect(self.noteTypeChangedCallback)
        # Triggers a selection so the fields will be populated
        self.form.modelList.setCurrentRow(0)

    def noteTypeChangedCallback(self):
        """Fill in the fieldMapGrid QGridLayout.

        Each row in the grid contains two columns:
        Column 0 = QLabel with name of field
        Column 1 = QComboBox with selection of mappings ("actions")
        The first two fields will default to Media and File Name, so we have
        special cases for rows 0 and 1. The final row is a spacer."""

        self.clearLayout(self.form.fieldMapGrid)
        noteType = self.form.modelList.currentItem().model["name"]

        # Add note fields to grid
        row = 0
        for field in self.form.modelList.currentItem().model["flds"]:
            self.createRow(field["name"], row)
            row += 1

        # Add special fields to grid
        for name in SPECIAL_FIELDS:
            self.createRow(name, row, special=True)
            row += 1
        self.fieldCount = row

        transientSettings = {}
        if noteType in settings["fieldSettings"]:
            transientSettings = settings["fieldSettings"][noteType]

        # Merge stored field settings with the default settings
        fieldSessionSettings = {}
        if noteType in self.sessionSettings:
            fieldSessionSettings = self.sessionSettings[noteType]

        # See https://stackoverflow.com/a/26853961
        fieldSettings = {**self.defaultSettings, **transientSettings, **fieldSessionSettings}

        # Apply stored field settings
        for i in range(self.fieldCount):
            lbl: QLabel
            cmb: QComboBox
            lbl = self.form.fieldMapGrid.itemAtPosition(i, 0).widget()
            cmb = self.form.fieldMapGrid.itemAtPosition(i, 1).widget()

            fieldName = lbl.text()
            if fieldName not in fieldSettings:
                # This field doesn't have a stored setting
                continue

            fieldSetting = fieldSettings[fieldName]
            settingsIndex = cmb.findText(fieldSetting)
            if settingsIndex >= 0:
                cmb.setCurrentIndex(settingsIndex)

        # Add a flexible spacer below the dropdown menus
        try:
            self.form.fieldMapGrid.addItem(
                QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding), row, 0
            )
        except AttributeError:
            self.form.fieldMapGrid.addItem(
                QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding), row, 0,
            )

    def fieldSettingChangedCallback(self, field, setting):
        """
        Callback that stores changed field settings in the sessionSettings dicionary

        :param field: The field name (str or Action)
        :param setting: The field text selected by the user
        :return: None
        """
        noteType = self.form.modelList.currentItem().model["name"]
        if noteType not in self.sessionSettings:
            self.sessionSettings[noteType] = {}
        self.sessionSettings[noteType][field] = setting

    def createRow(self, name, idx, special=False):
        lbl = QLabel(name)
        cmb = QComboBox(None)

        # Add the actions to the dropdown menu, and add tooltips
        for action in Actions:
            # Tags cannot store media
            if name == "Tags" and action == Actions.media:
                continue
            cmb.addItem(action)
            if action in ACTION_TOOLTIPS:
                cmb.setItemData(cmb.count()-1, ACTION_TOOLTIPS[action], QtCore.Qt.ItemDataRole.ToolTipRole)

        # Register a callback function for combobox index changes
        cmb.currentTextChanged.connect(lambda setting, field=name: self.fieldSettingChangedCallback(field, setting))

        # piggyback the special flag on QLabel
        lbl.special = special
        self.form.fieldMapGrid.addWidget(lbl, idx, 0)
        self.form.fieldMapGrid.addWidget(cmb, idx, 1)

    def getDialogResult(self):
        """Return a tuple containing the user-defined settings to follow
        for an import. The tuple contains four items (in order):
         - Path to chosen media folder
         - The model (note type) to use for new notes
         - A dictionary that maps each of the fields in the model to an
           integer index from the ACTIONS list
         - True/False indicating whether the user clicked OK/Cancel"""

        try:
            if self.result() == QDialog.Rejected:
                return None, False, None, None, False
        except AttributeError:
            if self.result() == QDialog.DialogCode.Rejected:
                return None, False, None, None, False

        model = self.form.modelList.currentItem().model
        # Iterate the grid rows to populate the field map
        fieldList = []
        grid = self.form.fieldMapGrid
        for row in range(self.fieldCount):
            # QLabel with field name
            field = grid.itemAtPosition(row, 0).widget().text()
            # Piggybacked special flag
            special = grid.itemAtPosition(row, 0).widget().special
            # QComboBox with currently displayed text
            actionText = grid.itemAtPosition(row, 1).widget().currentText()
            fieldList.append((field, actionText, special))
        return self.mediaDir, self.recursive, model, fieldList, True

    def onBrowse(self):
        """Show the file picker."""
        path = QFileDialog.getExistingDirectory(mw, caption="Import Folder", directory=self.mediaDir)
        if not path:
            return
        self.mediaDir = path
        self.form.mediaDir.setText(self.mediaDir)
        self.form.mediaDir.setStyleSheet("")

    def recursiveCheckboxClicked(self, value: bool):
        self.recursive = value

    def accept(self):
        # Show a red warning box if the user tries to import without selecting
        # a media folder.
        if not self.mediaDir:
            self.form.mediaDir.setStyleSheet("border: 1px solid red")
            return

        # The dialog will be accepted.
        # Store the settings of the current field type to disk.
        noteType = self.form.modelList.currentItem().model["name"]

        transientSettings = {}
        for i in range(self.fieldCount):
            lbl: QLabel
            cmb: QComboBox
            lbl = self.form.fieldMapGrid.itemAtPosition(i, 0).widget()
            cmb = self.form.fieldMapGrid.itemAtPosition(i, 1).widget()

            fieldName = lbl.text()
            fieldSetting = cmb.currentText()
            transientSettings[fieldName] = fieldSetting
        # TODO: store the settings immediately after an import operation is started
        settings["fieldSettings"][noteType] = transientSettings
        settings["loadFolder"] = self.mediaDir
        settings["includeSubfolders"] = self.recursive
        saveSettings()

        QDialog.accept(self)

    def clearLayout(self, layout):
        """Convenience method to remove child widgets from a layout."""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget() is not None:
                child.widget().deleteLater()
            elif child.layout() is not None:
                self.clearLayout(child.layout())


def showCompletionDialog(newCount):
    QMessageBox.about(
        mw,
        "Media Import Complete",
        """
<p>
Media import is complete and %s new notes were created.
All generated cards are placed in the <b>MediaImport</b> deck.
<br><br>
Please refer to the introductory videos for instructions on
<a href="https://www.youtube.com/watch?v=DnbKwHEQ1mA">flipping card content</a> or
<a href="https://www.youtube.com/watch?v=F1j1Zx0mXME">modifying the appearance of cards.</a>
</p>"""
        % newCount,
    )


def showFailureDialog():
    QMessageBox.about(
        mw,
        "Media Import Failure",
        """
<p>
Failed to generate cards and no media files were imported. Please ensure the
note type you selected is able to generate cards by using a valid
<a href="https://docs.ankiweb.net/templates/intro.html">card template</a>.
</p>
""",
    )


action = QAction("Media Import 2...", mw)
action.triggered.connect(doMediaImport)  # noqa
mw.form.menuTools.addAction(action)
