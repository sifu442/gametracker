import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: mediaTab
    property var logoField
    property var coverField
    property var heroField
    property string gameName: ""
    property bool useBackendFallback: false
    property var backend
    property var openFileDialog
    property var openUrlDialog
    property bool logoCleared: false
    property bool coverCleared: false
    property bool heroCleared: false

    

    function resolvePath(path) {
        if (!path)
            return ""
        var s = path.toString()
        if (s.startsWith("file://") || s.startsWith("http://") || s.startsWith("https://"))
            return s
        if (/^[A-Za-z]:[\\/]/.test(s))
            return "file:///" + s.replace(/\\/g, "/")
        if (s.indexOf("/") >= 0 || s.indexOf("\\") >= 0)
            return Qt.resolvedUrl("../../" + s.replace(/\\/g, "/"))
        if (backend && backend.resolve_media_url)
            return backend.resolve_media_url(s)
        return ""
    }

    Connections {
        target: logoField
        ignoreUnknownSignals: true
        function onTextChanged() {
            if (logoField && logoField.text !== "")
                mediaTab.logoCleared = false
        }
    }

    Connections {
        target: coverField
        ignoreUnknownSignals: true
        function onTextChanged() {
            if (coverField && coverField.text !== "")
                mediaTab.coverCleared = false
        }
    }

    Connections {
        target: heroField
        ignoreUnknownSignals: true
        function onTextChanged() {
            if (heroField && heroField.text !== "")
                mediaTab.heroCleared = false
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 16

        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: parent.width * 0.45
            spacing: 16

            ColumnLayout {
                spacing: 8
                Text { text: "Icon"; color: "#d6d6d6"; font.bold: true }
                RowLayout {
                    spacing: 8
                    StyledButton {
                        text: ""
                        iconText: "+"
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        onClicked: openFileDialog(logoField, "Image files (*.png *.jpg *.jpeg *.gif *.bmp);;All files (*)")
                    }
                    StyledButton {
                        text: ""
                        iconSource: Qt.resolvedUrl("../assets/link.svg")
                        iconSize: 12
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        onClicked: openUrlDialog("logo", logoField, gameName)
                    }
                    StyledButton {
                        text: ""
                        iconSource: Qt.resolvedUrl("../assets/remove.svg")
                        iconSize: 12
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        onClicked: {
                            mediaTab.logoCleared = true
                            if (logoField) logoField.text = ""
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Text { text: "128x128px"; color: "#9a9a9a"; font.pointSize: 9 }
                }
                Rectangle {
                    width: 128
                    height: 128
                    radius: 6
                    color: "#1a1a1a"
                    border.color: "#2a2a2a"
                    Image {
                        anchors.fill: parent
                        source: resolvePath(
                            mediaTab.logoCleared
                                ? ""
                                : ((logoField && logoField.text !== "")
                                   ? logoField.text
                                   : (useBackendFallback && backend ? backend.selectedGameLogo : ""))
                        )
                        fillMode: Image.PreserveAspectFit
                    }
                }
            }

            ColumnLayout {
                spacing: 8
                Text { text: "Cover Image"; color: "#d6d6d6"; font.bold: true }
                RowLayout {
                    spacing: 8
                    StyledButton {
                        text: ""
                        iconText: "+"
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        onClicked: openFileDialog(coverField, "Image files (*.png *.jpg *.jpeg *.gif *.bmp);;All files (*)")
                    }
                    StyledButton {
                        text: ""
                        iconSource: Qt.resolvedUrl("../assets/link.svg")
                        iconSize: 12
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        onClicked: openUrlDialog("cover", coverField, gameName)
                    }
                    StyledButton {
                        text: ""
                        iconSource: Qt.resolvedUrl("../assets/remove.svg")
                        iconSize: 12
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        onClicked: {
                            mediaTab.coverCleared = true
                            if (coverField) coverField.text = ""
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Text { text: "810x1080px"; color: "#9a9a9a"; font.pointSize: 9 }
                }
                Rectangle {
                    width: 220
                    height: 220
                    radius: 6
                    color: "#1a1a1a"
                    border.color: "#2a2a2a"
                    Image {
                        anchors.fill: parent
                        source: resolvePath(
                            mediaTab.coverCleared
                                ? ""
                                : ((coverField && coverField.text !== "")
                                   ? coverField.text
                                   : (useBackendFallback && backend ? backend.selectedGameCover : ""))
                        )
                        fillMode: Image.PreserveAspectFit
                    }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: parent.width * 0.55
            spacing: 16

            ColumnLayout {
                spacing: 8
                Text { text: "Background Image"; color: "#d6d6d6"; font.bold: true }
                RowLayout {
                    spacing: 8
                    StyledButton {
                        text: ""
                        iconText: "+"
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        onClicked: openFileDialog(heroField, "Image files (*.png *.jpg *.jpeg *.gif *.bmp);;All files (*)")
                    }
                    StyledButton {
                        text: ""
                        iconSource: Qt.resolvedUrl("../assets/link.svg")
                        iconSize: 12
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        onClicked: openUrlDialog("hero", heroField, gameName)
                    }
                    StyledButton {
                        text: ""
                        iconSource: Qt.resolvedUrl("../assets/remove.svg")
                        iconSize: 12
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        onClicked: {
                            mediaTab.heroCleared = true
                            if (heroField) heroField.text = ""
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Text { text: "1600x900px"; color: "#9a9a9a"; font.pointSize: 9 }
                }
                Rectangle {
                    width: 360
                    height: 240
                    radius: 6
                    color: "#1a1a1a"
                    border.color: "#2a2a2a"
                    Image {
                        anchors.fill: parent
                        source: resolvePath(
                            mediaTab.heroCleared
                                ? ""
                                : ((heroField && heroField.text !== "")
                                   ? heroField.text
                                   : (useBackendFallback && backend ? backend.selectedGameHero : ""))
                        )
                        fillMode: Image.PreserveAspectFit
                    }
                }
            }
        }
    }
}
