import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

Dialog {
    id: igdbDialog
    title: ""
    modal: true
    standardButtons: Dialog.NoButton
    width: 520
    height: 420
    x: Math.round(((parent ? parent.width : 0) - width) / 2)
    y: Math.round(((parent ? parent.height : 0) - height) / 2)
    background: Rectangle { color: "transparent"; border.color: "transparent" }
    Behavior on width { NumberAnimation { duration: 60; easing.type: Easing.OutCubic } }
    Behavior on height { NumberAnimation { duration: 60; easing.type: Easing.OutCubic } }

    property alias queryText: searchField.text
    property var searchModel
    property var resizeComponent

    signal searchTextChanged(string text)
    signal gameChosen(var gameId, string name)

    contentItem: Rectangle {
        color: "#1e1f25"
        radius: 8
        border.color: "#2a2a2a"
        width: igdbDialog.width
        height: igdbDialog.height

        MouseArea {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 28
            cursorShape: Qt.SizeAllCursor
            property real startX
            property real startY
            property real startDialogX
            property real startDialogY
            onPressed: function(mouse) {
                startX = mouse.x
                startY = mouse.y
                startDialogX = igdbDialog.x
                startDialogY = igdbDialog.y
            }
            onPositionChanged: function(mouse) {
                if (!pressed)
                    return
                igdbDialog.x = Math.round(igdbDialog.x + ((startDialogX + (mouse.x - startX)) - igdbDialog.x) * 0.35)
                igdbDialog.y = Math.round(igdbDialog.y + ((startDialogY + (mouse.y - startY)) - igdbDialog.y) * 0.35)
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8

            CrispText { text: "Search IGDB"; color: "#f0f0f0"; font.bold: true }
            TextField {
                id: searchField
                Layout.fillWidth: true
                placeholderText: "Type a game name..."
                onTextChanged: igdbDialog.searchTextChanged(text)
            }

            ListView {
                id: searchList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 4
                model: igdbDialog.searchModel

                delegate: Rectangle {
                    width: searchList.width
                    height: 36
                    radius: 4
                    color: ListView.isCurrentItem ? "#2a2d36" : "transparent"
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 6
                        Rectangle {
                            width: 24
                            height: 24
                            radius: 3
                            color: "#1a1a1a"
                            border.color: "#2a2a2a"
                            Image {
                                anchors.fill: parent
                                source: cover_url || ""
                                fillMode: Image.PreserveAspectFit
                                visible: source !== ""
                            }
                            CrispText {
                                anchors.centerIn: parent
                                text: "🎮"
                                color: "#9a9a9a"
                                font.pointSize: 10
                                visible: (cover_url || "") === ""
                            }
                        }
                        CrispText {
                            text: year && year.length > 0 ? name + " (" + year + ")" : name
                            color: "#e0e0e0"
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            if (!game_id) {
                                return
                            }
                            igdbDialog.gameChosen(game_id, name)
                            igdbDialog.close()
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                StyledButton {
                    text: "Close"
                    onClicked: igdbDialog.close()
                }
            }
        }
        Loader {
            anchors.fill: parent
            sourceComponent: igdbDialog.resizeComponent
            onLoaded: {
                item.dialogRef = igdbDialog
                item.minWidth = 420
                item.minHeight = 300
            }
        }
    }
}
