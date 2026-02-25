import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

Dialog {
    id: steamApiDialog
    title: ""
    modal: true
    standardButtons: Dialog.NoButton
    background: Rectangle { color: "transparent"; border.color: "transparent" }
    width: 620
    height: 300
    x: Math.round(((parent ? parent.width : 0) - width) / 2)
    y: Math.round(((parent ? parent.height : 0) - height) / 2)

    property var backendRef

    onOpened: {
        apiKeyField.text = backendRef.steamWebApiKey || ""
        steamIdField.text = backendRef.steamId64 || ""
    }

    contentItem: Rectangle {
        color: "#1e1f25"
        radius: 8
        border.color: "#2a2a2a"
        width: steamApiDialog.width
        height: steamApiDialog.height

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            CrispText {
                text: "Steam Web API Settings"
                color: "#f0f0f0"
                font.bold: true
                font.pointSize: 13
            }

            CrispText {
                text: "How to get it: 1) Visit steamcommunity.com/dev/apikey  2) Sign in  3) Generate key  4) Find SteamID64 at steamid.io"
                color: "#c5c5c5"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                CrispText { text: "API Key"; color: "#d6d6d6"; Layout.preferredWidth: 90 }
                TextField {
                    id: apiKeyField
                    Layout.fillWidth: true
                    placeholderText: "Paste Steam Web API key"
                    echoMode: TextInput.Normal
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                CrispText { text: "SteamID64"; color: "#d6d6d6"; Layout.preferredWidth: 90 }
                TextField {
                    id: steamIdField
                    Layout.fillWidth: true
                    placeholderText: "Example: 7656119..."
                }
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                StyledButton {
                    text: "Save"
                    onClicked: {
                        backendRef.set_steam_api_settings(apiKeyField.text, steamIdField.text)
                        steamApiDialog.close()
                    }
                }
                StyledButton {
                    text: "Cancel"
                    onClicked: steamApiDialog.close()
                }
            }
        }
    }
}
