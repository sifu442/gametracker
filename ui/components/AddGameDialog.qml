import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

Dialog {
    id: addDialog
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
    property alias details: addDetails

    onOpened: {
        addDetails.nameField.text = ""
        addDetails.genreValue.text = ""
        addDetails._setGenresFromString("")
        addDetails.developersField.editText = ""
        addDetails.publishersField.editText = ""
        addDetails.categoriesField.editText = ""
        addDetails.platformField.currentIndex = -1
        addDetails.platformField.editText = ""
        addDetails.playtimeField.text = "0"
        addDetails.notesField.text = ""
        addDetails.serialField.text = ""
        addExeWinField.text = ""
        addExeLinuxField.text = ""
        addDetails.exePathField.text = ""
        addDetails.launchOptionsField.text = ""
        addDetails.winePrefixField.text = ""
        addDetails.wineEsyncCheck.checked = false
        addDetails.wineFsyncCheck.checked = false
        addDetails.protonWaylandCheck.checked = false
        addDetails.protonDiscordRichPresenceCheck.checked = false
        addDetails.windowsOnlyCheck.checked = false
        addDetails.installedCheck.checked = false
        addDetails.coverField.text = ""
        addDetails.logoField.text = ""
        addDetails.heroField.text = ""
        addDetails.compatCombo.currentIndex = appRootRef.compatIndex("", "")
        addDetails.compatToolField.text = ""
        addDetails.protonPathField.text = ""
        addDetails.envVarsField.text = ""
        addDetails.emulatedCheck.checked = false
        addDetails.emulatorCombo.currentIndex = 0
        addDetails.romField.text = ""
        addDetails.gameIdField.text = ""
        addDetails.firstPlayedField.text = ""
        addDetails.lastPlayedField.text = ""
        addDetails.loadLinksFromJson("[]")
    }

    onAccepted: {
        backendRef.add_game_full(
            addDetails.nameField.text,
            addDetails.genreValue.text,
            addDetails.platformField.editText || addDetails.platformField.currentText,
            addDetails.developersField.editText || addDetails.developersField.currentText,
            addDetails.publishersField.editText || addDetails.publishersField.currentText,
            addDetails.categoriesField.editText || addDetails.categoriesField.currentText,
            parseInt(addDetails.playtimeField.text || "0"),
            addDetails.notesField.text,
            addDetails.serialField.text,
            addDetails.exePathField.text,
            addDetails.exePathField.text,
            "",
            addDetails.launchOptionsField.text,
            addDetails.winePrefixField.text,
            addDetails.envVarsField.text,
            addDetails.wineEsyncCheck.checked,
            addDetails.wineFsyncCheck.checked,
            addDetails.protonWaylandCheck.checked,
            addDetails.protonDiscordRichPresenceCheck.checked,
            addDetails.windowsOnlyCheck.checked,
            addDetails.installedCheck.checked,
            addDetails.coverField.text,
            addDetails.logoField.text,
            addDetails.heroField.text,
            addDetails.compatToolField.text,
            addDetails.protonPathField.text,
            addDetails.emulatedCheck.checked,
            addDetails.emulatorCombo.currentText,
            addDetails.romField.text,
            addDetails.linksJsonField.text,
            addDetails.firstPlayedField.text,
            addDetails.lastPlayedField.text
        )
    }

    contentItem: Rectangle {
        color: "#1e1f25"
        radius: 8
        border.color: "#2a2a2a"
        width: addDialog.width
        height: addDialog.height
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
                startDialogX = addDialog.x
                startDialogY = addDialog.y
            }
            onPositionChanged: function(mouse) {
                if (!pressed)
                    return
                addDialog.x = Math.round(addDialog.x + ((startDialogX + (mouse.x - startX)) - addDialog.x) * 0.35)
                addDialog.y = Math.round(addDialog.y + ((startDialogY + (mouse.y - startY)) - addDialog.y) * 0.35)
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            CrispText {
                text: "Add Game Details"
                color: "#f0f0f0"
                font.pointSize: 14
                font.bold: true
            }

            TabBar {
                id: addTabs
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

            TextField { id: addExeWinField; visible: false }
            TextField { id: addExeLinuxField; visible: false }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#202129"
                radius: 6
                border.color: "transparent"

                GameDetailsTabs {
                    id: addDetails
                    anchors.fill: parent
                    currentIndex: addTabs.currentIndex
                    backend: backendRef
                    openFileDialog: appRootRef.openFileDialog
                    openFolderDialog: appRootRef.openFolderDialog
                    openUrlDialog: appRootRef.openUrlDialog
                    emulatorKeys: appRootRef.emulatorKeys
                    platformOptions: appRootRef.platformOptions
                    useBackendFallback: false
                    showInstalledLocation: false
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                StyledButton {
                    text: "Download Metadata..."
                    Layout.preferredWidth: 220
                    onClicked: {
                        appRootRef.metadataTarget = "add"
                        igdbDialogRef.queryText = addDetails.nameField.text || ""
                        igdbDialogRef.open()
                        igdbDebounceRef.restart()
                    }
                }
                Item { Layout.fillWidth: true }
                StyledButton { text: "Save" ; onClicked: addDialog.accept() }
                StyledButton { text: "Cancel" ; onClicked: addDialog.reject() }
            }
        }
        Loader {
            anchors.fill: parent
            sourceComponent: addDialog.resizeComponent
            onLoaded: {
                item.dialogRef = addDialog
                item.minWidth = 720
                item.minHeight = 520
            }
        }
    }
}
