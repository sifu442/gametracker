import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "."

Dialog {
    id: steamEmuLocationsDialog
    title: ""
    modal: true
    standardButtons: Dialog.NoButton
    background: Rectangle { color: "transparent"; border.color: "transparent" }
    width: 860
    height: 520
    x: Math.round(((parent ? parent.width : 0) - width) / 2)
    y: Math.round(((parent ? parent.height : 0) - height) / 2)

    property var backendRef

    ListModel { id: defaultRootsModel }
    ListModel { id: customRootsModel }

    function reloadRoots() {
        defaultRootsModel.clear()
        customRootsModel.clear()
        var defaults = backendRef ? (backendRef.steamEmuDefaultRoots || []) : []
        var custom = backendRef ? (backendRef.steamEmuCustomRoots || []) : []
        for (var i = 0; i < defaults.length; i++)
            defaultRootsModel.append({ "path": defaults[i] })
        for (var j = 0; j < custom.length; j++)
            customRootsModel.append({ "path": custom[j] })
    }

    function toLocalPath(url) {
        if (!url)
            return ""
        var s = url.toString()
        if (s.startsWith("file:///"))
            return s.slice(8)
        if (s.startsWith("file://"))
            return s.slice(7)
        return s
    }

    onOpened: reloadRoots()

    FolderDialog {
        id: addFolderDialog
        onAccepted: {
            var picked = selectedFolder
            var localPath = toLocalPath(picked)
            backendRef.add_steam_emu_custom_root(localPath)
            reloadRoots()
        }
    }

    Connections {
        target: backendRef
        function onSteamEmuRootsChanged() {
            steamEmuLocationsDialog.reloadRoots()
        }
    }

    contentItem: Rectangle {
        color: "#1e1f25"
        radius: 8
        border.color: "#2a2a2a"
        width: steamEmuLocationsDialog.width
        height: steamEmuLocationsDialog.height

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            CrispText {
                text: "SteamEmu Locations"
                color: "#f0f0f0"
                font.bold: true
                font.pointSize: 13
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 10

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 6
                    color: "#161821"
                    border.color: "#2a2a2a"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 6
                        CrispText { text: "Default (read-only)"; color: "#e8e8e8"; font.bold: true }
                        ListView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            model: defaultRootsModel
                            clip: true
                            delegate: Rectangle {
                                width: ListView.view.width
                                height: 30
                                color: "transparent"
                                CrispText {
                                    text: model.path
                                    color: "#cfd3dc"
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left
                                    anchors.leftMargin: 6
                                    elide: Text.ElideMiddle
                                    width: parent.width - 12
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 6
                    color: "#161821"
                    border.color: "#2a2a2a"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 6
                        CrispText { text: "Custom"; color: "#e8e8e8"; font.bold: true }
                        ListView {
                            id: customRootsView
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            model: customRootsModel
                            clip: true
                            currentIndex: -1
                            delegate: Rectangle {
                                width: ListView.view.width
                                height: 32
                                color: ListView.isCurrentItem ? "#2d3342" : "transparent"
                                radius: 4
                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: customRootsView.currentIndex = index
                                }
                                CrispText {
                                    text: model.path
                                    color: "#e8e8e8"
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left
                                    anchors.leftMargin: 6
                                    elide: Text.ElideMiddle
                                    width: parent.width - 12
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            StyledButton {
                                text: "Add Folder"
                                onClicked: addFolderDialog.open()
                            }
                            StyledButton {
                                text: "Remove"
                                enabled: customRootsView.currentIndex >= 0
                                onClicked: {
                                    if (customRootsView.currentIndex < 0)
                                        return
                                    var path = customRootsModel.get(customRootsView.currentIndex).path
                                    backendRef.remove_steam_emu_custom_root(path)
                                    reloadRoots()
                                    customRootsView.currentIndex = -1
                                }
                            }
                            Item { Layout.fillWidth: true }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                StyledButton {
                    text: "Close"
                    onClicked: steamEmuLocationsDialog.close()
                }
            }
        }
    }
}
