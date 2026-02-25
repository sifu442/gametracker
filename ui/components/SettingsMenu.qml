import QtQuick
import QtQuick.Controls

Item {
    id: settingsMenuRoot
    property var backendRef
    property var emulatorDialogRef
    property var riotClientDialogRef
    property var steamApiDialogRef
    property var steamEmuLocationsDialogRef
    property var errorDialogRef
    property int menuY: 48

    function open() {
        settingsMenu.y = menuY
        settingsMenu.open()
    }

    component SettingsMenuItem: MenuItem {
        id: control
        property bool showChevron: false
        contentItem: Row {
            anchors.fill: parent
            spacing: 8
            Text {
                width: parent.width - (control.showChevron ? 16 : 0)
                text: control.text
                color: "#f0f0f0"
                elide: Text.ElideRight
                verticalAlignment: Text.AlignVCenter
            }
            Text {
                visible: control.showChevron
                text: "›"
                color: "#f0f0f0"
                verticalAlignment: Text.AlignVCenter
            }
        }
    }

        Menu {
        id: settingsMenu
        y: menuY
        width: 260
        palette.text: "#f0f0f0"
        palette.windowText: "#f0f0f0"
        palette.buttonText: "#f0f0f0"
        property int itemHeight: 32
        onClosed: libraryMenu.close()
        background: Rectangle {
            color: "#1c1c1c"
            radius: 6
            border.color: "#2a2a2a"
        }

        SettingsMenuItem { text: "New Window"; onHoveredChanged: if (hovered) libraryMenu.close() }
        SettingsMenuItem { text: "Open File..."; onHoveredChanged: if (hovered) libraryMenu.close() }
        SettingsMenuItem { text: "Open Folder..."; onHoveredChanged: if (hovered) libraryMenu.close() }
        MenuSeparator { }

        SettingsMenuItem {
            id: libraryMenuItem
            text: "Library"
            showChevron: true
            onHoveredChanged: {
                if (hovered) {
                    libraryMenu.x = settingsMenu.x + settingsMenu.width - 2
                    libraryMenu.y = settingsMenu.y + (settingsMenu.itemHeight * 3)
                    libraryMenu.open()
                }
            }
            onTriggered: {
                libraryMenu.x = settingsMenu.x + settingsMenu.width - 2
                libraryMenu.y = settingsMenu.y + (settingsMenu.itemHeight * 3)
                libraryMenu.open()
            }
        }
        MenuSeparator { }
        SettingsMenuItem { text: "Preferences"; onHoveredChanged: if (hovered) libraryMenu.close() }
        MenuSeparator { }
        SettingsMenuItem { text: "Exit"; onHoveredChanged: if (hovered) libraryMenu.close(); onTriggered: Qt.quit() }
    }

    Menu {
        id: libraryMenu
        width: 260
        palette.text: "#f0f0f0"
        palette.windowText: "#f0f0f0"
        palette.buttonText: "#f0f0f0"
        background: Rectangle {
            color: "#1c1c1c"
            radius: 6
            border.color: "#2a2a2a"
        }
        SettingsMenuItem {
            text: "Configure Emulators..."
            onTriggered: emulatorDialogRef.open()
        }
        SettingsMenuItem {
            text: "Riot Client..."
            onTriggered: riotClientDialogRef.open()
        }
        SettingsMenuItem {
            text: "Steam Web API..."
            onTriggered: steamApiDialogRef.open()
        }
        SettingsMenuItem {
            text: "SteamEmu Locations..."
            onTriggered: steamEmuLocationsDialogRef.open()
        }
        SettingsMenuItem {
            text: "Update Library"
            onTriggered: {
                var result = backendRef.update_library_from_emulators()
                errorDialogRef.message = result
                errorDialogRef.open()
            }
        }
        SettingsMenuItem {
            text: "Update Images"
            onTriggered: {
                var result = backendRef.update_images_from_steamgriddb()
                errorDialogRef.message = result
                errorDialogRef.open()
            }
        }
        SettingsMenuItem {
            text: "Refresh Steam Achievements"
            onTriggered: {
                var result = backendRef.refresh_steam_achievements()
                errorDialogRef.message = result
                errorDialogRef.open()
            }
        }
        SettingsMenuItem {
            text: "Refresh SteamEmu Achievements"
            onTriggered: {
                var result = backendRef.refresh_steamemu_achievements()
                errorDialogRef.message = result
                errorDialogRef.open()
            }
        }
        SettingsMenuItem {
            text: "Test Notification"
            onTriggered: {
                var result = backendRef.test_notification()
                errorDialogRef.message = result
                errorDialogRef.open()
            }
        }
    }
}
