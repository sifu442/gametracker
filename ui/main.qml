import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtQuick.Effects
import "components"

ApplicationWindow {
    id: root
    property var backendRef: backend
    font.hintingPreference: Font.PreferFullHinting
    font.preferShaping: false
    width: 1200
    height: 800
    visible: true
    title: "Halo Launcher"

    Item {
        id: backgroundLayer
        anchors.fill: parent
        z: -1

        Image {
            anchors.fill: parent
            source: backend.resolve_media_url(appRoot.heroSource)
            fillMode: Image.PreserveAspectCrop
            opacity: 1
            visible: source !== ""
            asynchronous: true
            cache: true
        }

        Rectangle {
            anchors.fill: parent
            color: "#0f0f0f"
            opacity: 0.25
        }
    }

    MultiEffect {
        id: backgroundBlur
        anchors.fill: backgroundLayer
        source: backgroundLayer
        z: 0
        blurEnabled: true
        blur: 0.6
        saturation: 0.9
        brightness: -0.05
    }

    Rectangle {
        id: glassOverlay
        anchors.fill: parent
        z: 1
        color: "#ffffff08"
        border.color: "#ffffff1a"
        border.width: 1
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#ffffff18" }
            GradientStop { position: 0.35; color: "#ffffff0a" }
            GradientStop { position: 1.0; color: "#ffffff05" }
        }
    }

    Component {
        id: resizeHandlesComponent
        ResizeHandles {}
    }

    Rectangle {
        id: appRoot
        anchors.fill: parent
        z: 2
        color: "#0f0f0f"
        property string heroSource: ""
        property string lastHeroId: ""
        property var emulatorKeys: []
        property string selectedEmulatorId: ""
        property var emulatorExePathsDraft: ({})
        property string emulatorTypeLast: ""
        property bool emulatorTypeSyncing: false
        property var platformOptions: backend.platformOptions
        property string metadataTarget: "add"
        function emulatorIndex(id) {
            var keys = appRoot.emulatorKeys || []
            var idx = keys.indexOf(id)
            return idx >= 0 ? idx : 0
        }
        function platformIndex(value) {
            var list = appRoot.platformOptions || []
            var target = (value || "").toLowerCase()
            for (var i = 0; i < list.length; i++) {
                if ((list[i] || "").toLowerCase() === target)
                    return i
            }
            return -1
        }
        function compatIndex(tool, path) {
            var options = (root.backendRef && root.backendRef.availableCompatOptions) ? root.backendRef.availableCompatOptions : []
            if (!options || options.length === 0)
                return 0
            var normTool = (tool || "").toLowerCase()
            for (var i = 0; i < options.length; i++) {
                var opt = options[i]
                var optTool = (opt.tool || "").toLowerCase()
                if (optTool !== normTool)
                    continue
                if ((optTool === "proton" || optTool === "wine") && (opt.path || "") !== (path || ""))
                    continue
                return i
            }
            return 0
        }
        function normalizeLaunchType(type) {
            var t = (type || "").toLowerCase()
            if (t === "exe")
                return "executable"
            return t
        }
        function getExePathForType(emu, type) {
            if (!emu)
                return ""
            var t = appRoot.normalizeLaunchType(type)
            if (backend.isWindows && emu.exe_path_windows)
                return emu.exe_path_windows
            if (backend.isLinux && emu.exe_path_linux)
                return emu.exe_path_linux
            if (emu.exe_paths && typeof emu.exe_paths === "object") {
                if (emu.exe_paths[t])
                    return emu.exe_paths[t]
            }
            return emu.exe_path || ""
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0
            z: 1

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 56
                color: "#141414"

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 12

                    StyledButton {
                        text: "Settings"
                        iconText: ""
                        bgColor: "#2a2d36"
                        bgHover: "#343846"
                        bgPressed: "#1f222b"
                        textColor: "#e8e8e8"
                        onClicked: settingsMenu.open()
                    }

                    TextField {
                        Layout.preferredWidth: 280
                        placeholderText: "Search games..."
                    }

                    ComboBox {
                        id: sortCombo
                        Layout.preferredWidth: 130
                        model: ["Last Played", "A-Z", "Z-A"]
                        currentIndex: 0
                        Component.onCompleted: backend.set_game_sort_order("last_played")
                        onCurrentIndexChanged: {
                            var mode = "last_played"
                            if (currentIndex === 1)
                                mode = "az"
                            else if (currentIndex === 2)
                                mode = "za"
                            backend.set_game_sort_order(mode)
                        }
                    }

                    ComboBox {
                        id: installFilterCombo
                        Layout.preferredWidth: 150
                        model: ["All", "Installed", "Not Installed", "Hidden"]
                        currentIndex: 1
                        Component.onCompleted: backend.set_game_install_filter("installed")
                        onCurrentIndexChanged: {
                            var mode = "all"
                            if (currentIndex === 1)
                                mode = "installed"
                            else if (currentIndex === 2)
                                mode = "not_installed"
                            else if (currentIndex === 3)
                                mode = "hidden"
                            backend.set_game_install_filter(mode)
                        }
                    }

                    Item { Layout.fillWidth: true }

                    StyledButton {
                        id: refreshButton
                        text: "Refresh"
                        iconText: "⟳"
                        onClicked: backend.reload()
                    }

                    StyledButton {
                        text: "Add Game"
                        iconText: "＋"
                        onClicked: addDialog.open()
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                Rectangle {
                    Layout.preferredWidth: 280
                    Layout.fillHeight: true
                    color: "#111111"
                    border.color: "#1e1e1e"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8

                        CrispText {
                            text: "Library"
                            color: "#d6d6d6"
                            font.pointSize: 14
                            font.bold: true
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            color: "transparent"
                            border.color: "#1f1f1f"
                            radius: 6

                            ListView {
                                id: gameList
                                anchors.fill: parent
                                clip: true
                                spacing: 4
                                reuseItems: true
                                cacheBuffer: 200
                                model: backend.gameModel

                                delegate: Rectangle {
                                    width: gameList.width
                                    height: 44
                                    color: backend.selectedGameId === model.id ? "#1f2a20" : "transparent"
                                    radius: 4
                                    property string logoUrl: backend.resolve_media_url(model.logo)

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: 6
                                        spacing: 8

                                        Rectangle {
                                            width: 24
                                            height: 24
                                            radius: 3
                                            color: "#1a1a1a"
                                            border.color: "#2a2a2a"

                                            Image {
                                                anchors.fill: parent
                                                source: logoUrl
                                                fillMode: Image.PreserveAspectFit
                                                visible: source !== ""
                                                asynchronous: true
                                                cache: true
                                            }

                                            CrispText {
                                                anchors.centerIn: parent
                                                text: "🎮"
                                                color: "#9a9a9a"
                                                font.pointSize: 10
                                                visible: logoUrl === ""
                                            }
                                        }

                                        CrispText {
                                            text: model.name || model.id
                                            color: "#e0e0e0"
                                            elide: Text.ElideRight
                                            verticalAlignment: Text.AlignVCenter
                                            Layout.fillWidth: true
                                        }
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                                        onClicked: function(mouse) {
                                            backend.select_game(model.id)
                                            if (mouse.button === Qt.RightButton) {
                                                var p = mapToItem(root.contentItem, mouse.x, mouse.y)
                                                gameContextMenu.x = p.x
                                                gameContextMenu.y = p.y
                                                gameContextMenu.open()
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                GameDetailsPanel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    backendRef: backend
                    editDialogRef: editDialog
                    errorDialogRef: errorDialog
                    onRemoveRequested: appRoot.confirmRemoveSelected()
                }
            }
        }

        EditGameDialog {
            id: editDialog
            backendRef: backend
            appRootRef: appRoot
            resizeComponent: resizeHandlesComponent
            igdbDialogRef: igdbSearchDialog
            igdbDebounceRef: igdbSearchDebounce
            errorDialogRef: errorDialog
        }

        AddGameDialog {
            id: addDialog
            backendRef: backend
            appRootRef: appRoot
            resizeComponent: resizeHandlesComponent
            igdbDialogRef: igdbSearchDialog
            igdbDebounceRef: igdbSearchDebounce
        }

        EmulatorDialog {
            id: emulatorDialog
            backendRef: backend
            appRootRef: appRoot
            resizeComponent: resizeHandlesComponent
            errorDialogRef: errorDialog
        }

        ErrorDialog {
            id: errorDialog
            resizeComponent: resizeHandlesComponent
        }

        Connections {
            target: backend
            function onErrorMessage(message) {
                errorDialog.message = message
                errorDialog.open()
            }
            function onIgdbGameDetailsJson(payload) {
                if (!payload)
                    return
                var parsed = {}
                try {
                    parsed = JSON.parse(payload)
                } catch (e) {
                    return
                }
                backendIgdbDetailsHandler(parsed)
            }
            function onIgdbSearchResults(results) {
                igdbSearchModel.clear()
                for (var i = 0; i < results.length; i++) {
                    igdbSearchModel.append(results[i])
                }
            }
            function onIgdbGameDetails(details) {
                backendIgdbDetailsHandler(details)
            }

            function backendIgdbDetailsHandler(details) {
                if (!details || !details.name) {
                    var target = appRoot.metadataTarget === "edit" ? editDialog.details : addDialog.details
                    var fallbackName = target.nameField.text || ""
                    if (!fallbackName) {
                        return
                    }
                    details = details || {}
                    details.name = fallbackName
                }
                var target = appRoot.metadataTarget === "edit" ? editDialog.details : addDialog.details
                target.nameField.text = details.name || ""
                target.sortingNameField.text = details.name || ""
                var missing = []
                var igdbDebug = ""
                if (details.first_release_date) {
                    var dt = new Date(details.first_release_date * 1000)
                    var month = (dt.getUTCMonth() + 1).toString().padStart(2, "0")
                    var day = dt.getUTCDate().toString().padStart(2, "0")
                    target.releaseDateField.text = dt.getUTCFullYear() + "-" + month + "-" + day
                } else {
                    missing.push("Release Date")
                }
                if (details.platforms && details.platforms.length > 0) {
                    var plat = details.platforms[0].name || ""
                    for (var pi = 0; pi < details.platforms.length; pi++) {
                        var pname = (details.platforms[pi].name || "").toLowerCase()
                        if (pname === "pc (microsoft windows)") {
                            plat = details.platforms[pi].name
                            break
                        }
                    }
                    target.platformField.currentIndex = appRoot.platformIndex(plat)
                    target.platformField.editText = plat
                } else {
                    missing.push("Platform")
                }
                if (details.genres && details.genres.length > 0) {
                    var g = details.genres.map(function(x) { return x.name }).filter(Boolean)
                    target.genreField.text = g.join(", ")
                } else {
                    missing.push("Genres")
                }
                if (details.collection && details.collection.name) {
                    target.seriesField.text = details.collection.name || ""
                } else if (details.collections && details.collections.length > 0) {
                    target.seriesField.text = details.collections[0].name || ""
                } else {
                    missing.push("Series")
                }
                if (details.summary) {
                    target.notesField.text = details.summary
                } else {
                    missing.push("Description")
                }
                if (details.release_dates && details.release_dates.length > 0) {
                    var regionMap = {
                        1: "Europe",
                        2: "North America",
                        3: "Australia",
                        4: "New Zealand",
                        5: "Japan",
                        6: "China",
                        7: "Asia",
                        8: "Worldwide"
                    }
                    var regions = []
                    for (var i = 0; i < details.release_dates.length; i++) {
                        var code = details.release_dates[i].region
                        if (regionMap[code] && regions.indexOf(regionMap[code]) === -1)
                            regions.push(regionMap[code])
                    }
                    if (regions.length > 0)
                        target.regionField.text = regions.join(", ")
                    else
                        missing.push("Region")
                } else {
                    missing.push("Region")
                }
                if (details.game_modes && details.game_modes.length > 0) {
                    var c = details.game_modes.map(function(x) { return x.name }).filter(Boolean)
                    target.categoriesField.text = c.join(", ")
                } else {
                    missing.push("Categories")
                }
                if (details.themes && details.themes.length > 0) {
                    var f = details.themes.map(function(x) { return x.name }).filter(Boolean)
                    target.featuresField.text = f.join(", ")
                } else {
                    missing.push("Features")
                }
                if (details.involved_companies && details.involved_companies.length > 0) {
                    var devs = []
                    var pubs = []
                    for (var i = 0; i < details.involved_companies.length; i++) {
                        var comp = details.involved_companies[i]
                        var cname = comp.company && comp.company.name ? comp.company.name : ""
                        if (!cname)
                            continue
                        if (comp.developer)
                            devs.push(cname)
                        if (comp.publisher)
                            pubs.push(cname)
                    }
                    if (devs.length > 0)
                        target.developersField.text = devs.join(", ")
                    else
                        missing.push("Developers")
                    if (pubs.length > 0)
                        target.publishersField.text = pubs.join(", ")
                    else
                        missing.push("Publishers")
                } else {
                    missing.push("Developers")
                    missing.push("Publishers")
                }
                if (details.age_ratings && details.age_ratings.length > 0) {
                    var ratingText = appRoot.formatAgeRating(details.age_ratings)
                    if (ratingText)
                        target.ageRatingField.text = ratingText
                    else
                        missing.push("Age Rating")
                } else {
                    missing.push("Age Rating")
                }
                if (details.rating !== undefined && details.rating !== null) {
                    target.userScoreField.text = Math.round(details.rating).toString()
                } else {
                    missing.push("User Score")
                }
                if (details.aggregated_rating !== undefined && details.aggregated_rating !== null) {
                    target.criticScoreField.text = Math.round(details.aggregated_rating).toString()
                } else {
                    missing.push("Critic Score")
                }
                if (details.category !== undefined && details.category !== null) {
                    var src = appRoot.mapIgdbCategory(details.category)
                    if (src)
                        target.sourceField.text = src
                    else
                        missing.push("Source")
                } else {
                    missing.push("Source")
                }
                if (details.websites && details.websites.length > 0) {
                    var linkRows = []
                    for (var wi = 0; wi < details.websites.length; wi++) {
                        var w = details.websites[wi]
                        if (!w || !w.url)
                            continue
                        linkRows.push({ type: appRoot.mapIgdbLinkType(w.category), url: w.url })
                    }
                    if (linkRows.length > 0)
                        target.loadLinksFromJson(JSON.stringify(linkRows))
                }
                if (missing.length > 0) {
                    var msg = "Missing from IGDB: " + missing.join(", ")
                    // suppressed dialog
                }
            }
            function onIgdbCoverDownloaded(success, imagePath, gameName) {
                if (success) {
                    if (appRoot.metadataTarget === "edit") {
                        editDialog.details.coverField.text = imagePath
                        if (!editDialog.details.nameField.text)
                            editDialog.details.nameField.text = gameName
                    } else {
                        addDialog.details.coverField.text = imagePath
                        if (!addDialog.details.nameField.text)
                            addDialog.details.nameField.text = gameName
                    }
                } else {
                    var targetName = appRoot.metadataTarget === "edit" ? editDialog.details.nameField.text : addDialog.details.nameField.text
                    // suppressed dialog
                }
            }
            function onEmulatorsChanged() {
                                                                appRoot.refreshEmulators()
            }
        }

        FileDialog {
            id: fileDialog
            property var targetField
            nameFilters: ["All files (*)"]
            onAccepted: {
                if (targetField) {
                    var picked = selectedFile
                    if (!picked && selectedFiles && selectedFiles.length > 0)
                        picked = selectedFiles[0]
                    targetField.text = appRoot.toLocalPath(picked)
                }
            }
        }

        FolderDialog {
            id: folderDialog
            property var targetField
            onAccepted: {
                if (targetField) {
                    var picked = selectedFolder
                    targetField.text = appRoot.toLocalPath(picked)
                }
            }
        }

        UrlDownloadDialog {
            id: urlDialog
            backendRef: backend
            resizeComponent: resizeHandlesComponent
        }

        ListModel { id: igdbSearchModel }

        IgdbSearchDialog {
            id: igdbSearchDialog
            searchModel: igdbSearchModel
            resizeComponent: resizeHandlesComponent
            onSearchTextChanged: igdbSearchDebounce.restart()
            onGameChosen: function(gameId, name) {
                if (appRoot.metadataTarget === "edit")
                    editDialog.details.nameField.text = name
                else
                    addDialog.details.nameField.text = name
                backend.fetch_igdb_game_details(gameId)
            }
        }

        Timer {
            id: igdbSearchDebounce
            interval: 350
            repeat: false
            onTriggered: backend.search_igdb_titles(igdbSearchDialog.queryText)
        }

        function openFileDialog(target, filters) {
            fileDialog.targetField = target
            if (filters)
                fileDialog.nameFilters = filters.split(";;")
            fileDialog.open()
        }

        function openFolderDialog(target) {
            folderDialog.targetField = target
            folderDialog.open()
        }

        function confirmRemoveSelected() {
            if (backend.selectedGameName === "")
                return
            removeConfirmText.text = "Remove '" + backend.selectedGameName + "' from library?"
            removeConfirmDialog.open()
        }

        Menu {
            id: gameContextMenu
            width: 220
            palette.text: "#f0f0f0"
            palette.windowText: "#f0f0f0"
            palette.buttonText: "#f0f0f0"
            background: Rectangle {
                color: "#1c1c1c"
                radius: 6
                border.color: "#2a2a2a"
            }
            MenuItem {
                text: "Edit"
                contentItem: Text {
                    text: parent.text
                    color: "#f0f0f0"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                onTriggered: editDialog.open()
            }
            MenuItem {
                text: backend.selectedGameHidden ? "Unhide" : "Hide"
                contentItem: Text {
                    text: parent.text
                    color: "#f0f0f0"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                enabled: backend.selectedGameName !== ""
                onTriggered: backend.set_selected_hidden(!backend.selectedGameHidden)
            }
            MenuItem {
                text: "Sync HLTB Playtime"
                contentItem: Text {
                    text: parent.text
                    color: "#f0f0f0"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                onTriggered: {
                    var result = backend.sync_selected_hltb()
                    errorDialog.message = result
                    errorDialog.open()
                }
            }
            MenuItem {
                text: "Create Desktop Shortcut"
                contentItem: Text {
                    text: parent.text
                    color: "#f0f0f0"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                onTriggered: {
                    var result = backend.create_desktop_shortcut()
                    errorDialog.message = result
                    errorDialog.open()
                }
            }
            MenuItem {
                text: "Remove"
                contentItem: Text {
                    text: parent.text
                    color: "#f0f0f0"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                enabled: backend.selectedGameName !== ""
                onTriggered: appRoot.confirmRemoveSelected()
            }
            MenuItem {
                text: "Set RetroAchievements ID"
                contentItem: Text {
                    text: parent.text
                    color: "#f0f0f0"
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                visible: backend.selectedGameIsEmulated
                onTriggered: {
                    raIdField.text = backend.selectedGameRaGameId
                    raIdDialog.open()
                }
            }
        }

        Dialog {
            id: removeConfirmDialog
            title: "Confirm Remove"
            modal: true
            standardButtons: Dialog.Yes | Dialog.No
            width: 440
            height: 180
            x: Math.round((root.width - width) / 2)
            y: Math.round((root.height - height) / 2)
            background: Rectangle { color: "transparent"; border.color: "transparent" }
            onAccepted: backend.remove_selected()

            contentItem: Rectangle {
                color: "#1e1f25"
                radius: 8
                border.color: "#2a2a2a"
                anchors.fill: parent

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10

                    CrispText {
                        id: removeConfirmText
                        text: ""
                        color: "#e8e8e8"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }
        }

        Dialog {
            id: raIdDialog
            title: "RetroAchievements ID"
            modal: true
            standardButtons: Dialog.Ok | Dialog.Cancel
            width: 420
            height: 170
            x: Math.round((root.width - width) / 2)
            y: Math.round((root.height - height) / 2)
            background: Rectangle { color: "transparent"; border.color: "transparent" }

            contentItem: Rectangle {
                color: "#1e1f25"
                radius: 8
                border.color: "#2a2a2a"
                anchors.fill: parent

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8
                    CrispText { text: "RetroAchievements Game ID"; color: "#e8e8e8" }
                    TextField {
                        id: raIdField
                        Layout.fillWidth: true
                        placeholderText: "e.g. 12345 (leave blank to clear)"
                    }
                }
            }

            onAccepted: {
                backend.set_selected_ra_game_id(raIdField.text)
            }
        }
        SettingsMenu {
            id: settingsMenu
            backendRef: backend
            emulatorDialogRef: emulatorDialog
            riotClientDialogRef: riotClientDialog
            steamApiDialogRef: steamApiDialog
            steamEmuLocationsDialogRef: steamEmuLocationsDialog
            errorDialogRef: errorDialog
        }
        function splitCsv(text) {
            if (!text)
                return []
            return text.split(",").map(function(item) { return item.trim() }).filter(function(item) { return item.length > 0 })
        }

        function mapIgdbCategory(category) {
            var map = {
                0: "Main Game",
                1: "DLC / Add-on",
                2: "Expansion",
                3: "Bundle",
                4: "Standalone Expansion",
                5: "Mod",
                6: "Episode",
                7: "Season",
                8: "Remake",
                9: "Remaster",
                10: "Expanded Game",
                11: "Port",
                12: "Fork",
                13: "Pack",
                14: "Update"
            }
            return map[category] || ""
        }

        function formatAgeRating(ratings) {
            if (!ratings || ratings.length === 0)
                return ""
            var best = ratings[0]
            var category = best.category
            var rating = best.rating
            if (category === 1) {
                var esrb = {
                    6: "RP",
                    7: "EC",
                    8: "E",
                    9: "E10+",
                    10: "T",
                    11: "M",
                    12: "AO"
                }
                return "ESRB " + (esrb[rating] || rating)
            }
            if (category === 2) {
                var pegi = {
                    1: "3",
                    2: "7",
                    3: "12",
                    4: "16",
                    5: "18"
                }
                return "PEGI " + (pegi[rating] || rating)
            }
            return "Rating " + rating
        }

        function mapIgdbLinkType(category) {
            var map = {
                1: "website",
                2: "wiki",
                3: "wikipedia",
                4: "facebook",
                5: "twitter",
                6: "twitch",
                8: "instagram",
                9: "youtube",
                13: "steam",
                14: "reddit",
                15: "itch.io",
                16: "epic",
                17: "gog",
                18: "discord"
            }
            return map[category] || "website"
        }

        function refreshEmulators() {
            appRoot.emulatorKeys = Object.keys(root.backendRef.emulatorsData || {})
            if (appRoot.emulatorKeys.length === 0) {
                appRoot.selectedEmulatorId = ""
            } else if (appRoot.selectedEmulatorId === "" || appRoot.emulatorKeys.indexOf(appRoot.selectedEmulatorId) === -1) {
                appRoot.selectedEmulatorId = appRoot.emulatorKeys[0]
            }
        }

        RiotClientDialog {
            id: riotClientDialog
            backendRef: backend
            appRootRef: appRoot
        }

        SteamApiDialog {
            id: steamApiDialog
            backendRef: backend
        }

        SteamEmuLocationsDialog {
            id: steamEmuLocationsDialog
            backendRef: backend
        }

        function openUrlDialog(mediaType, target, gameName) {
            urlDialog.mediaType = mediaType
            urlDialog.targetField = target
            urlDialog.gameName = gameName || ""
            urlDialog.urlText = ""
            urlDialog.open()
        }

        function resolveMedia(path) {
            if (!path)
                return ""
            var s = path.toString()
            if (s.startsWith("file://") || s.startsWith("http://") || s.startsWith("https://"))
                return s
            if (/^[A-Za-z]:[\\/]/.test(s))
                return "file:///" + s.replace(/\\/g, "/")
            return backend.resolve_media_url(s)
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

        Component.onCompleted: {
            heroSource = backend.selectedGameHero
            lastHeroId = backend.selectedGameId
        }
    }

    Timer {
        id: heroUpdateTimer
        interval: 120
        repeat: false
        onTriggered: {
            if (backend.selectedGameId !== appRoot.lastHeroId) {
                appRoot.lastHeroId = backend.selectedGameId
                appRoot.heroSource = backend.selectedGameHero
            }
        }
    }

    Connections {
        target: backend
        function onLibraryChanged() {
            heroUpdateTimer.restart()
        }
    }
}
