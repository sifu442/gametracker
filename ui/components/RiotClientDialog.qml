import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

Dialog {
    id: riotClientDialog
    title: ""
    modal: true
    standardButtons: Dialog.NoButton
    background: Rectangle { color: "transparent"; border.color: "transparent" }
    width: 520
    height: 200
    x: Math.round(((parent ? parent.width : 0) - width) / 2)
    y: Math.round(((parent ? parent.height : 0) - height) / 2)

    property var backendRef
    property var appRootRef

    onOpened: {
        riotClientField.text = backendRef.riotClientPath
    }

    contentItem: Rectangle {
        color: "#1e1f25"
        radius: 8
        border.color: "#2a2a2a"
        width: riotClientDialog.width
        height: riotClientDialog.height

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            CrispText {
                text: "Riot Client Path"
                color: "#f0f0f0"
                font.bold: true
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TextField {
                    id: riotClientField
                    Layout.fillWidth: true
                    placeholderText: "C:/Riot Games/Riot Client/RiotClientServices.exe"
                }
                StyledButton {
                    text: "Browse"
                    Layout.preferredWidth: 100
                    onClicked: appRootRef.openFileDialog(riotClientField, "Executable (*.exe);;All files (*)")
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                StyledButton {
                    text: "Save"
                    onClicked: {
                        backendRef.set_riot_client_path(riotClientField.text)
                        riotClientDialog.close()
                    }
                }
                StyledButton {
                    text: "Cancel"
                    onClicked: riotClientDialog.close()
                }
            }
        }
    }
}
