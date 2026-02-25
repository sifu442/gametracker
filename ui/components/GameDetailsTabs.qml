import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "."

Item {
    id: root

    property int currentIndex: 0
    property var backend
    property var openFileDialog
    property var openFolderDialog
    property var openUrlDialog
    property var emulatorKeys: []
    property var platformOptions: []
    property bool useBackendFallback: false
    property string gameIdText: ""
    property string firstPlayedText: ""
    property string lastPlayedText: ""

    property alias nameField: nameField
    property alias sortingNameField: sortingNameField
    property alias genreField: genreField
    property alias platformField: platformField
    property alias playtimeField: playtimeField
    property alias notesField: notesField
    property alias releaseDateField: releaseDateField
    property alias seriesField: seriesField
    property alias ageRatingField: ageRatingField
    property alias regionField: regionField
    property alias sourceField: sourceField
    property alias developersField: developersField
    property alias publishersField: publishersField
    property alias categoriesField: categoriesField
    property alias featuresField: featuresField
    property alias exePathField: exePathField
    property alias userScoreField: userScoreField
    property alias criticScoreField: criticScoreField
    property alias serialField: serialField
    property alias emulatedCheck: emulatedCheck
    property alias emulatorCombo: emulatorCombo
    property alias romField: romField
    property alias logoField: logoField
    property alias coverField: coverField
    property alias heroField: heroField
    property alias gameIdField: gameIdField
    property alias firstPlayedField: firstPlayedField
    property alias lastPlayedField: lastPlayedField
    property alias linksJsonField: linksJsonField
    property alias windowsOnlyCheck: windowsOnlyCheck
    property alias installedCheck: installedCheck
    property alias winePrefixField: winePrefixField
    property alias compatCombo: compatCombo
    property alias compatToolField: compatToolField
    property alias protonPathField: protonPathField
    property alias wineDllOverridesField: wineDllOverridesField

    property bool showInstalledLocation: false
    property var _dateTargetField: null

    TextField { id: logoField; visible: false }
    TextField { id: coverField; visible: false }
    TextField { id: heroField; visible: false }
    TextField { id: compatToolField; visible: false }
    TextField { id: protonPathField; visible: false }
    TextField { id: wineDllOverridesField; visible: false }
    TextArea { id: linksJsonField; visible: false; text: "[]" }

    Popup {
        id: datePickerPopup
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        width: 300
        height: 340
        x: Math.round((root.width - width) / 2)
        y: Math.round((root.height - height) / 2)
        background: Rectangle {
            color: "#1f212b"
            radius: 8
            border.color: "#2a2a2a"
        }
        contentItem: ColumnLayout {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 8
            CrispText { text: "Select Date"; color: "#d6d6d6"; font.bold: true }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                SpinBox {
                    id: yearSpin
                    from: 1970
                    to: 2100
                    value: (new Date()).getFullYear()
                    editable: true
                    Layout.fillWidth: true
                    textFromValue: function(value, locale) {
                        return String(value)
                    }
                    valueFromText: function(text, locale) {
                        return parseInt(text)
                    }
                }
                SpinBox {
                    id: monthSpin
                    from: 1
                    to: 12
                    value: (new Date()).getMonth() + 1
                    editable: true
                    Layout.fillWidth: true
                }
                SpinBox {
                    id: daySpin
                    from: 1
                    to: 31
                    value: (new Date()).getDate()
                    editable: true
                    Layout.fillWidth: true
                }
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                StyledButton {
                    text: "Clear"
                    onClicked: {
                        if (root._dateTargetField)
                            root._dateTargetField.text = ""
                        datePickerPopup.close()
                    }
                }
                StyledButton {
                    text: "Set"
                    onClicked: {
                        if (root._dateTargetField) {
                            var yyyy = yearSpin.value.toString()
                            var mm = monthSpin.value.toString()
                            if (mm.length < 2) mm = "0" + mm
                            var dd = daySpin.value.toString()
                            if (dd.length < 2) dd = "0" + dd
                            root._dateTargetField.text = yyyy + "-" + mm + "-" + dd
                        }
                        datePickerPopup.close()
                    }
                }
            }
        }
    }

    StackLayout {
        anchors.fill: parent
        currentIndex: root.currentIndex

        Item {
            RowLayout {
                anchors.fill: parent
                anchors.margins: 0
                spacing: 16

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    GridLayout {
                        columns: 2
                        columnSpacing: 12
                        rowSpacing: 8
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop

                        Text { text: "Name"; color: "#d6d6d6" }
                        TextField { id: nameField; placeholderText: "Name"; Layout.fillWidth: true }

                        Text { text: "Sorting Name"; color: "#d6d6d6" }
                        TextField { id: sortingNameField; placeholderText: "" ; Layout.fillWidth: true }

                        Text { text: "Platform"; color: "#d6d6d6" }
                        ComboBox {
                            id: platformField
                            model: root.platformOptions
                            editable: true
                            Layout.fillWidth: true
                        }

                        Text { text: "Genres"; color: "#d6d6d6" }
                        TextField { id: genreField; placeholderText: "Genre"; Layout.fillWidth: true }

                        Text { text: "Developers"; color: "#d6d6d6" }
                        TextField { id: developersField; placeholderText: "" ; Layout.fillWidth: true }

                        Text { text: "Publishers"; color: "#d6d6d6" }
                        TextField { id: publishersField; placeholderText: "" ; Layout.fillWidth: true }

                        Text { text: "Categories"; color: "#d6d6d6" }
                        TextField { id: categoriesField; placeholderText: "" ; Layout.fillWidth: true }

                        Text { text: "Features"; color: "#d6d6d6" }
                        TextField { id: featuresField; placeholderText: "" ; Layout.fillWidth: true }

                        Text { text: "Description"; color: "#d6d6d6" }
                        TextArea { id: notesField; Layout.fillWidth: true; Layout.preferredHeight: 120; wrapMode: TextArea.Wrap; placeholderText: "Notes" }
                    }
                    Item { Layout.fillHeight: true }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    GridLayout {
                        columns: 2
                        columnSpacing: 12
                        rowSpacing: 8
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop

                        Text { text: "Release Date"; color: "#d6d6d6" }
                        TextField { id: releaseDateField; placeholderText: "YYYY-MM-DD"; Layout.fillWidth: true }

                        Text { text: "Series"; color: "#d6d6d6" }
                        TextField { id: seriesField; placeholderText: "" ; Layout.fillWidth: true }

                        Text { text: "Age Rating"; color: "#d6d6d6" }
                        TextField { id: ageRatingField; placeholderText: "" ; Layout.fillWidth: true }

                        Text { text: "Region"; color: "#d6d6d6" }
                        TextField { id: regionField; placeholderText: "" ; Layout.fillWidth: true }

                        Text { text: "Source"; color: "#d6d6d6" }
                        TextField { id: sourceField; placeholderText: "" ; Layout.fillWidth: true }

                        Text { text: "Completion Status"; color: "#d6d6d6" }
                        TextField { placeholderText: "" ; Layout.fillWidth: true }

                        Text { text: "User Score"; color: "#d6d6d6" }
                        TextField { id: userScoreField; placeholderText: "" ; Layout.fillWidth: true }

                        Text { text: "Critic Score"; color: "#d6d6d6" }
                        TextField { id: criticScoreField; placeholderText: "" ; Layout.fillWidth: true }

                        Text { text: "Community Score"; color: "#d6d6d6" }
                        TextField { placeholderText: "" ; Layout.fillWidth: true }

                        Text { text: "Playtime (mins)"; color: "#d6d6d6" }
                        TextField { id: playtimeField; placeholderText: "0" ; Layout.fillWidth: true }
                    }
                    Item { Layout.fillHeight: true }
                }
            }
        }

        Item {
            RowLayout {
                anchors.fill: parent
                anchors.margins: 0
                spacing: 16

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    GridLayout {
                        columns: 2
                        columnSpacing: 12
                        rowSpacing: 8
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop

                        Text { text: "Game ID"; color: "#d6d6d6" }
                        TextField { id: gameIdField; readOnly: true; text: root.gameIdText; Layout.fillWidth: true }

                        Text { text: "Serial"; color: "#d6d6d6" }
                        TextField { id: serialField; Layout.fillWidth: true }

                        Text { text: "First Played"; color: "#d6d6d6" }
                        RowLayout {
                            Layout.fillWidth: true
                            TextField { id: firstPlayedField; text: root.firstPlayedText; Layout.fillWidth: true; placeholderText: "YYYY-MM-DD" }
                            StyledButton {
                                text: ""
                                Layout.preferredWidth: 40
                                contentItem: Text {
                                    anchors.centerIn: parent
                                    text: "📅"
                                    color: "#e8e8e8"
                                    font.pixelSize: 16
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    root._dateTargetField = firstPlayedField
                                    datePickerPopup.open()
                                }
                            }
                        }

                        Text { text: "Last Played"; color: "#d6d6d6" }
                        RowLayout {
                            Layout.fillWidth: true
                            TextField { id: lastPlayedField; text: root.lastPlayedText; Layout.fillWidth: true; placeholderText: "YYYY-MM-DD" }
                            StyledButton {
                                text: ""
                                Layout.preferredWidth: 40
                                contentItem: Text {
                                    anchors.centerIn: parent
                                    text: "📅"
                                    color: "#e8e8e8"
                                    font.pixelSize: 16
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    root._dateTargetField = lastPlayedField
                                    datePickerPopup.open()
                                }
                            }
                        }
                    }
                    Item { Layout.fillHeight: true }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    GridLayout {
                        columns: 2
                        columnSpacing: 12
                        rowSpacing: 8
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop

                        Text { text: "Emulated"; color: "#d6d6d6" }
                        CheckBox { id: emulatedCheck; Layout.fillWidth: true; Layout.alignment: Qt.AlignRight }

                        Text { text: "Emulator"; color: "#d6d6d6"; visible: emulatedCheck.checked }
                        ComboBox {
                            id: emulatorCombo
                            model: root.emulatorKeys
                            Layout.fillWidth: true
                            visible: emulatedCheck.checked
                        }

                        Text { text: "ROM Path"; color: "#d6d6d6"; visible: emulatedCheck.checked }
                        RowLayout {
                            Layout.fillWidth: true
                            visible: emulatedCheck.checked
                            TextField { id: romField; Layout.fillWidth: true }
                            StyledButton {
                                text: "Browse"
                                onClicked: root.openFileDialog(romField, "ROM files (*.*)")
                            }
                        }
                        Item { Layout.fillHeight: true }
                    }
                }
                Item { Layout.fillHeight: true }
            }
        }

        Item {
            MediaTabContent {
                anchors.fill: parent
                logoField: logoField
                coverField: coverField
                heroField: heroField
                gameName: nameField.text
                useBackendFallback: root.useBackendFallback
                backend: root.backend
                openFileDialog: root.openFileDialog
                openUrlDialog: root.openUrlDialog
            }
        }

        Item {
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    CrispText {
                        text: "Links"
                        color: "#f0f0f0"
                        font.bold: true
                    }
                    Item { Layout.fillWidth: true }
                    StyledButton {
                        text: "Add Link"
                        onClicked: {
                            linksModel.append({ type: "", url: "" })
                            root._syncLinksJson()
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 6
                    color: "#171922"
                    border.color: "#2a2a2a"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            CrispText { text: "Type"; color: "#cfd3dc"; Layout.preferredWidth: 180; font.bold: true }
                            CrispText { text: "Link"; color: "#cfd3dc"; Layout.fillWidth: true; font.bold: true }
                            Item { Layout.preferredWidth: 80 }
                        }

                        ListView {
                            id: linksList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: ListModel { id: linksModel }
                            spacing: 6
                            delegate: RowLayout {
                                width: linksList.width
                                spacing: 8

                                ComboBox {
                                    id: linkTypeCombo
                                    Layout.preferredWidth: 180
                                    editable: true
                                    model: [
                                        "website", "steam", "twitter", "facebook", "youtube",
                                        "twitch", "reddit", "discord", "epic", "gog", "itch.io", "wiki"
                                    ]
                                    function applyTypeValue(value) {
                                        var v = (value || "").toString().trim().toLowerCase()
                                        if (!v) {
                                            currentIndex = 0
                                            return
                                        }
                                        var idx = -1
                                        for (var mi = 0; mi < model.length; mi++) {
                                            if (model[mi].toString().toLowerCase() === v) {
                                                idx = mi
                                                break
                                            }
                                        }
                                        if (idx >= 0) {
                                            currentIndex = idx
                                        } else {
                                            editText = value
                                        }
                                    }
                                    Component.onCompleted: {
                                        applyTypeValue(type)
                                    }
                                    onActivated: {
                                        linksModel.setProperty(index, "type", currentText)
                                        root._syncLinksJson()
                                    }
                                    onEditTextChanged: {
                                        linksModel.setProperty(index, "type", editText)
                                        root._syncLinksJson()
                                    }
                                }

                                TextField {
                                    Layout.fillWidth: true
                                    placeholderText: "https://..."
                                    text: url || ""
                                    onTextChanged: {
                                        linksModel.setProperty(index, "url", text)
                                        root._syncLinksJson()
                                    }
                                }

                                StyledButton {
                                    text: "Remove"
                                    Layout.preferredWidth: 80
                                    onClicked: {
                                        linksModel.remove(index)
                                        root._syncLinksJson()
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        Item {
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 12

                RowLayout {
                    Layout.fillWidth: true
                    Text { text: "Executable"; color: "#d6d6d6" }
                    RowLayout {
                        Layout.fillWidth: true
                        TextField { id: exePathField; Layout.fillWidth: true; placeholderText: "Game.exe" }
                        StyledButton {
                            text: "Browse"
                            onClicked: root.openFileDialog(exePathField, "Executable (*.exe *.AppImage);;All files (*)")
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: Qt.platform.os === "linux" && !root.emulatedCheck.checked
                    Text { text: "Wine Prefix"; color: "#d6d6d6" }
                    RowLayout {
                        Layout.fillWidth: true
                        TextField { id: winePrefixField; Layout.fillWidth: true; placeholderText: "~/.local/share/gametracker/Prefixes/<Game Name>" }
                        StyledButton {
                            text: "Browse"
                            onClicked: root.openFolderDialog(winePrefixField)
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: Qt.platform.os === "linux" && !root.emulatedCheck.checked
                    Text { text: "Wine/Proton"; color: "#d6d6d6" }
                    ComboBox {
                        id: compatCombo
                        Layout.fillWidth: true
                        model: root.backend ? root.backend.availableCompatOptions : []
                        textRole: "label"
                        onCurrentIndexChanged: {
                            var options = model || []
                            if (currentIndex < 0 || currentIndex >= options.length)
                                return
                            var opt = options[currentIndex]
                            compatToolField.text = opt.tool || ""
                            protonPathField.text = opt.path || ""
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: Qt.platform.os === "linux" && !root.emulatedCheck.checked
                    Text { text: "Wine DLL Overrides"; color: "#d6d6d6" }
                    TextField {
                        id: wineDllOverridesInput
                        Layout.fillWidth: true
                        placeholderText: "Example: d3d11=n,b;dxgi=n,b"
                        text: wineDllOverridesField.text
                        onTextChanged: wineDllOverridesField.text = text
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Text { text: "Installed"; color: "#d6d6d6" }
                    CheckBox { id: installedCheck; Layout.alignment: Qt.AlignRight }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Text { text: "Windows Only"; color: "#d6d6d6" }
                    CheckBox { id: windowsOnlyCheck; Layout.alignment: Qt.AlignRight }
                }

                Item { Layout.fillHeight: true }
            }
        }
        Item { }
        Item { }
    }

    function _syncLinksJson() {
        var out = []
        for (var i = 0; i < linksModel.count; i++) {
            var row = linksModel.get(i)
            var t = (row.type || "").toString().trim()
            var u = (row.url || "").toString().trim()
            if (t.length === 0 && u.length === 0)
                continue
            out.push({ "type": t, "url": u })
        }
        linksJsonField.text = JSON.stringify(out)
    }

    function loadLinksFromJson(rawJson) {
        linksModel.clear()
        var parsed = []
        try {
            parsed = JSON.parse(rawJson || "[]")
        } catch (e) {
            parsed = []
        }
        if (!parsed || parsed.length === 0) {
            linksJsonField.text = "[]"
            return
        }
        for (var i = 0; i < parsed.length; i++) {
            var item = parsed[i]
            if (!item)
                continue
            linksModel.append({
                "type": item.type || "",
                "url": item.url || ""
            })
        }
        _syncLinksJson()
    }
}
