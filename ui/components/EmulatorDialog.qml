import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

Dialog {
    id: emulatorDialog
    title: ""
    modal: true
    standardButtons: Dialog.NoButton
    background: Rectangle { color: "transparent"; border.color: "transparent" }
    width: 780
    height: 560
    x: Math.round(((parent ? parent.width : 0) - width) / 2)
    y: Math.round(((parent ? parent.height : 0) - height) / 2)
    Behavior on width { NumberAnimation { duration: 60; easing.type: Easing.OutCubic } }
    Behavior on height { NumberAnimation { duration: 60; easing.type: Easing.OutCubic } }

    property var backendRef
    property var appRootRef
    property var resizeComponent
    property var errorDialogRef

    onOpened: {
        appRootRef.emulatorKeys = Object.keys(backendRef.emulatorsData || {})
        appRootRef.selectedEmulatorId = appRootRef.emulatorKeys.length > 0 ? appRootRef.emulatorKeys[0] : ""
        loadEmulatorFields()
        settingsStack.currentIndex = 0
    }

    contentItem: Rectangle {
        color: "#1e1f25"
        radius: 8
        border.color: "#2a2a2a"
        width: emulatorDialog.width
        height: emulatorDialog.height
        implicitWidth: 780
        implicitHeight: 560
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
                startDialogX = emulatorDialog.x
                startDialogY = emulatorDialog.y
            }
            onPositionChanged: function(mouse) {
                if (!pressed)
                    return
                emulatorDialog.x = Math.round(emulatorDialog.x + ((startDialogX + (mouse.x - startX)) - emulatorDialog.x) * 0.35)
                emulatorDialog.y = Math.round(emulatorDialog.y + ((startDialogY + (mouse.y - startY)) - emulatorDialog.y) * 0.35)
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 12

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "#141414"
                    radius: 6
                    border.color: "transparent"

                    StackLayout {
                        id: settingsStack
                        anchors.fill: parent
                        anchors.margins: 12
                        currentIndex: 0

                        Item {
                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 8

                                RowLayout {
                                    Layout.fillWidth: true
                                    CrispText { text: "Configure Emulators"; color: "#f0f0f0"; font.bold: true }
                                    Item { Layout.fillWidth: true }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    spacing: 12

                                    Rectangle {
                                        Layout.preferredWidth: 300
                                        Layout.fillHeight: true
                                        color: "#18191f"
                                        radius: 6
                                        border.color: "transparent"

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 10
                                            spacing: 8

                                            CrispText { text: "Emulators"; color: "#d6d6d6"; font.bold: true }

                                            ListView {
                                                id: emulatorList
                                                Layout.fillWidth: true
                                                Layout.fillHeight: true
                                                clip: true
                                                model: appRootRef.emulatorKeys
                                                delegate: Rectangle {
                                                    width: emulatorList.width
                                                    height: 36
                                                    color: appRootRef.selectedEmulatorId === modelData ? "#7c7436" : "transparent"
                                                    radius: 4
                                                    CrispText {
                                                        anchors.centerIn: parent
                                                        text: modelData
                                                        color: "#eaeaea"
                                                        font.pointSize: 10
                                                        font.bold: appRootRef.selectedEmulatorId === modelData
                                                    }
                                                    MouseArea {
                                                        anchors.fill: parent
                                                        onClicked: {
                                                            appRootRef.selectedEmulatorId = modelData
                                                            loadEmulatorFields()
                                                        }
                                                    }
                                                }
                                            }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: 6
                                                StyledButton {
                                                    text: "Add"
                                                    Layout.preferredWidth: 90
                                                    onClicked: {
                                                        appRootRef.selectedEmulatorId = ""
                                                        emulatorNameField.text = ""
                                                        appRootRef.emulatorTypeSyncing = true
                                                        emulatorTypeField.currentIndex = 0
                                                        appRootRef.emulatorTypeSyncing = false
                                                        emulatorExeField.text = ""
                                                        appRootRef.emulatorExePathsDraft = ({})
                                                        appRootRef.emulatorTypeLast = "executable"
                                                        emulatorFlatpakField.text = ""
                                                        emulatorArgsField.text = ""
                                                        emulatorExtensionsField.text = ""
                                                        emulatorRomDirsField.text = ""
                                                        emulatorPlatformCombo.currentIndex = 0
                                                        emulatorNameField.forceActiveFocus()
                                                    }
                                                }
                                                StyledButton {
                                                    text: "Copy"
                                                    Layout.preferredWidth: 90
                                                    onClicked: {
                                                        var newName = emulatorNameField.text + " Copy"
                                                        backendRef.add_emulator(
                                                            newName,
                                                            emulatorTypeField.currentText.toLowerCase(),
                                                            emulatorExeField.text,
                                                            emulatorArgsField.text,
                                                            emulatorPlatformCombo.currentText,
                                                            emulatorExtensionsField.text,
                                                            emulatorRomDirsField.text,
                                                            emulatorFlatpakField.text
                                                        )
                                                        appRootRef.refreshEmulators()
                                                    }
                                                }
                                                StyledButton {
                                                    text: "Remove"
                                                    Layout.preferredWidth: 90
                                                    onClicked: {
                                                        if (appRootRef.selectedEmulatorId === "")
                                                            return
                                                        backendRef.remove_emulator(appRootRef.selectedEmulatorId)
                                                        appRootRef.refreshEmulators()
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        Layout.preferredHeight: 400
                                        color: "#18191f"
                                        radius: 6
                                        border.color: "transparent"

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 12
                                            spacing: 10

                                            RowLayout {
                                                Layout.fillWidth: true
                                                CrispText { text: "Name"; color: "#ffffff" }
                                                TextField { id: emulatorNameField; Layout.fillWidth: true }
                                            }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                CrispText { text: "Emulator Specification"; color: "#d6d6d6" }
                                                ComboBox {
                                                    id: emulatorTypeField
                                                    model: backendRef.isWindows ? ["Executable"] : ["AppImage", "Flatpak"]
                                                    Layout.fillWidth: true
                                                    onCurrentIndexChanged: {
                                                        if (appRootRef.emulatorTypeSyncing)
                                                            return
                                                        var prevType = appRootRef.emulatorTypeLast
                                                        if (prevType)
                                                            appRootRef.emulatorExePathsDraft[prevType] = emulatorExeField.text
                                                        var currentType = appRootRef.normalizeLaunchType(emulatorTypeField.currentText)
                                                        appRootRef.emulatorTypeLast = currentType
                                                        emulatorExeField.text = appRootRef.emulatorExePathsDraft[currentType] || ""
                                                    }
                                                }
                                            }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                CrispText { text: "Executable"; color: "#d6d6d6" }
                                                TextField { id: emulatorExeField; Layout.fillWidth: true }
                                                StyledButton {
                                                    text: "Browse"
                                                    onClicked: appRootRef.openFileDialog(emulatorExeField, "Executable (*.exe *.AppImage);;All files (*)")
                                                }
                                            }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                visible: emulatorTypeField.currentText === "Flatpak"
                                                CrispText { text: "Flatpak ID"; color: "#d6d6d6" }
                                                TextField { id: emulatorFlatpakField; Layout.fillWidth: true }
                                            }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                CrispText { text: "Custom Arguments"; color: "#d6d6d6" }
                                                TextField { id: emulatorArgsField; Layout.fillWidth: true; placeholderText: "-fullscreen -batch -- {rom}" }
                                            }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                CrispText { text: "Platform"; color: "#d6d6d6" }
                                                ComboBox {
                                                    id: emulatorPlatformCombo
                                                    model: appRootRef.platformOptions
                                                    Layout.fillWidth: true
                                                }
                                            }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                CrispText { text: "Supported File Types"; color: "#d6d6d6" }
                                                TextField { id: emulatorExtensionsField; Layout.fillWidth: true; placeholderText: ".iso,.bin" }
                                            }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                CrispText { text: "ROM Directories"; color: "#d6d6d6" }
                                                TextField { id: emulatorRomDirsField; Layout.fillWidth: true; placeholderText: "D:/Roms/PS2, E:/Roms/PS2" }
                                            }

                                            Item { Layout.fillHeight: true }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                Item { Layout.fillWidth: true }
                                                StyledButton {
                                                    text: "Save"
                                                    Layout.preferredWidth: 100
                                                    onClicked: {
                                                        if (!emulatorNameField.text) {
                                                            errorDialogRef.message = "Please enter an emulator name."
                                                            errorDialogRef.open()
                                                            return
                                                        }
                                                        if (appRootRef.selectedEmulatorId === "") {
                                                        backendRef.add_emulator(
                                                            emulatorNameField.text,
                                                            emulatorTypeField.currentText.toLowerCase(),
                                                            emulatorExeField.text,
                                                            emulatorArgsField.text,
                                                            emulatorPlatformCombo.currentText,
                                                            emulatorExtensionsField.text,
                                                            emulatorRomDirsField.text,
                                                            emulatorFlatpakField.text
                                                        )
                                                        } else {
                                                        backendRef.update_emulator_fields(
                                                            appRootRef.selectedEmulatorId,
                                                            emulatorNameField.text,
                                                            emulatorTypeField.currentText.toLowerCase(),
                                                            emulatorExeField.text,
                                                            emulatorArgsField.text,
                                                            emulatorPlatformCombo.currentText,
                                                            emulatorExtensionsField.text,
                                                            emulatorRomDirsField.text,
                                                            emulatorFlatpakField.text
                                                        )
                                                        }
                                                        appRootRef.refreshEmulators()
                                                        appRootRef.selectedEmulatorId = emulatorNameField.text
                                                    }
                                                }
                                                StyledButton {
                                                    text: "Cancel"
                                                    Layout.preferredWidth: 100
                                                    onClicked: {
                                                        loadEmulatorFields()
                                                        emulatorDialog.close()
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                    Item { Layout.fillHeight: true }
                            }
                        }
                    }
                }
            }
        }
        Loader {
            anchors.fill: parent
            sourceComponent: emulatorDialog.resizeComponent
            onLoaded: {
                item.dialogRef = emulatorDialog
                item.minWidth = 640
                item.minHeight = 460
            }
        }
    }

    function loadEmulatorFields() {
        var emu = (backendRef.emulatorsData || {})[appRootRef.selectedEmulatorId]
        if (!emu) {
            emulatorNameField.text = ""
            appRootRef.emulatorTypeSyncing = true
            emulatorTypeField.currentIndex = 0
            appRootRef.emulatorTypeSyncing = false
            emulatorExeField.text = ""
            emulatorFlatpakField.text = ""
            emulatorArgsField.text = ""
            emulatorExtensionsField.text = ""
            emulatorRomDirsField.text = ""
            appRootRef.emulatorExePathsDraft = ({})
            appRootRef.emulatorTypeLast = "executable"
            return
        }
        emulatorNameField.text = emu.name || ""
        var type = (emu.launch_type || "exe").toLowerCase()
        if (backendRef.isWindows && emu.launch_type_windows)
            type = (emu.launch_type_windows || type).toLowerCase()
        if (backendRef.isLinux && emu.launch_type_linux)
            type = (emu.launch_type_linux || type).toLowerCase()
        appRootRef.emulatorExePathsDraft = emu.exe_paths && typeof emu.exe_paths === "object" ? emu.exe_paths : ({})
        var normalizedType = appRootRef.normalizeLaunchType(type)
        emulatorExeField.text = appRootRef.getExePathForType(emu, normalizedType)
        appRootRef.emulatorTypeLast = normalizedType
        appRootRef.emulatorTypeSyncing = true
        if (type === "flatpak")
            emulatorTypeField.currentIndex = 2
        else if (type === "appimage")
            emulatorTypeField.currentIndex = 1
        else
            emulatorTypeField.currentIndex = 0
        appRootRef.emulatorTypeSyncing = false
        emulatorFlatpakField.text = emu.flatpak_id || ""
        emulatorArgsField.text = emu.args_template || ""
        if (emu.platforms && emu.platforms.length > 0) {
            var idx = appRootRef.platformOptions.indexOf(emu.platforms[0])
            emulatorPlatformCombo.currentIndex = idx >= 0 ? idx : 0
        } else {
            emulatorPlatformCombo.currentIndex = 0
        }
        emulatorExtensionsField.text = (emu.rom_extensions || []).join(", ")
        emulatorRomDirsField.text = (emu.rom_dirs || []).join(", ")
    }
}
