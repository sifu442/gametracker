import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

Rectangle {
    id: panel
    property var backendRef
    property var editDialogRef
    property var errorDialogRef
    signal removeRequested()

    color: "#0f0f0f"
    border.color: "#1e1e1e"
    z: 10

    Rectangle {
        anchors.fill: parent
        radius: 10
        clip: true
        opacity: backendRef.selectedGameId !== "" ? 1 : 0.35

        Image {
            anchors.fill: parent
            source: backendRef.selectedGameHeroUrl
            fillMode: Image.PreserveAspectCrop
            visible: source !== ""
        }
        Rectangle {
            anchors.fill: parent
            color: "#0b0c10"
            opacity: 0.6
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 360
                color: "transparent"
                opacity: 1
                radius: 8
                clip: true

                ScrollView {
                    id: topHeroScroll
                    anchors.fill: parent
                    anchors.margins: 12
                    clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    ScrollBar.vertical.policy: ScrollBar.AsNeeded

                    ColumnLayout {
                        width: Math.max(0, topHeroScroll.availableWidth - 8)
                        spacing: 10

                        Rectangle {
                            width: 180
                            height: 240
                            radius: 10
                            clip: true
                            color: "transparent"

                            Image {
                                anchors.fill: parent
                                source: backendRef.selectedGameCoverUrl
                                fillMode: Image.PreserveAspectCrop
                                visible: source !== ""
                            }
                        }

                        CrispText {
                            text: backendRef.selectedGameName
                            color: "#ffffff"
                            font.pointSize: 16
                            font.bold: true
                            wrapMode: Text.WordWrap
                            width: 320
                        }

                        RowLayout {
                            spacing: 8
                            StyledButton {
                                text: backendRef.selectedGameRunning ? "Running" : "Play"
                                iconSource: backendRef.selectedGameRunning ? "" : Qt.resolvedUrl("../assets/play.svg")
                                bgColor: "#37d6b1"
                                bgHover: "#2ccaa6"
                                bgPressed: "#22b693"
                                textColor: "#ffffff"
                                enabled: backendRef.selectedGameName !== "" && !backendRef.isMonitoring
                                onClicked: backendRef.play_selected()
                            }
                            StyledButton {
                                text: "Edit"
                                iconSource: Qt.resolvedUrl("../assets/edit.svg")
                                bgColor: "#2a2d36"
                                bgHover: "#343846"
                                bgPressed: "#1f222b"
                                textColor: "#e8e8e8"
                                enabled: true
                                onClicked: {
                                    if (backendRef.selectedGameId === "") {
                                        errorDialogRef.message = "Please select a game first."
                                        errorDialogRef.open()
                                    } else {
                                        editDialogRef.open()
                                    }
                                }
                            }
                            StyledButton {
                                text: "Remove"
                                iconSource: Qt.resolvedUrl("../assets/remove.svg")
                                bgColor: "#2a2d36"
                                bgHover: "#343846"
                                bgPressed: "#1f222b"
                                textColor: "#e8e8e8"
                                enabled: backendRef.selectedGameName !== ""
                                onClicked: panel.removeRequested()
                            }
                        }
                        Item { Layout.fillWidth: true; Layout.preferredHeight: 8 }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                color: "transparent"
                radius: 8
                clip: true
                border.color: "transparent"

                Rectangle {
                    anchors.fill: parent
                    color: "#ffffff"
                    opacity: 0.12
                    radius: 10
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 18

                    Column {
                        spacing: 2
                        CrispText { text: "Last Played"; color: "#c5c5c5"; font.pointSize: 9 }
                        CrispText { text: backendRef.selectedGameLastPlayedText; color: "#f2f2f2"; font.pointSize: 12; font.bold: true }
                    }
                    Column {
                        spacing: 2
                        CrispText { text: "Time Played"; color: "#c5c5c5"; font.pointSize: 9 }
                        CrispText {
                            text: backendRef.selectedGamePlaytimeSeconds > 0
                                  ? Math.floor(backendRef.selectedGamePlaytimeSeconds / 3600) + "h " + Math.floor((backendRef.selectedGamePlaytimeSeconds % 3600) / 60) + "m"
                                  : "0m"
                            color: "#f2f2f2"
                            font.pointSize: 12
                            font.bold: true
                        }
                    }
                    Column {
                        spacing: 2
                        CrispText { text: "Genre"; color: "#c5c5c5"; font.pointSize: 9 }
                        CrispText { text: backendRef.selectedGameGenre || "N/A"; color: "#f2f2f2"; font.pointSize: 12; font.bold: true }
                    }
                    Column {
                        spacing: 2
                        CrispText { text: "Platform"; color: "#c5c5c5"; font.pointSize: 9 }
                        CrispText { text: backendRef.selectedGamePlatform || "N/A"; color: "#f2f2f2"; font.pointSize: 12; font.bold: true }
                    }
                    Item { Layout.fillWidth: true }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: 240
                spacing: 12

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "transparent"
                    border.color: "transparent"
                    radius: 8

                    Rectangle {
                        anchors.fill: parent
                        color: "#ffffff"
                        opacity: 0.12
                        radius: 10
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8

                        CrispText {
                            text: "Description"
                            color: "#f0f0f0"
                            font.bold: true
                        }

                        Flickable {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            contentWidth: width
                            contentHeight: notesText.implicitHeight

                            CrispText {
                                id: notesText
                                width: parent.width
                                text: backendRef.selectedGameNotes !== "" ? backendRef.selectedGameNotes : ""
                                color: "#d6d6d6"
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "transparent"
                    border.color: "transparent"
                    radius: 8

                    Rectangle {
                        anchors.fill: parent
                        color: "#ffffff"
                        opacity: 0.12
                        radius: 10
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8

                        CrispText {
                            text: "Achievements"
                            color: "#f0f0f0"
                            font.bold: true
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            visible: backendRef.selectedGameRaTotal > 0

                            ProgressBar {
                                Layout.fillWidth: true
                                from: 0
                                to: 1
                                value: backendRef.selectedGameRaProgress
                            }
                            CrispText {
                                text: backendRef.selectedGameRaProgressText
                                color: "#f2f2f2"
                                font.pointSize: 10
                                font.bold: true
                            }
                        }

                        ListView {
                            id: unlockedAchievementsList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            spacing: 4
                            model: backendRef.selectedGameRaUnlockedList
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            delegate: Rectangle {
                                width: Math.max(0, unlockedAchievementsList.width - 2)
                                height: 42
                                radius: 4
                                color: "#1b2530"
                                border.color: "#2d3a49"
                                border.width: 1
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 6
                                    spacing: 8
                                    Rectangle {
                                        width: 28
                                        height: 28
                                        radius: 4
                                        color: "#0f1720"
                                        border.color: "#2d3a49"
                                        border.width: 1
                                        clip: true
                                        Layout.alignment: Qt.AlignVCenter

                                        Image {
                                            anchors.fill: parent
                                            source: modelData.icon || ""
                                            fillMode: Image.PreserveAspectFit
                                            asynchronous: true
                                            cache: true
                                            visible: status === Image.Ready && source !== ""
                                        }

                                        CrispText {
                                            anchors.centerIn: parent
                                            text: "★"
                                            color: "#7ea0bf"
                                            font.pointSize: 10
                                            visible: (modelData.icon || "") === ""
                                        }
                                    }
                                    CrispText {
                                        text: modelData.title || ""
                                        color: "#f1f5f9"
                                        font.pointSize: 10
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    CrispText {
                                        text: modelData.earned || ""
                                        color: "#a9b4c0"
                                        font.pointSize: 9
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                }
                            }
                        }

                        CrispText {
                            text: backendRef.selectedGameRaUnlockedList.length === 0 ? "No unlocked achievements yet" : ""
                            color: "#b8c0c8"
                            visible: backendRef.selectedGameRaUnlockedList.length === 0
                        }
                    }
                }
            }
            Item { Layout.fillHeight: true }
        }

        CrispText {
            anchors.centerIn: parent
            text: "Select a game to see details"
            color: "#cfcfcf"
            font.pointSize: 12
            visible: backendRef.selectedGameId === ""
        }
    }
}
