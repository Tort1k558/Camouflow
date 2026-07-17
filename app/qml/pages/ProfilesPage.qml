import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

Flickable {
    id: root
    contentWidth: width
    contentHeight: content.height + 48
    clip: true
    property string editingProfile: ""
    property string contextProfile: ""

    function openProfileModal(profileName) {
        var data = profilesBridge.getProfile(profileName, browserSettingsBridge.engine)
        editingProfile = profileName
        editName.text = data.name || profileName
        editStage.text = data.stage || ""
        editProxyHost.text = data.proxy_host || ""
        editProxyPort.text = data.proxy_port || ""
        editProxyUser.text = data.proxy_user || ""
        editProxyPassword.text = data.proxy_password || ""
        editLocale.text = data.locale || ""
        editTimezone.text = data.timezone || ""
        editUserAgent.text = data.user_agent || ""
        editWebgl.text = data.webgl_vendor || ""
        editCpu.text = data.hardware_concurrency || ""
        profileDialog.open()
    }
    function openVariablesModal(profileName) {
        editingProfile = profileName || editingProfile
        profileVarsJson.text = profilesBridge.getProfileVariables(editingProfile)
        profileVarsDialog.open()
    }
    function openCookiesModal(profileName) {
        editingProfile = profileName || editingProfile
        profileCookiesJson.text = profilesBridge.getProfileCookiesJson(editingProfile)
        profileCookiesDialog.open()
    }
    function openBrowserOverridesModal(profileName) {
        editingProfile = profileName || editingProfile
        profileBrowserSettingsJson.text = profilesBridge.getProfileBrowserSettingsJson(editingProfile, browserSettingsBridge.engine)
        profileBrowserSettingsDialog.open()
    }
    function openTagsModal() {
        settingsBridge.refresh()
        tagName.text = ""
        tagsDialog.open()
    }

    Column {
        id: content
        width: parent.width - 56
        x: 28
        y: 24
        spacing: 22
        RowLayout {
            width: parent.width
            PageHeader {
                Layout.fillWidth: true
                title: "Profiles"
                subtitle: appState && appState.cloudEnabled
                    ? "Team: " + (appState.cloudTeamName || "No team") + " / Role: " + (appState.cloudRole || "none")
                    : "Manage your local browser profiles and sessions"
            }
            PrimaryButton { Layout.preferredWidth: 116; height: 42; text: "Import"; icon: "save"; secondary: true; enabled: profilesBridge.canManage; onClicked: importDialog.open() }
            PrimaryButton { Layout.preferredWidth: 116; height: 42; text: "Tags"; icon: "settings"; secondary: true; enabled: profilesBridge.canManage; onClicked: root.openTagsModal() }
            PrimaryButton { Layout.preferredWidth: 116; height: 42; text: "New Profile"; icon: "plus"; enabled: profilesBridge.canManage; onClicked: profilesBridge.createProfile() }
        }
        SearchBox { id: search; width: parent.width; placeholder: "Search profiles or tags..." }
        ListView {
            width: parent.width
            height: 38
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
                    color: model.selected ? "white" : Theme.muted
                    font.pixelSize: 12
                    font.bold: true
                }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: profilesBridge.setStageFilter(model.name) }
            }
        }
        ListView {
            width: parent.width
            height: Math.max(520, count * 92)
            model: profilesBridge.model
            spacing: 14
            interactive: false
            delegate: ProfileRow {
                width: ListView.view.width
                name: model.name
                ident: model.id
                browser: model.browser
                proxy: model.proxy
                lastActive: model.lastActive
                status: model.status
                tags: model.tags
                running: model.running
                lockedBy: model.lockedBy
                lockExpires: model.lockExpires
                canRun: profilesBridge.canRun
                canManage: profilesBridge.canManage
                canAdmin: profilesBridge.canAdmin
                visible: search.text.length === 0 || (model.name + model.tags + model.proxy).toLowerCase().indexOf(search.text.toLowerCase()) >= 0
                height: visible ? 78 : 0
                onStartClicked: profilesBridge.startProfile(model.name)
                onStopClicked: profilesBridge.stopProfile(model.name)
                onSettingsClicked: root.openProfileModal(model.name)
                onDeleteClicked: profilesBridge.deleteProfile(model.name)
                onContextRequested: function(x, y) {
                    root.contextProfile = model.name
                    profileMenu.popup(x + 28, y + 150)
                }
            }
        }
        GlassCard {
            width: parent.width
            height: 118
            padding: 18
            RowLayout {
                anchors.fill: parent
                spacing: 12
                Column {
                    Layout.preferredWidth: 210
                    spacing: 6
                    Text { text: "Run scenario for tag"; color: Theme.text; font.pixelSize: 16; font.bold: true }
                    Text { text: "Batch run selected scenario by profile tag"; color: Theme.muted; font.pixelSize: 12 }
                }
                Rectangle {
                    Layout.preferredWidth: 180
                    height: 42
                    radius: 11
                    color: Theme.subtle
                    border.color: Theme.border
                    ComboBox {
                        id: runTagSelect
                        anchors.fill: parent
                        anchors.margins: 6
                        model: profilesBridge.stagesModel
                        textRole: "name"
                        background: Item {}
                        contentItem: Text { text: runTagSelect.displayText || "Tag"; color: Theme.text; verticalAlignment: Text.AlignVCenter; font.pixelSize: 13; elide: Text.ElideRight }
                    }
                }
                Rectangle {
                    Layout.preferredWidth: 240
                    height: 42
                    radius: 11
                    color: Theme.subtle
                    border.color: Theme.border
                    ComboBox {
                        id: runScenarioSelect
                        anchors.fill: parent
                        anchors.margins: 6
                        model: scenariosBridge.model
                        textRole: "name"
                        background: Item {}
                        contentItem: Text { text: runScenarioSelect.displayText || "Scenario"; color: Theme.text; verticalAlignment: Text.AlignVCenter; font.pixelSize: 13; elide: Text.ElideRight }
                    }
                }
                FormField { id: runMax; Layout.preferredWidth: 90; label: "Max"; text: "10" }
                PrimaryButton {
                    Layout.preferredWidth: 130
                    text: "Run for tag"
                    icon: "play"
                    enabled: scenariosBridge.canRun
                    onClicked: scenariosBridge.runForTag(runTagSelect.currentText, runScenarioSelect.currentText, parseInt(runMax.text || "1"))
                }
                PrimaryButton { Layout.preferredWidth: 120; text: "Variables"; icon: "settings"; secondary: true; onClicked: variablesDialog.open() }
            }
        }
    }

    Dialog {
        id: importDialog
        modal: true
        width: Math.min(900, root.width - 80)
        height: Math.min(680, root.height - 80)
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: 22; border.color: Theme.border }
        contentItem: Column {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14
            Text { text: "Import Profiles"; color: Theme.text; font.pixelSize: 24; font.bold: true }
            FormField { id: importTemplate; width: parent.width; label: "Account parse template"; text: "{email};{password};{secret_key};{extra};{twofa_url}" }
            Row {
                width: parent.width
                spacing: 12
                FormField { id: importTag; width: (parent.width - 12) / 2; label: "Default tag" }
                Rectangle {
                    width: (parent.width - 12) / 2
                    height: 62
                    color: "transparent"
                    Text { text: "Proxy pool"; color: Theme.text; font.pixelSize: 12; font.bold: true }
                    Rectangle {
                        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                        height: 40; radius: 11; color: Theme.subtle; border.color: Theme.border
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
            Text { text: "Profiles, one per line"; color: Theme.text; font.pixelSize: 12; font.bold: true }
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
                    enabled: profilesBridge.canManage
                    onClicked: {
                        profilesBridge.importProfiles(importLines.text, importTemplate.text, importTag.text, importProxyPool.currentText === "All pools" ? "" : importProxyPool.currentText)
                        importDialog.close()
                    }
                }
                PrimaryButton { width: 100; text: "Cancel"; secondary: true; onClicked: importDialog.close() }
            }
        }
    }

    Dialog {
        id: tagsDialog
        modal: true
        width: Math.min(480, root.width - 80)
        height: 520
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: 22; border.color: Theme.border }
        contentItem: Column {
            spacing: 14
            padding: 22
            RowLayout {
                width: parent.width - 44
                Text { text: "Profile Tags"; color: Theme.text; font.pixelSize: 22; font.bold: true; Layout.fillWidth: true }
                PrimaryButton { Layout.preferredWidth: 40; text: ""; icon: "plus"; enabled: profilesBridge.canManage; onClicked: tagCreateDialog.open() }
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
                    Text { anchors.left: parent.left; anchors.leftMargin: 12; anchors.verticalCenter: parent.verticalCenter; text: model.name; color: Theme.text; font.pixelSize: 13; font.bold: true }
                    PrimaryButton { anchors.right: parent.right; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter; width: 34; height: 28; text: ""; icon: "trash"; danger: true; enabled: profilesBridge.canManage; onClicked: { settingsBridge.deleteStage(model.name); profilesBridge.refresh() } }
                }
            }
        }
    }

    Dialog {
        id: tagCreateDialog
        modal: true
        width: Math.min(420, root.width - 100)
        height: 210
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: 20; border.color: Theme.border }
        contentItem: Column {
            spacing: 14
            padding: 22
            Text { text: "New Tag"; color: Theme.text; font.pixelSize: 20; font.bold: true }
            FormField { id: tagName; width: parent.width - 44; label: "Tag name" }
            Row {
                spacing: 10
                PrimaryButton { width: 110; text: "Create"; icon: "plus"; enabled: profilesBridge.canManage; onClicked: { settingsBridge.addStage(tagName.text); profilesBridge.refresh(); tagCreateDialog.close() } }
                PrimaryButton { width: 100; text: "Cancel"; secondary: true; onClicked: tagCreateDialog.close() }
            }
        }
    }

    Dialog {
        id: profileDialog
        modal: true
        width: Math.min(820, root.width - 80)
        height: Math.min(720, root.height - 80)
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: 22; border.color: Theme.border }
        contentItem: Flickable {
            contentWidth: width
            contentHeight: modalContent.height + 44
            clip: true
            Column {
                id: modalContent
                width: parent.width - 44
                x: 22
                y: 22
                spacing: 18
                Text { text: "Profile Settings"; color: Theme.text; font.pixelSize: 24; font.bold: true }
                Text { text: "Profile data + per-profile browser overrides for " + browserSettingsBridge.engine; color: Theme.muted; font.pixelSize: 13 }
                GridLayout {
                    width: parent.width
                    columns: 2
                    columnSpacing: 16
                    rowSpacing: 14
                    FormField { id: editName; Layout.fillWidth: true; label: "Name" }
                    FormField { id: editStage; Layout.fillWidth: true; label: "Tag / Scenario" }
                    FormField { id: editProxyHost; Layout.fillWidth: true; label: "Proxy host" }
                    FormField { id: editProxyPort; Layout.fillWidth: true; label: "Proxy port" }
                    FormField { id: editProxyUser; Layout.fillWidth: true; label: "Proxy user" }
                    FormField { id: editProxyPassword; Layout.fillWidth: true; label: "Proxy password" }
                }
                Rectangle { width: parent.width; height: 1; color: Theme.border }
                Text { text: "Browser Overrides"; color: Theme.text; font.pixelSize: 18; font.bold: true }
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
                Row {
                    spacing: 12
                    PrimaryButton {
                        width: 120
                        text: "Save"
                        icon: "save"
                        enabled: profilesBridge.canManage
                        onClicked: {
                            profilesBridge.saveProfile(root.editingProfile, editName.text, editStage.text, editProxyHost.text, editProxyPort.text, editProxyUser.text, editProxyPassword.text, browserSettingsBridge.engine, editLocale.text, editTimezone.text, editUserAgent.text, editWebgl.text, editCpu.text)
                            profileDialog.close()
                        }
                    }
                    PrimaryButton { width: 110; text: "Vars"; secondary: true; enabled: profilesBridge.canManage; onClicked: root.openVariablesModal(root.editingProfile) }
                    PrimaryButton { width: 120; text: "Cookies"; secondary: true; enabled: profilesBridge.canManage; onClicked: root.openCookiesModal(root.editingProfile) }
                    PrimaryButton { width: 150; text: "Browser JSON"; secondary: true; enabled: profilesBridge.canManage; onClicked: root.openBrowserOverridesModal(root.editingProfile) }
                    PrimaryButton { width: 110; text: "Cancel"; secondary: true; onClicked: profileDialog.close() }
                }
            }
        }
    }

    Dialog {
        id: profileBrowserSettingsDialog
        modal: true
        width: Math.min(860, root.width - 80)
        height: Math.min(660, root.height - 80)
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: 22; border.color: Theme.border }
        contentItem: Column {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14
            Text { text: "Browser Overrides: " + root.editingProfile; color: Theme.text; font.pixelSize: 22; font.bold: true }
            Text { text: "JSON overrides only for current engine: " + browserSettingsBridge.engine; color: Theme.muted; font.pixelSize: 12 }
            Rectangle {
                width: parent.width
                height: parent.height - 122
                radius: 14
                color: Theme.subtle
                border.color: Theme.border
                TextArea { id: profileBrowserSettingsJson; anchors.fill: parent; anchors.margins: 12; color: Theme.text; font.family: "Consolas"; font.pixelSize: 12; background: Item {} wrapMode: TextArea.Wrap }
            }
            Row {
                spacing: 10
                PrimaryButton { width: 120; text: "Save"; icon: "save"; enabled: profilesBridge.canManage; onClicked: { profilesBridge.saveProfileBrowserSettingsJson(root.editingProfile, browserSettingsBridge.engine, profileBrowserSettingsJson.text); profileBrowserSettingsDialog.close() } }
                PrimaryButton { width: 110; text: "Cancel"; secondary: true; onClicked: profileBrowserSettingsDialog.close() }
            }
        }
    }

    Dialog {
        id: profileVarsDialog
        modal: true
        width: Math.min(760, root.width - 80)
        height: Math.min(620, root.height - 80)
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: 22; border.color: Theme.border }
        contentItem: Column {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14
            Text { text: "Profile Variables: " + root.editingProfile; color: Theme.text; font.pixelSize: 22; font.bold: true }
            Rectangle {
                width: parent.width
                height: parent.height - 92
                radius: 14
                color: Theme.subtle
                border.color: Theme.border
                TextArea { id: profileVarsJson; anchors.fill: parent; anchors.margins: 12; color: Theme.text; font.family: "Consolas"; font.pixelSize: 12; background: Item {} }
            }
            Row {
                spacing: 10
                PrimaryButton { width: 120; text: "Save"; icon: "save"; enabled: profilesBridge.canManage; onClicked: { profilesBridge.saveProfileVariables(root.editingProfile, profileVarsJson.text); profileVarsDialog.close() } }
                PrimaryButton { width: 110; text: "Cancel"; secondary: true; onClicked: profileVarsDialog.close() }
            }
        }
    }

    Dialog {
        id: profileCookiesDialog
        modal: true
        width: Math.min(840, root.width - 80)
        height: Math.min(660, root.height - 80)
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: 22; border.color: Theme.border }
        contentItem: Column {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14
            Text { text: "Cookies JSON: " + root.editingProfile; color: Theme.text; font.pixelSize: 22; font.bold: true }
            Text { text: "Edit JSON array and save. Encrypted Chromium values may be read-only."; color: Theme.muted; font.pixelSize: 12 }
            Rectangle {
                width: parent.width
                height: parent.height - 122
                radius: 14
                color: Theme.subtle
                border.color: Theme.border
                TextArea { id: profileCookiesJson; anchors.fill: parent; anchors.margins: 12; color: Theme.text; font.family: "Consolas"; font.pixelSize: 12; background: Item {} }
            }
            Row {
                spacing: 10
                PrimaryButton { width: 120; text: "Refresh"; secondary: true; onClicked: profileCookiesJson.text = profilesBridge.getProfileCookiesJson(root.editingProfile) }
                PrimaryButton { width: 120; text: "Save"; icon: "save"; enabled: profilesBridge.canManage; onClicked: { profilesBridge.saveProfileCookiesJson(root.editingProfile, profileCookiesJson.text); profileCookiesDialog.close() } }
                PrimaryButton { width: 110; text: "Cancel"; secondary: true; onClicked: profileCookiesDialog.close() }
            }
        }
    }

    Dialog {
        id: variablesDialog
        modal: true
        width: Math.min(860, root.width - 80)
        height: Math.min(560, root.height - 80)
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: 22; border.color: Theme.border }
        contentItem: Column {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 16
            RowLayout {
                width: parent.width
                height: 38
                Text { text: "Shared Variables"; color: Theme.text; font.pixelSize: 22; font.bold: true; Layout.fillWidth: true }
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
                    Text { text: "Value"; color: Theme.text; font.pixelSize: 12; font.bold: true }
                    Rectangle { width: parent.width; height: 190; radius: 11; color: Theme.subtle; border.color: Theme.border
                        TextArea { id: sharedValue; anchors.fill: parent; anchors.margins: 10; color: Theme.text; placeholderText: "Value or one list item per line"; placeholderTextColor: Theme.dim; background: Item {} wrapMode: TextArea.Wrap; font.pixelSize: 13 }
                    }
                    Row {
                        spacing: 10
                        PrimaryButton { width: 130; text: "Save"; icon: "save"; enabled: profilesBridge.canManage; onClicked: settingsBridge.saveVariable(sharedKey.text, sharedType.text, sharedValue.text) }
                        PrimaryButton { width: 110; text: "Delete"; danger: true; enabled: profilesBridge.canManage; onClicked: settingsBridge.deleteVariable(sharedKey.text) }
                    }
                }
            }
        }
    }

    Menu {
        id: profileMenu
        MenuItem { text: "Profile settings"; enabled: profilesBridge.canManage; onTriggered: root.openProfileModal(root.contextProfile) }
        MenuItem { text: "Open browser"; enabled: profilesBridge.canRun; onTriggered: profilesBridge.startProfile(root.contextProfile) }
        MenuItem { text: "Force unlock"; enabled: appState && appState.cloudEnabled && profilesBridge.canManage; onTriggered: profilesBridge.forceUnlockProfile(root.contextProfile) }
        MenuItem { text: "Variables"; enabled: profilesBridge.canManage; onTriggered: root.openVariablesModal(root.contextProfile) }
        MenuItem { text: "Cookies"; enabled: profilesBridge.canManage; onTriggered: root.openCookiesModal(root.contextProfile) }
        MenuItem { text: "Browser overrides"; enabled: profilesBridge.canManage; onTriggered: root.openBrowserOverridesModal(root.contextProfile) }
        MenuItem { text: "Run selected scenario"; enabled: scenariosBridge.canRun; onTriggered: { scenariosBridge.setRunProfile(root.contextProfile); scenariosBridge.runSelected() } }
        MenuSeparator {}
        MenuItem { text: "Delete profile"; enabled: profilesBridge.canAdmin; onTriggered: profilesBridge.deleteProfile(root.contextProfile) }
    }
}
