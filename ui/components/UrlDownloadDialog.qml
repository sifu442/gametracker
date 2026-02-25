import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

Dialog {
    id: urlDialog
    title: "Download Image"
    modal: true
    width: 420
    height: 180
    x: Math.round(((parent ? parent.width : 0) - width) / 2)
    y: Math.round(((parent ? parent.height : 0) - height) / 2)
    standardButtons: Dialog.Ok | Dialog.Cancel
    background: Rectangle { color: "transparent"; border.color: "transparent" }
    Behavior on width { NumberAnimation { duration: 60; easing.type: Easing.OutCubic } }
    Behavior on height { NumberAnimation { duration: 60; easing.type: Easing.OutCubic } }

    property var targetField
    property string mediaType: ""
    property string gameName: ""
    property var backendRef
    property var resizeComponent
    property alias urlText: urlField.text

    contentItem: Rectangle {
        color: "#1e1f25"
        radius: 8
        border.color: "#2a2a2a"
        width: urlDialog.width
        height: urlDialog.height
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
                startDialogX = urlDialog.x
                startDialogY = urlDialog.y
            }
            onPositionChanged: function(mouse) {
                if (!pressed)
                    return
                urlDialog.x = Math.round(urlDialog.x + ((startDialogX + (mouse.x - startX)) - urlDialog.x) * 0.35)
                urlDialog.y = Math.round(urlDialog.y + ((startDialogY + (mouse.y - startY)) - urlDialog.y) * 0.35)
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 8
            CrispText { text: "Image URL"; color: "#e0e0e0" }
            TextField { id: urlField; placeholderText: "https://..." ; Layout.fillWidth: true }
        }
        Loader {
            anchors.fill: parent
            sourceComponent: urlDialog.resizeComponent
            onLoaded: {
                item.dialogRef = urlDialog
                item.minWidth = 320
                item.minHeight = 140
            }
        }
    }

    onAccepted: {
        if (!backendRef)
            return
        var path = backendRef.download_media(mediaType, urlField.text, gameName)
        if (targetField && path) {
            targetField.text = path
        }
    }
}
