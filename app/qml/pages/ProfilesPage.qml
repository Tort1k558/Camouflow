import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

Item {
    id: root
    clip: true
    property string editingId: ""
    property string editingEngine: "camoufox"
    property var contextActions: ({})
    property string editingProfile: ""
    property string contextProfile: ""
    property string profileSettingsTab: "profile"
    property var loadedTabs: ({})
    property bool cookiesLoading: false
    property var proxyChoices: []
    Connections {
        target: profilesBridge
        function onModelChanged() { root.contextActions = profilesBridge.actionState(root.contextProfile) }
        function onProfileSaved(name) { if (name === root.editingProfile) profileDialog.close() }
        function onCookiesLoaded(name, payload, error) {
            if (name !== root.editingProfile || !root.cookiesLoading) return
            root.cookiesLoading = false
            if (error) { appState.notify(error); root.loadedTabs.cookies = false }
            else profileCookiesJson.text = payload
        }
    }

    function openProfileModal(profileName) {
        var data = profilesBridge.getProfile(profileName, "")
        if (!data.name) { appState.notify("Profile is unavailable; refresh the list"); return }
        editingEngine = data.engine
        editingId = data.id || ""
        editingProfile = profileName
        editName.text = data.name || profileName
        editStage.text = data.stage || ""
        loadedTabs = ({})
        cookiesLoading = false
        proxyChoices = profilesBridge.proxyOptions()
        editProxyChoice.currentIndex = 0
        editProxy.text = data.proxy_url || ""
        editLocale.text = data.locale || ""
        editTimezone.text = data.timezone || ""
        editUserAgent.text = data.user_agent || ""
        editWebgl.text = data.webgl_vendor || ""
        editCpu.text = data.hardware_concurrency || ""
        profileSettingsTab = "profile"
        profileDialog.open()
    }
    function openProfileTab(profileName, tab) {
        if (profileName && profileName !== editingProfile) {
            openProfileModal(profileName)
        } else if (!profileDialog.visible) {
            profileDialog.open()
        }
        profileSettingsTab = tab
        if (loadedTabs[tab]) return
        loadedTabs[tab] = true
        if (tab === "variables") profileVarsJson.text = profilesBridge.getProfileVariables(editingProfile)
        if (tab === "cookies") { profileCookiesJson.text = ""; cookiesLoading = true; profilesBridge.loadCookies(editingProfile) }
        if (tab === "browser") profileBrowserSettingsJson.text = profilesBridge.getProfileBrowserSettingsJson(editingProfile, root.editingEngine)
    }
    function openVariablesModal(profileName) {
        openProfileTab(profileName, "variables")
    }
    function openCookiesModal(profileName) {
        openProfileTab(profileName, "cookies")
    }
    function openBrowserOverridesModal(profileName) {
        openProfileTab(profileName, "browser")
    }
    function openTagsModal() {
        settingsBridge.refresh()
        tagName.text = ""
        tagsDialog.open()
    }

    component ProfileTab: Rectangle {
        id: profileTab
        property string title: "Tab"
        property string tabId: "profile"
        readonly property bool active: root.profileSettingsTab === tabId
        width: Math.max(92, tabText.implicitWidth + 28)
        height: 34
        radius: 10
        color: active ? Theme.primary : Theme.subtle
        border.color: active ? Theme.primaryLight : Theme.border
        Text { id: tabText; anchors.centerIn: parent; text: profileTab.title; color: active ? Theme.primaryText : Theme.muted; font.pixelSize: 12; font.weight: Font.DemiBold }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.openProfileTab("", profileTab.tabId) }
    }

    Component.onCompleted: profilesBridge.setSearch("")
    function confirmDelete(name) {
        confirmDialog.ask('Delete profile "' + name + '"? This action cannot be undone.', function() { profilesBridge.deleteProfile(name) })
    }
    ConfirmDialog { id: confirmDialog }
    Menu {
        id: profileImportMenu
        parent: importButton; y: importButton.height
        MenuItem { text: "Import profile list"; onTriggered: importDialog.open() }
        MenuItem { text: appState.cloudEnabled ? "Restore archive (local workspace only)" : "Restore archive"; enabled: !appState.cloudEnabled; onTriggered: { profileActions.mode = "restore"; profileActionsDialog.open() } }
    }
    Menu {
        id: selectedActionsMenu
        parent: selectedActionsButton; y: selectedActionsButton.height
        MenuItem { text: "Schedule scenario"; enabled: scenariosBridge.canRun; onTriggered: appState.setPage("ScenarioRuns") }
        MenuItem { text: appState.cloudEnabled ? "Bulk edit / export (local only)" : "Bulk edit / export"; enabled: !appState.cloudEnabled; onTriggered: { profileActions.mode = "bulk"; profileActionsDialog.open() } }
        MenuItem { text: appState.cloudEnabled ? "Profile archive (local only)" : "Full profile archive"; enabled: !appState.cloudEnabled; onTriggered: { profileActions.mode = "backup"; profileActionsDialog.open() } }
    }
    WorkspaceDialog {
        id: profileActionsDialog
        objectName: "profileActionsDialog"
        anchors.centerIn: Overlay.overlay
        width: Math.min(880, root.width - 48); height: Math.min(720, root.height - 48)
        title: profileActions.mode === "bulk" ? "Selected profile actions" : profileActions.mode === "restore" ? "Restore profile archive" : "Profile archives"
        contentItem: ProfileActionsPanel { id: profileActions; objectName: "profileActionsPanel" }
        footer: Item {
            height: 56
            PrimaryButton { text: "Close"; secondary: true; anchors.right: parent.right; anchors.rightMargin: 20; onClicked: profileActionsDialog.close() }
        }
    }

    ColumnLayout {
        anchors.fill: parent; anchors.margins: 28; spacing: 14
        RowLayout {
            Layout.fillWidth: true
            PageHeader { Layout.fillWidth: true; height: 72; title: "Profiles"; subtitle: "Browser sessions, identities and assigned connections" }
            PrimaryButton { id: importButton; text: "Import"; icon: "save"; secondary: true; enabled: profilesBridge.canManage && !profilesBridge.busy; onClicked: profileImportMenu.open() }
            PrimaryButton { text: "New Profile"; icon: "plus"; enabled: profilesBridge.canManage && !profilesBridge.busy; onClicked: profilesBridge.createProfile() }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            SearchBox { id: search; Layout.fillWidth: true; Layout.preferredHeight: 42; placeholder: "Search profiles, tags or proxies"; onTextChanged: profilesBridge.setSearch(text) }
            PrimaryButton { id: selectedActionsButton; text: "Selected actions"; enabled: operationsBridge.selectedProfiles !== ""; secondary: true; onClicked: selectedActionsMenu.open() }
            PrimaryButton { text: "Run scenarios"; icon: "play"; secondary: true; enabled: scenariosBridge.canRun && profileList.count > 0; onClicked: appState.setPage("ScenarioRuns") }
            PrimaryButton { text: "Local variables"; secondary: true; onClicked: variablesDialog.open() }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            ListView {
            Layout.fillWidth: true
            Layout.preferredHeight: 38
            orientation: ListView.Horizontal
            spacing: 8
            model: profilesBridge.stagesModel
            clip: true
            delegate: Rectangle {
                width: tagText.width + 34
                height: 34
                radius: 11
                color: model.selected ? Theme.primary : Theme.subtle
                border.color: model.selected ? Theme.primaryLight : Theme.border
                Text {
                    id: tagText
                    anchors.centerIn: parent
                    text: model.name + "  " + model.count
                    color: model.selected ? Theme.primaryText : Theme.muted
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: profilesBridge.setStageFilter(model.name) }
            }
        }
            PrimaryButton { text: "Local tag presets"; secondary: true; enabled: profilesBridge.canManage && !profilesBridge.busy; onClicked: root.openTagsModal() }
        }
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            id: profileList
            EmptyState { anchors.centerIn: parent; width: Math.min(360, parent.width); visible: profileList.count === 0 && !profilesBridge.loading; title: search.text ? "No matching profiles" : "Your first profile starts here"; description: search.text ? "Try a different name, tag or proxy." : "Create a browser profile or import existing accounts."; icon: "user" }
            BusyIndicator { anchors.centerIn: parent; running: profilesBridge.loading && profileList.count === 0; visible: running }
            model: profilesBridge.model
            spacing: 14
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            delegate: ProfileRow {
                id: profileRow
                width: ListView.view.width
                chosen: operationsBridge.selectedProfiles.split("\n").indexOf(model.name) >= 0
                onSelectionToggled: function(selected) { operationsBridge.selectProfile(model.name, selected) }
                name: model.name
                ident: model.id
                browser: model.browser
                proxy: model.proxy
                health: model.health
                lastActive: model.lastActive
                status: model.status
                tags: model.tags
                running: model.running
                lockedBy: model.lockedBy
                lockExpires: model.lockExpires
                canRun: profilesBridge.canRun
                startAllowed: model.startAllowed
                stopAllowed: model.stopAllowed
                canManage: model.editAllowed
                canAdmin: model.deleteAllowed
                height: 78
                onStartClicked: profilesBridge.startProfile(model.name)
                onStopClicked: profilesBridge.stopProfile(model.name)
                onSettingsClicked: root.openProfileModal(model.name)
                onDeleteClicked: root.confirmDelete(model.name)
                onContextRequested: function(x, y) {
                    root.contextProfile = model.name
                    root.contextActions = profilesBridge.actionState(model.name)
                    var point = profileRow.mapToItem(root, x, y)
                    profileMenu.popup(point.x, point.y)
                }
            }
        }
        Text { text: profileList.count + " profiles shown"; color: Theme.dim; font.pixelSize: 11 }
    }
    WorkspaceDialog {
        id: importDialog
        objectName: "importDialog"
        modal: true
        width: Math.min(900, root.width - 80)
        height: Math.min(680, root.height - 80)
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: Theme.radiusLg; border.color: Theme.border }
        contentItem: Column {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14
            Text { text: "Import Profiles"; color: Theme.text; font.pixelSize: 24; font.weight: Font.DemiBold }
            FormField { id: importTemplate; width: parent.width; label: "Account parse template"; text: "{email};{password};{secret_key};{extra};{twofa_url}" }
            Row {
                width: parent.width
                spacing: 12
                FormField { id: importTag; width: (parent.width - 12) / 2; label: "Default tag" }
                Rectangle {
                    width: (parent.width - 12) / 2
                    height: 62
                    color: "transparent"
                    Text { text: "Proxy pool"; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold }
                    Rectangle {
                        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                        height: 40; radius: Theme.radiusSm; color: Theme.subtle; border.color: Theme.border
                        ComboBox {
                            id: importProxyPool
                            anchors.fill: parent
                            anchors.margins: 6
                            model: proxiesBridge.poolsModel
                            textRole: "name"
                            background: Item {}
                            contentItem: Text { text: importProxyPool.displayText || "Default"; color: Theme.text; verticalAlignment: Text.AlignVCenter; font.pixelSize: 13 }
                        }
                    }
                }
            }
            Text { text: "Profiles, one per line"; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold }
            Rectangle {
                width: parent.width
                height: parent.height - 230
                radius: 14
                color: Theme.subtle
                border.color: Theme.border
                TextArea {
                    id: importLines
                    anchors.fill: parent
                    anchors.margins: 12
                    color: Theme.text
                    placeholderText: "user@example.com;pass123;SECRET;note;https://2fa.example.com/"
                    placeholderTextColor: Theme.dim
                    background: Item {}
                    font.pixelSize: 13
                }
            }
            Row {
                spacing: 10
                PrimaryButton {
                    width: 120
                    text: "Import"
                    icon: "save"
                    enabled: profilesBridge.canManage && !profilesBridge.busy
                    onClicked: {
                        profilesBridge.importProfiles(importLines.text, importTemplate.text, importTag.text, importProxyPool.currentText === "All pools" ? "" : importProxyPool.currentText)
                        importDialog.close()
                    }
                }
                PrimaryButton { width: 100; text: "Cancel"; secondary: true; onClicked: importDialog.close() }
            }
        }
    }

    WorkspaceDialog {
        id: tagsDialog
        objectName: "tagsDialog"
        modal: true
        width: Math.min(480, root.width - 80)
        height: 520
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: Theme.radiusLg; border.color: Theme.border }
        contentItem: Column {
            spacing: 14
            padding: 22
            RowLayout {
                width: parent.width - 44
                Text { text: "Profile Tags"; color: Theme.text; font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
                PrimaryButton { Layout.preferredWidth: 40; text: ""; icon: "plus"; enabled: profilesBridge.canManage && !profilesBridge.busy; onClicked: tagCreateDialog.open() }
            }
            Text { width: parent.width - 44; text: "Create tags here, then assign them in profile settings."; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap }
            ListView {
                width: parent.width - 44
                height: 360
                model: settingsBridge.stagesModel
                spacing: 8
                clip: true
                delegate: Rectangle {
                    width: ListView.view.width
                    height: 42
                    radius: 11
                    color: Theme.subtle
                    border.color: Theme.border
                    Text { anchors.left: parent.left; anchors.leftMargin: 12; anchors.verticalCenter: parent.verticalCenter; text: model.name; color: Theme.text; font.pixelSize: 13; font.weight: Font.DemiBold }
                    PrimaryButton { anchors.right: parent.right; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter; width: 34; height: 28; text: ""; icon: "trash"; danger: true; enabled: profilesBridge.canManage && !profilesBridge.busy; onClicked: { settingsBridge.deleteStage(model.name); profilesBridge.refresh() } }
                }
            }
        }
    }

    WorkspaceDialog {
        id: tagCreateDialog
        objectName: "tagCreateDialog"
        modal: true
        width: Math.min(420, root.width - 100)
        height: 210
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: Theme.radiusLg; border.color: Theme.border }
        contentItem: Column {
            spacing: 14
            padding: 22
            Text { text: "New Tag"; color: Theme.text; font.pixelSize: 20; font.weight: Font.DemiBold }
            FormField { id: tagName; width: parent.width - 44; label: "Tag name" }
            Row {
                spacing: 10
                PrimaryButton { width: 110; text: "Create"; icon: "plus"; enabled: profilesBridge.canManage && !profilesBridge.busy; onClicked: { settingsBridge.addStage(tagName.text); profilesBridge.refresh(); tagCreateDialog.close() } }
                PrimaryButton { width: 100; text: "Cancel"; secondary: true; onClicked: tagCreateDialog.close() }
            }
        }
    }

    WorkspaceDialog {
        id: profileDialog
        objectName: "profileDialog"
        modal: true
        width: Math.min(820, root.width - 80)
        height: Math.min(720, root.height - 80)
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: Theme.radiusLg; border.color: Theme.border }
        contentItem: Flickable {
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            contentWidth: width
            contentHeight: modalContent.height + 44
            clip: true
            Column {
                id: modalContent
                width: parent.width - 44
                x: 22
                y: 22
                spacing: 18
                Text { text: "Profile Settings"; color: Theme.text; font.pixelSize: 24; font.weight: Font.DemiBold }
                Text { text: "Profile engine: " + root.editingEngine + " / ID: " + (root.editingId || "local"); color: Theme.muted; font.pixelSize: 13 }
                Row {
                    spacing: 8
                    ProfileTab { title: "Profile"; tabId: "profile" }
                    ProfileTab { title: "Variables"; tabId: "variables" }
                    ProfileTab { title: "Cookies"; tabId: "cookies" }
                    ProfileTab { title: "Browser JSON"; tabId: "browser" }
                }
                Column {
                    width: parent.width
                    spacing: 18
                    visible: root.profileSettingsTab === "profile"
                    GridLayout {
                        width: parent.width
                        columns: 2
                        columnSpacing: 16
                        rowSpacing: 14
                        FormField { id: editName; Layout.fillWidth: true; label: "Name" }
                        FormField { id: editStage; Layout.fillWidth: true; label: "Tag / Scenario" }
                        ComboBox {
                            id: editProxyChoice
                            Layout.fillWidth: true; Layout.columnSpan: 2
                            model: root.proxyChoices; textRole: "label"
                        }
                        FormField {
                            id: editProxy; Layout.fillWidth: true; Layout.columnSpan: 2
                            visible: editProxyChoice.currentIndex <= 0
                            label: "Proxy connection"; placeholder: "socks5://user:password@host:port (empty = no proxy)"
                        }
                    }
                    Rectangle { width: parent.width; height: 1; color: Theme.border }
                    Text { text: "Browser Overrides"; color: Theme.text; font.pixelSize: 18; font.weight: Font.DemiBold }
                    GridLayout {
                        width: parent.width
                        columns: 2
                        columnSpacing: 16
                        rowSpacing: 14
                        FormField { id: editLocale; Layout.fillWidth: true; label: "Locale"; placeholder: "en-US" }
                        FormField { id: editTimezone; Layout.fillWidth: true; label: "Timezone"; placeholder: "America/New_York" }
                        FormField { id: editUserAgent; Layout.fillWidth: true; label: "User Agent" }
                        FormField { id: editWebgl; Layout.fillWidth: true; label: "WebGL / GPU vendor" }
                        FormField { id: editCpu; Layout.fillWidth: true; label: "CPU cores" }
                    }
                }
                Column {
                    width: parent.width
                    spacing: 12
                    visible: root.profileSettingsTab === "variables"
                    Text { text: "Profile variables"; color: Theme.text; font.pixelSize: 18; font.weight: Font.DemiBold }
                    Text { text: "JSON object available to this profile's scenarios."; color: Theme.muted; font.pixelSize: 12 }
                    Rectangle { width: parent.width; height: 400; radius: 14; color: Theme.subtle; border.color: Theme.border
                        TextArea { id: profileVarsJson; anchors.fill: parent; anchors.margins: 12; color: Theme.text; font.family: "Consolas"; font.pixelSize: 12; background: Item {} }
                    }
                }
                Column {
                    width: parent.width
                    spacing: 12
                    visible: root.profileSettingsTab === "cookies"
                    Text { text: "Cookies"; color: Theme.text; font.pixelSize: 18; font.weight: Font.DemiBold }
                    Text { text: "Edit JSON array and save. Encrypted Chromium values may be read-only."; color: Theme.muted; font.pixelSize: 12 }
                    Rectangle { width: parent.width; height: 400; radius: 14; color: Theme.subtle; border.color: Theme.border
                        TextArea { id: profileCookiesJson; enabled: !root.cookiesLoading; placeholderText: root.cookiesLoading ? "Loading cookies..." : ""; anchors.fill: parent; anchors.margins: 12; color: Theme.text; font.family: "Consolas"; font.pixelSize: 12; background: Item {} }
                    }
                }
                Column {
                    width: parent.width
                    spacing: 12
                    visible: root.profileSettingsTab === "browser"
                    Text { text: "Browser JSON"; color: Theme.text; font.pixelSize: 18; font.weight: Font.DemiBold }
                    Text { text: "Overrides for current engine: " + root.editingEngine; color: Theme.muted; font.pixelSize: 12 }
                    Rectangle { width: parent.width; height: 400; radius: 14; color: Theme.subtle; border.color: Theme.border
                        TextArea { id: profileBrowserSettingsJson; anchors.fill: parent; anchors.margins: 12; color: Theme.text; font.family: "Consolas"; font.pixelSize: 12; background: Item {} wrapMode: TextArea.Wrap }
                    }
                }
                Row {
                    spacing: 12
                    visible: root.profileSettingsTab === "profile"
                    PrimaryButton { width: 120; text: "Save"; icon: "save"; enabled: profilesBridge.canManage && !profilesBridge.busy; onClicked: {
                        var choice = root.proxyChoices[editProxyChoice.currentIndex] || {}
                        profilesBridge.saveProfileForm(root.editingProfile, JSON.stringify({
                            name: editName.text, stage: editStage.text, engine: root.editingEngine,
                            pool: choice.pool || "", proxy: editProxyChoice.currentIndex > 0 ? choice.value : editProxy.text,
                            locale: editLocale.text, timezone: editTimezone.text, user_agent: editUserAgent.text,
                            webgl_vendor: editWebgl.text, hardware_concurrency: editCpu.text
                        })) } }
                    PrimaryButton { width: 110; text: "Cancel"; secondary: true; onClicked: profileDialog.close() }
                }
                Row {
                    spacing: 12
                    visible: root.profileSettingsTab === "variables"
                    PrimaryButton { width: 120; text: "Save"; icon: "save"; enabled: profilesBridge.canManage && !profilesBridge.busy; onClicked: profilesBridge.saveProfileVariables(root.editingProfile, profileVarsJson.text) }
                    PrimaryButton { width: 110; text: "Cancel"; secondary: true; onClicked: profileDialog.close() }
                }
                Row {
                    spacing: 12
                    visible: root.profileSettingsTab === "cookies"
                    PrimaryButton { width: 120; text: "Refresh"; secondary: true; enabled: !root.cookiesLoading; onClicked: { root.cookiesLoading = true; profilesBridge.loadCookies(root.editingProfile) } }
                    PrimaryButton { width: 120; text: "Save"; icon: "save"; enabled: profilesBridge.canManage && !profilesBridge.busy && !root.cookiesLoading; onClicked: profilesBridge.saveProfileCookiesJson(root.editingProfile, profileCookiesJson.text) }
                    PrimaryButton { width: 110; text: "Cancel"; secondary: true; onClicked: profileDialog.close() }
                }
                Row {
                    spacing: 12
                    visible: root.profileSettingsTab === "browser"
                    PrimaryButton { width: 120; text: "Save"; icon: "save"; enabled: profilesBridge.canManage && !profilesBridge.busy; onClicked: profilesBridge.saveProfileBrowserSettingsJson(root.editingProfile, root.editingEngine, profileBrowserSettingsJson.text) }
                    PrimaryButton { width: 110; text: "Cancel"; secondary: true; onClicked: profileDialog.close() }
                }
            }
        }
    }

    WorkspaceDialog {
        id: variablesDialog
        objectName: "variablesDialog"
        modal: true
        width: Math.min(860, root.width - 80)
        height: Math.min(560, root.height - 80)
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: Theme.radiusLg; border.color: Theme.border }
        contentItem: Column {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 16
            RowLayout {
                width: parent.width
                height: 38
                Text { text: "Variables on this computer"; color: Theme.text; font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
                PrimaryButton { Layout.preferredWidth: 104; text: "Close"; secondary: true; onClicked: variablesDialog.close() }
            }
            RowLayout {
                width: parent.width
                height: parent.height - 54
                spacing: 16
                ListView {
                    Layout.preferredWidth: 330
                    Layout.fillHeight: true
                    model: settingsBridge.variablesModel
                    spacing: 8
                    clip: true
                    delegate: Rectangle {
                        width: ListView.view.width
                        height: 54
                        radius: 12
                        color: Theme.subtle
                        border.color: Theme.border
                        Text { anchors.left: parent.left; anchors.leftMargin: 12; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 24; text: "[" + model.type + "] " + model.key + ": " + model.value; color: Theme.muted; font.pixelSize: 12; elide: Text.ElideRight }
                        MouseArea { anchors.fill: parent; onClicked: { sharedKey.text = model.key; sharedType.text = model.type; sharedValue.text = settingsBridge.getVariable(model.key).value || "" } }
                    }
                }
                Column {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 14
                    FormField { id: sharedKey; width: parent.width; label: "Key" }
                    Row {
                        width: parent.width
                        spacing: 10
                        PrimaryButton { width: (parent.width - 20) / 3; text: "string"; secondary: sharedType.text !== "string"; onClicked: sharedType.text = "string" }
                        PrimaryButton { width: (parent.width - 20) / 3; text: "number"; secondary: sharedType.text !== "number"; onClicked: sharedType.text = "number" }
                        PrimaryButton { width: (parent.width - 20) / 3; text: "list"; secondary: sharedType.text !== "list"; onClicked: sharedType.text = "list" }
                    }
                    FormField { id: sharedType; visible: false; text: "string" }
                    Text { text: "Value"; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold }
                    Rectangle { width: parent.width; height: 190; radius: Theme.radiusSm; color: Theme.subtle; border.color: Theme.border
                        TextArea { id: sharedValue; anchors.fill: parent; anchors.margins: 10; color: Theme.text; placeholderText: "Value or one list item per line"; placeholderTextColor: Theme.dim; background: Item {} wrapMode: TextArea.Wrap; font.pixelSize: 13 }
                    }
                    Row {
                        spacing: 10
                        PrimaryButton { width: 130; text: "Save"; icon: "save"; enabled: profilesBridge.canManage && !profilesBridge.busy; onClicked: settingsBridge.saveVariable(sharedKey.text, sharedType.text, sharedValue.text) }
                        PrimaryButton { width: 110; text: "Delete"; danger: true; enabled: profilesBridge.canManage && !profilesBridge.busy; onClicked: settingsBridge.deleteVariable(sharedKey.text) }
                    }
                }
            }
        }
    }

    Menu {
        id: profileMenu
        MenuItem { text: "Open browser"; enabled: !!root.contextActions.startAllowed; onTriggered: profilesBridge.startProfile(root.contextProfile) }
        MenuItem { text: "Stop browser"; visible: !!root.contextActions.stopAllowed; onTriggered: profilesBridge.stopProfile(root.contextProfile) }
        MenuItem { text: "Run scenario..."; enabled: !!root.contextActions.startAllowed; onTriggered: operationsBridge.prepareRun(root.contextProfile) }
        MenuSeparator {}
        MenuItem { text: "Profile settings"; enabled: !!root.contextActions.editAllowed; onTriggered: root.openProfileModal(root.contextProfile) }
        MenuItem { text: "Profile health check"; enabled: !!root.contextActions.startAllowed; onTriggered: profilesBridge.runHealthCheck(root.contextProfile) }
        MenuItem {
            text: "Unlock profile"
            visible: root.contextActions.status === "Locked"
            enabled: !!root.contextActions.unlockAllowed
            onTriggered: {
                var name = root.contextProfile
                confirmDialog.ask('Unlock "' + name + '"? Confirm its browser has stopped on all devices.',
                                  function() { profilesBridge.forceUnlockProfile(name) }, "Unlock")
            }
        }
        MenuSeparator {}
        MenuItem { text: "Delete profile"; enabled: !!root.contextActions.deleteAllowed; onTriggered: root.confirmDelete(root.contextProfile) }
    }
}
