import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

Dialog {
    id: editDialog
    title: ""
    modal: true
    standardButtons: Dialog.NoButton
    background: Rectangle { color: "transparent"; border.color: "transparent" }
    width: 900
    height: 680
    x: Math.round(((parent ? parent.width : 0) - width) / 2)
    y: Math.round(((parent ? parent.height : 0) - height) / 2)
    Behavior on width { NumberAnimation { duration: 60; easing.type: Easing.OutCubic } }
    Behavior on height { NumberAnimation { duration: 60; easing.type: Easing.OutCubic } }

    property var backendRef
    property var appRootRef
    property var resizeComponent
    property var igdbDialogRef
    property var igdbDebounceRef
    property var errorDialogRef
    property alias details: editDetails

    onOpened: {
        appRootRef.refreshEmulators()
        editDetails.nameField.text = backendRef.selectedGameName
        editDetails._setGenresFromString(backendRef.selectedGameGenre)
        editDetails.developersField.text = backendRef.selectedGameDevelopers
        editDetails.publishersField.text = backendRef.selectedGamePublishers
        editDetails.categoriesField.text = backendRef.selectedGameCategories
        editDetails.platformField.currentIndex = appRootRef.platformIndex(backendRef.selectedGamePlatform)
        editDetails.platformField.editText = backendRef.selectedGamePlatform
        editDetails.playtimeField.text = backendRef.selectedGamePlaytimeMinutes.toString()
        editDetails.notesField.text = backendRef.selectedGameNotes
        editDetails.serialField.text = backendRef.selectedGameSerial
        editExeWinField.text = backendRef.selectedGameExeWindows
        editExeLinuxField.text = backendRef.selectedGameExeLinux
        var defaultPrefix = ""
        if (Qt.platform.os === "linux" && !backendRef.selectedGameIsEmulated) {
            var rawName = backendRef.selectedGameName || "Game"
            var safeName = rawName.replace(/[^A-Za-z0-9._-]/g, "_").replace(/^_+|_+$/g, "")
            defaultPrefix = "~/.local/share/gametracker/Prefixes/" + (safeName || "Game")
        }
        editDetails.winePrefixField.text = backendRef.selectedGameWinePrefix || defaultPrefix
        editDetails.envVarsField.text = backendRef.selectedGameEnvVars
        editDetails.wineEsyncCheck.checked = backendRef.selectedGameWineEsync
        editDetails.wineFsyncCheck.checked = backendRef.selectedGameWineFsync
        editDetails.protonWaylandCheck.checked = backendRef.selectedGameProtonWayland
        editDetails.protonDiscordRichPresenceCheck.checked = backendRef.selectedGameProtonDiscordRichPresence
        editDetails.windowsOnlyCheck.checked = backendRef.selectedGameWindowsOnly
        editDetails.installedCheck.checked = backendRef.selectedGameInstalledFlag
        editDetails.coverField.text = backendRef.selectedGameCover
        editDetails.logoField.text = backendRef.selectedGameLogo
        editDetails.heroField.text = backendRef.selectedGameHero
        editDetails.exePathField.text = backendRef.selectedGameExeWindows || ""
        editDetails.emulatedCheck.checked = backendRef.selectedGameIsEmulated
        editDetails.romField.text = backendRef.selectedGameRomPath
        editDetails.emulatorCombo.currentIndex = appRootRef.emulatorIndex(backendRef.selectedGameEmulatorId)
        editDetails.compatCombo.currentIndex = appRootRef.compatIndex(
            backendRef.selectedGameCompatTool,
            backendRef.selectedGameProtonPath
        )
        editDetails.compatToolField.text = backendRef.selectedGameCompatTool
        editDetails.protonPathField.text = backendRef.selectedGameProtonPath
        editDetails.launchOptionsField.text = backendRef.selectedGameLaunchOptions
        editDetails.gameIdField.text = backendRef.selectedGameId
        editDetails.firstPlayedField.text = backendRef.selectedGameFirstPlayedDate
        editDetails.lastPlayedField.text = backendRef.selectedGameLastPlayedDate
        editDetails.loadLinksFromJson(backendRef.selectedGameLinksJson)
    }

    onAccepted: {
        backendRef.update_selected_full(
            editDetails.nameField.text,
            editDetails.genreValue.text,
            editDetails.platformField.editText || editDetails.platformField.currentText,
            editDetails.developersField.editText || editDetails.developersField.currentText,
            editDetails.publishersField.editText || editDetails.publishersField.currentText,
            editDetails.categoriesField.editText || editDetails.categoriesField.currentText,
            parseInt(editDetails.playtimeField.text || "0"),
            editDetails.notesField.text,
            editDetails.serialField.text,
            editDetails.exePathField.text,
            editDetails.exePathField.text,
            "",
            editDetails.launchOptionsField.text,
            editDetails.winePrefixField.text,
            editDetails.envVarsField.text,
            editDetails.wineEsyncCheck.checked,
            editDetails.wineFsyncCheck.checked,
            editDetails.protonWaylandCheck.checked,
            editDetails.protonDiscordRichPresenceCheck.checked,
            editDetails.windowsOnlyCheck.checked,
            editDetails.installedCheck.checked,
            editDetails.coverField.text,
            editDetails.logoField.text,
            editDetails.heroField.text,
            editDetails.compatToolField.text,
            editDetails.protonPathField.text,
            editDetails.linksJsonField.text,
            editDetails.firstPlayedField.text,
            editDetails.lastPlayedField.text
        )
        backendRef.update_selected_emulation(
            editDetails.emulatedCheck.checked,
            editDetails.emulatorCombo.currentText,
            editDetails.romField.text
        )
    }

    contentItem: Rectangle {
        color: "#1e1f25"
        radius: 8
        border.color: "#2a2a2a"
        width: editDialog.width
        height: editDialog.height
        implicitWidth: 900
        implicitHeight: 620
        MouseArea {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 32
            cursorShape: Qt.SizeAllCursor
            property real startX
            property real startY
            property real startDialogX
            property real startDialogY
            onPressed: function(mouse) {
                startX = mouse.x
                startY = mouse.y
                startDialogX = editDialog.x
                startDialogY = editDialog.y
            }
            onPositionChanged: function(mouse) {
                if (!pressed)
                    return
                editDialog.x = Math.round(editDialog.x + ((startDialogX + (mouse.x - startX)) - editDialog.x) * 0.35)
                editDialog.y = Math.round(editDialog.y + ((startDialogY + (mouse.y - startY)) - editDialog.y) * 0.35)
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            CrispText {
                text: "Edit Game Details"
                color: "#f0f0f0"
                font.pointSize: 14
                font.bold: true
            }

            TabBar {
                id: editTabs
                Layout.fillWidth: true
                background: Rectangle { color: "#1e1f25" }
                TabButton { text: "General" }
                TabButton { text: "Advanced" }
                TabButton { text: "Media" }
                TabButton { text: "Links" }
                TabButton { text: "Installation" }
                TabButton { text: "Actions" }
                TabButton { text: "Scripts" }
            }

            TextField { id: editExeWinField; visible: false }
            TextField { id: editExeLinuxField; visible: false }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#202129"
                radius: 6
                border.color: "transparent"

                GameDetailsTabs {
                    id: editDetails
                    anchors.fill: parent
                    currentIndex: editTabs.currentIndex
                    backend: backendRef
                    openFileDialog: appRootRef.openFileDialog
                    openFolderDialog: appRootRef.openFolderDialog
                    openUrlDialog: appRootRef.openUrlDialog
                    emulatorKeys: appRootRef.emulatorKeys
                    platformOptions: appRootRef.platformOptions
                    useBackendFallback: true
                    showInstalledLocation: true
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                StyledButton {
                    text: "Download Metadata..."
                    Layout.preferredWidth: 220
                    onClicked: {
                        appRootRef.metadataTarget = "edit"
                        igdbDialogRef.queryText = editDetails.nameField.text || ""
                        igdbDialogRef.open()
                        igdbDebounceRef.restart()
                    }
                }
                Item { Layout.fillWidth: true }
                StyledButton {
                    text: "Save"
                    onClicked: {
                        if (!backendRef.selectedGameId) {
                            errorDialogRef.message = "No game selected."
                            errorDialogRef.open()
                            return
                        }
                        backendRef.update_selected_full(
                            editDetails.nameField.text,
                            editDetails.genreValue.text,
                            editDetails.platformField.editText || editDetails.platformField.currentText,
                            editDetails.developersField.editText || editDetails.developersField.currentText,
                            editDetails.publishersField.editText || editDetails.publishersField.currentText,
                            editDetails.categoriesField.editText || editDetails.categoriesField.currentText,
                            parseInt(editDetails.playtimeField.text || "0"),
                            editDetails.notesField.text,
                            editDetails.serialField.text,
                            editExeWinField.text,
                            editExeLinuxField.text,
                            "",
                            editDetails.launchOptionsField.text,
                            editDetails.winePrefixField.text,
                            editDetails.envVarsField.text,
                            editDetails.wineEsyncCheck.checked,
                            editDetails.wineFsyncCheck.checked,
                            editDetails.protonWaylandCheck.checked,
                            editDetails.protonDiscordRichPresenceCheck.checked,
                            editDetails.windowsOnlyCheck.checked,
                            editDetails.installedCheck.checked,
                            editDetails.coverField.text,
                            editDetails.logoField.text,
                            editDetails.heroField.text,
                            editDetails.compatToolField.text,
                            editDetails.protonPathField.text,
                            editDetails.linksJsonField.text,
                            editDetails.firstPlayedField.text,
                            editDetails.lastPlayedField.text
                        )
                        backendRef.update_selected_emulation(
                            editDetails.emulatedCheck.checked,
                            editDetails.emulatorCombo.currentText,
                            editDetails.romField.text
                        )
                        editDialog.close()
                    }
                }
                StyledButton { text: "Cancel" ; onClicked: editDialog.reject() }
            }
        }
        Loader {
            anchors.fill: parent
            sourceComponent: editDialog.resizeComponent
            onLoaded: {
                item.dialogRef = editDialog
                item.minWidth = 720
                item.minHeight = 520
            }
        }
    }
}
