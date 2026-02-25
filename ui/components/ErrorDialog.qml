import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

Dialog {
    id: errorDialog
    title: ""
    modal: true
    standardButtons: Dialog.NoButton
    background: Rectangle { color: "transparent"; border.color: "transparent" }
    width: 520
    height: 150
    x: Math.round(((parent ? parent.width : 0) - width) / 2)
    y: Math.round(((parent ? parent.height : 0) - height) / 2)
    Behavior on width { NumberAnimation { duration: 60; easing.type: Easing.OutCubic } }
    Behavior on height { NumberAnimation { duration: 60; easing.type: Easing.OutCubic } }

    property var resizeComponent
    property string message: ""
    onMessageChanged: {
        var textHeight = Math.max(24, errorText.contentHeight)
        height = Math.max(140, Math.min(320, Math.round(textHeight + 90)))
    }
    onOpened: {
        var textHeight = Math.max(24, errorText.contentHeight)
        height = Math.max(140, Math.min(320, Math.round(textHeight + 90)))
    }

    contentItem: Rectangle {
        color: "#1e1f25"
        radius: 8
        border.color: "#2a2a2a"
        width: errorDialog.width
        height: errorDialog.height
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
                startDialogX = errorDialog.x
                startDialogY = errorDialog.y
            }
            onPositionChanged: function(mouse) {
                if (!pressed)
                    return
                errorDialog.x = Math.round(errorDialog.x + ((startDialogX + (mouse.x - startX)) - errorDialog.x) * 0.35)
                errorDialog.y = Math.round(errorDialog.y + ((startDialogY + (mouse.y - startY)) - errorDialog.y) * 0.35)
            }
        }

        CrispText {
            id: errorText
            text: errorDialog.message
            color: "#e0e0e0"
            wrapMode: Text.WordWrap
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: buttonRow.top
            anchors.margins: 12
        }
        RowLayout {
            id: buttonRow
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 12
            StyledButton {
                text: "OK"
                onClicked: errorDialog.close()
            }
        }
        Loader {
            anchors.fill: parent
            sourceComponent: errorDialog.resizeComponent
            onLoaded: {
                item.dialogRef = errorDialog
                item.minWidth = 360
                item.minHeight = 140
            }
        }
    }
}
