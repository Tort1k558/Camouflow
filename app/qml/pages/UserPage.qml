import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import theme 1.0
import "../components"

Flickable {
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    id: root
    property var bridge: typeof userBridge !== "undefined" ? userBridge : null
    readonly property bool cloud: bridge && bridge.serverEnabled
    readonly property string accountName: cloud ? (bridge.fullName !== "" ? bridge.fullName : bridge.email) : ""
    readonly property var avatarTones: ["#d1f366", "#b9e58a", "#a3d79e", "#cfe08a", "#9ccf96", "#bfe0b0"]
    readonly property int avatarTone: {
        var seed = accountName !== "" ? accountName : "local"
        var h = 0
        for (var i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) % 997
        return h % 6
    }
    readonly property string accountInitials: {
        var n = accountName !== "" ? accountName : "You"
        var parts = n.trim().split(/\s+/)
        if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase()
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    }
    function teamTone(name) {
        var h = 0
        for (var i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 997
        return h % 6
    }
    function teamInitials(name) {
        var parts = name.trim().split(/\s+/)
        if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase()
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    }
    contentWidth: width
    contentHeight: content.height + 64
    clip: true

    Column {
        id: content
        width: parent.width - 56
        x: 28
        y: 24
        spacing: 24

        PageHeader {
            width: parent.width
            title: "Account & teams"
            subtitle: "Account, teams, roles and invitations"
            badge: root.bridge && root.bridge.serverEnabled ? "Cloud" : "Local mode"
        }

        // ── profile header: no card, avatar + identity + actions ──
        RowLayout {
            width: parent.width
            spacing: 15

            Item {
                Layout.preferredWidth: 54
                Layout.preferredHeight: 54
                Rectangle {
                    anchors.fill: parent
                    radius: 27
                    color: root.avatarTones[root.avatarTone]
                    Text { anchors.centerIn: parent; text: root.accountInitials; color: Theme.primaryText; font.pixelSize: 17; font.weight: Font.DemiBold }
                }
                Rectangle {
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    width: 14; height: 14; radius: 7
                    color: root.cloud ? Theme.success : "#9aa793"
                    border.width: 3
                    border.color: Theme.background
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    Layout.fillWidth: true
                    text: root.cloud ? (root.accountName || "Account") : "Local workspace"
                    color: Theme.text; font.pixelSize: 21; font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    text: root.cloud ? root.bridge.email : "Profiles stored on this computer"
                    color: Theme.muted; font.pixelSize: 13
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    visible: root.cloud
                    text: root.bridge ? root.bridge.status : ""
                    color: Theme.primaryLight; font.pixelSize: 11
                    elide: Text.ElideMiddle
                }
            }

            PrimaryButton {
                visible: !root.cloud
                text: "Login"
                icon: "link"
                onClicked: {
                    loginEmail.text = root.bridge ? root.bridge.serverEmail : ""
                    loginPassword.text = ""
                    loginDialog.open()
                }
            }
        }

        // ── sync toolbar (cloud) ──────────────────────────────────
        RowLayout {
            width: parent.width
            visible: root.cloud
            spacing: 8
            PrimaryButton {
                text: "Sync cloud"
                icon: "save"
                secondary: true
                enabled: root.bridge ? root.bridge.canManageCloud : false
                onClicked: syncConfirm.ask("Synchronize all local profiles, proxies and scenarios with team " + root.bridge.selectedTeamId + " at " + root.bridge.serverUrl + "? This links local data to this team.", function() { root.bridge.syncCloudWorkspace() })
            }
            PrimaryButton {
                text: "Sync + cookies"
                icon: "cookie"
                secondary: true
                enabled: root.bridge ? root.bridge.canManageCloud : false
                onClicked: syncConfirm.ask("Upload local data AND browser cookies to team " + root.bridge.selectedTeamId + " at " + root.bridge.serverUrl + "? Cookies can grant access to signed-in accounts.", function() { root.bridge.syncCloudWorkspace(true) })
            }
            PrimaryButton {
                text: root.bridge && root.bridge.conflictCount > 0 ? "Conflicts (" + root.bridge.conflictCount + ")" : "Conflicts"
                icon: "link"
                secondary: true
                visible: root.bridge && root.bridge.canManageCloud
                onClicked: conflictDialog.open()
            }
            Item { Layout.fillWidth: true }
            CheckBox {
                checked: root.bridge ? root.bridge.autoSyncEnabled : false
                onToggled: root.bridge.setAutoSyncEnabled(checked)
                text: "Auto-sync"
                font.pixelSize: 12
            }
            PrimaryButton {
                text: "Logout"
                icon: "stop"
                danger: true
                onClicked: root.bridge.logout()
            }
        }

        // ── local hint ────────────────────────────────────────────
        Text {
            width: parent.width
            visible: !root.cloud
            text: "Login to unlock teams, roles, invites, profile locks between teammates and the audit log. Local profiles and saved scenarios do not require signing in."
            color: Theme.muted
            font.pixelSize: 12
            wrapMode: Text.WordWrap
            lineHeight: 1.25
        }

        // ── pending invites: compact rows ─────────────────────────
        ColumnLayout {
            width: parent.width
            spacing: 8
            visible: root.cloud && root.bridge && root.bridge.invitesModel.count > 0

            RowLayout {
                Layout.fillWidth: true
                Text { text: "PENDING INVITES · " + (root.bridge ? root.bridge.invitesModel.count : 0); color: Theme.dim; font.family: Theme.monoFamily; font.pixelSize: 10; font.letterSpacing: 1.2 }
                Item { Layout.fillWidth: true }
            }

            Repeater {
                model: root.bridge ? root.bridge.invitesModel : null
                delegate: Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 44
                    radius: 9
                    color: "transparent"
                    border.color: Theme.borderSubtle
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 11
                        anchors.rightMargin: 7
                        spacing: 10
                        Column {
                            Layout.fillWidth: true
                            spacing: 1
                            Text { text: model.team_name; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight; width: parent.width }
                            Text { text: "invited as " + model.role + (model.invited_by_email ? " · by " + model.invited_by_email : ""); color: Theme.dim; font.pixelSize: 10; elide: Text.ElideRight; width: parent.width }
                        }
                        PrimaryButton { Layout.preferredHeight: 27; text: "Accept"; icon: "check"; onClicked: root.bridge.acceptInvite(model.id) }
                    }
                }
            }
        }

        // ── my teams: compact selectable rows ─────────────────────
        ColumnLayout {
            width: parent.width
            spacing: 8
            visible: root.cloud

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Text {
                    text: "MY TEAMS · " + (root.bridge ? root.bridge.teamsModel.count : 0)
                    color: Theme.dim
                    font.family: Theme.monoFamily
                    font.pixelSize: 10
                    font.letterSpacing: 1.2
                }
                Item { Layout.fillWidth: true }
                PrimaryButton {
                    text: ""
                    icon: "refresh"
                    iconOnly: true
                    width: 30
                    onClicked: root.bridge.refresh()
                }
            }

            Repeater {
                model: root.bridge ? root.bridge.teamsModel : null
                delegate: Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 56
                    radius: 10
                    color: model.selected ? Theme.selection : "transparent"
                    border.color: model.selected ? Theme.primary : Theme.borderSubtle
                    opacity: 1

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.bridge.selectTeam(model.id)
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 11

                        Rectangle {
                            Layout.preferredWidth: 34
                            Layout.preferredHeight: 34
                            radius: 17
                            color: root.avatarTones[root.teamTone(model.name)]
                            Text { anchors.centerIn: parent; text: root.teamInitials(model.name); color: Theme.primaryText; font.pixelSize: 12; font.weight: Font.DemiBold }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                Text { text: model.name; color: Theme.text; font.pixelSize: 13; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
                                Rectangle {
                                    visible: model.selected
                                    Layout.preferredWidth: 58
                                    Layout.preferredHeight: 18
                                    radius: 9
                                    color: Theme.primary
                                    Text { anchors.centerIn: parent; text: "ACTIVE"; color: Theme.primaryText; font.pixelSize: 9; font.weight: Font.DemiBold; font.letterSpacing: 0.6 }
                                }
                            }
                            Text {
                                text: model.slug + " · " + model.plan + " · " + model.profiles + "p " + model.proxies + "x " + model.scenarios + "s"
                                color: Theme.dim
                                font.family: Theme.monoFamily
                                font.pixelSize: 10
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }

                        Rectangle {
                            Layout.preferredWidth: 74
                            Layout.preferredHeight: 21
                            radius: 7
                            color: model.role === "owner" ? "#496b2c" : Theme.subtle
                            Text { anchors.centerIn: parent; text: model.role; color: model.role === "owner" ? "#edf4e6" : Theme.primaryLight; font.pixelSize: 10; font.weight: Font.DemiBold }
                        }
                    }
                }
            }

            Text {
                visible: root.bridge && root.bridge.teamsModel.count === 0
                text: "No teams yet — create one on camouflow.site/console or accept an invite."
                color: Theme.muted
                font.pixelSize: 12
            }
        }

        GlassCard {
            width: parent.width
            height: 470
            padding: 22
            visible: root.bridge && root.bridge.serverEnabled

            component InitialsAvatar: Rectangle {
                id: avatar
                property string name: ""
                readonly property var tones: ["#d1f366", "#b9e58a", "#a3d79e", "#cfe08a", "#9ccf96", "#bfe0b0"]
                readonly property int tone: {
                    var h = 0
                    for (var i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 997
                    return h % 6
                }
                readonly property string initialsText: {
                    var parts = name.trim().split(/\s+/)
                    if (parts.length === 0 || parts[0] === "") return "?"
                    if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase()
                    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
                }
                width: 26; height: 26; radius: 13
                color: tones[tone]
                Text {
                    anchors.centerIn: parent
                    text: avatar.initialsText
                    color: "#26331f"
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                }
            }

            component ConsoleTab: Rectangle {
                id: ctab
                property string label: ""
                property bool active: false
                signal selected()
                height: 30; radius: 8
                width: tabLabel.implicitWidth + 26
                color: active ? Theme.selection : "transparent"
                border.color: active ? Theme.primary : Theme.borderSubtle
                Text { id: tabLabel; anchors.centerIn: parent; text: ctab.label; color: ctab.active ? Theme.primaryLight : Theme.muted; font.pixelSize: 12; font.weight: Font.DemiBold }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: ctab.selected() }
            }

            RowLayout {
                id: accessHeader
                anchors.left: parent.left
                anchors.right: parent.right
                spacing: 10
                Rectangle { Layout.preferredWidth: 36; Layout.preferredHeight: 36; radius: 12; color: "transparent"; border.color: Theme.primaryInk; LineIcon { anchors.centerIn: parent; name: "users"; color: Theme.primaryInk; size: 18 } }
                Column {
                    Layout.fillWidth: true
                    Text { text: "Team console"; color: Theme.text; font.pixelSize: 17; font.weight: Font.DemiBold }
                    Text { text: root.bridge && root.bridge.canManageTeam ? "Members, invites and activity for the active team." : "Members and activity — managing requires admin role."; color: Theme.muted; font.pixelSize: 12 }
                }
                PrimaryButton {
                    Layout.preferredHeight: 30
                    text: "Leave team"
                    secondary: true
                    visible: root.bridge && root.bridge.canViewCloud
                    onClicked: leaveConfirm.ask("Leave this team? You can come back via a new invite.", function() { root.bridge.leaveTeam() }, "Leave")
                }
            }

            Row {
                id: consoleTabs
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: accessHeader.bottom
                anchors.topMargin: 14
                spacing: 8
                property string current: "members"
                ConsoleTab { label: "Members"; active: consoleTabs.current === "members"; onSelected: consoleTabs.current = "members" }
                ConsoleTab { label: "Invites"; active: consoleTabs.current === "invites"; onSelected: consoleTabs.current = "invites" }
                ConsoleTab { label: "Audit"; active: consoleTabs.current === "audit"; onSelected: consoleTabs.current = "audit" }
            }

            // ── Members tab ────────────────────────────────────────
            ListView {
                visible: consoleTabs.current === "members"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: consoleTabs.bottom
                anchors.topMargin: 10
                anchors.bottom: parent.bottom
                clip: true
                spacing: 4
                model: root.bridge ? root.bridge.membersModel : null

                delegate: Rectangle {
                    width: ListView.view.width
                    height: 38
                    radius: 9
                    color: "transparent"
                    border.color: Theme.borderSubtle
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 9
                        anchors.rightMargin: 6
                        spacing: 9
                        InitialsAvatar { name: model.full_name !== "" ? model.full_name : model.email }
                        Column {
                            Layout.fillWidth: true
                            spacing: 1
                            Text { text: model.full_name !== "" ? model.full_name : model.email; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight; width: parent.width }
                            Text { text: model.last_seen !== "" ? model.email + " · seen " + model.last_seen : model.email; color: Theme.dim; font.pixelSize: 10; elide: Text.ElideRight; width: parent.width }
                        }
                        ComboBox {
                            id: roleEdit
                            Layout.preferredWidth: 104
                            Layout.preferredHeight: 26
                            font.pixelSize: 11
                            model: ["viewer", "operator", "manager", "admin", "owner"]
                            currentIndex: Math.max(0, ["viewer", "operator", "manager", "admin", "owner"].indexOf(model.role))
                            enabled: root.bridge ? root.bridge.canManageTeam : false
                        }
                        PrimaryButton { Layout.preferredWidth: 54; Layout.preferredHeight: 26; text: "Save"; secondary: true; visible: root.bridge && root.bridge.canManageTeam; onClicked: root.bridge.updateMemberRole(model.id, roleEdit.currentText) }
                        PrimaryButton { Layout.preferredWidth: 62; Layout.preferredHeight: 26; text: "Remove"; danger: true; visible: root.bridge && root.bridge.canManageTeam && model.role !== "owner"; onClicked: memberConfirm.ask('Remove "' + model.email + '" from the team?', function() { root.bridge.deleteMember(model.id) }) }
                    }
                }
                EmptyState { anchors.centerIn: parent; width: Math.min(320, parent.width); visible: root.bridge && root.bridge.membersModel.count === 0; title: "No members"; description: "Invite people from the Invites tab."; icon: "users" }
            }

            // ── Invites tab ────────────────────────────────────────
            ColumnLayout {
                visible: consoleTabs.current === "invites"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: consoleTabs.bottom
                anchors.topMargin: 10
                anchors.bottom: parent.bottom
                spacing: 10

                RowLayout {
                    visible: root.bridge && root.bridge.canManageTeam
                    Layout.fillWidth: true
                    spacing: 8
                    FormField { id: inviteEmail; Layout.fillWidth: true; label: "Email"; placeholder: "user@company.com" }
                    Column {
                        Layout.preferredWidth: 120
                        spacing: 3
                        Text { text: "Role"; color: Theme.dim; font.pixelSize: 10; font.weight: Font.DemiBold }
                        ComboBox {
                            id: inviteRole
                            width: parent.width
                            model: ["viewer", "operator", "manager", "admin"]
                            currentIndex: 1
                        }
                    }
                    PrimaryButton { Layout.preferredWidth: 90; Layout.alignment: Qt.AlignBottom; text: "Invite"; icon: "plus"; onClicked: root.bridge.createInvite(inviteEmail.text, inviteRole.currentText) }
                }

                Rectangle {
                    visible: root.bridge && root.bridge.lastInviteLink !== ""
                    Layout.fillWidth: true
                    Layout.preferredHeight: 50
                    radius: 9
                    color: Theme.selection
                    border.color: Theme.primary
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 8
                        Text { Layout.fillWidth: true; text: root.bridge ? root.bridge.lastInviteLink : ""; color: Theme.text; font.pixelSize: 11; elide: Text.ElideMiddle }
                        PrimaryButton { Layout.preferredWidth: 66; Layout.preferredHeight: 26; text: "Copy"; secondary: true; onClicked: root.bridge.copyToClipboard(root.bridge.lastInviteLink) }
                        PrimaryButton { Layout.preferredWidth: 66; Layout.preferredHeight: 26; text: "Open"; secondary: true; onClicked: Qt.openUrlExternally(root.bridge.lastInviteLink) }
                    }
                }

                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 4
                    model: root.bridge ? root.bridge.sentInvitesModel : null
                    delegate: Rectangle {
                        width: ListView.view.width
                        height: 34
                        radius: 8
                        color: "transparent"
                        border.color: Theme.borderSubtle
                        opacity: model.status === "active" ? 1 : 0.55
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 9
                            anchors.rightMargin: 6
                            spacing: 8
                            Text { Layout.fillWidth: true; text: model.email; color: Theme.text; font.pixelSize: 12; elide: Text.ElideRight }
                            Text { Layout.preferredWidth: 70; text: model.role; color: Theme.dim; font.pixelSize: 11 }
                            Rectangle {
                                Layout.preferredWidth: 62; Layout.preferredHeight: 19; radius: 9
                                color: model.status === "active" ? Theme.selection : model.status === "used" ? Theme.subtle : Theme.dangerSurface
                                Text { anchors.centerIn: parent; text: model.status; color: model.status === "expired" ? Theme.danger : model.status === "active" ? Theme.primaryInk : Theme.dim; font.pixelSize: 9; font.weight: Font.DemiBold }
                            }
                            PrimaryButton { Layout.preferredWidth: 62; Layout.preferredHeight: 24; text: "Revoke"; danger: true; visible: root.bridge && root.bridge.canManageTeam && model.status === "active"; onClicked: inviteConfirm.ask('Revoke invite for "' + model.email + '"?', function() { root.bridge.revokeInvite(model.id) }) }
                        }
                    }
                    EmptyState { anchors.centerIn: parent; width: Math.min(320, parent.width); visible: root.bridge && root.bridge.sentInvitesModel.count === 0; title: "No invites yet"; description: "Create one above — the link is copied automatically."; icon: "mail" }
                }
            }

            // ── Audit tab ──────────────────────────────────────────
            ListView {
                visible: consoleTabs.current === "audit"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: consoleTabs.bottom
                anchors.topMargin: 10
                anchors.bottom: parent.bottom
                clip: true
                spacing: 3
                model: root.bridge ? root.bridge.auditModel : null
                delegate: Rectangle {
                    width: ListView.view.width
                    height: 30
                    radius: 7
                    color: "transparent"
                    border.color: Theme.borderSubtle
                    opacity: 0.9
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 9
                        anchors.rightMargin: 9
                        spacing: 8
                        Text { Layout.preferredWidth: 118; text: model.time; color: Theme.dim; font.pixelSize: 10; font.family: Theme.monoFamily }
                        Text { Layout.preferredWidth: 132; text: model.action; color: Theme.primaryInk; font.pixelSize: 10; font.weight: Font.DemiBold; font.family: Theme.monoFamily; elide: Text.ElideRight }
                        Text { Layout.preferredWidth: 110; text: model.entity; color: Theme.muted; font.pixelSize: 10; elide: Text.ElideRight }
                        Text { Layout.fillWidth: true; text: model.details; color: Theme.dim; font.pixelSize: 10; elide: Text.ElideRight }
                    }
                }
                EmptyState { anchors.centerIn: parent; width: Math.min(320, parent.width); visible: root.bridge && root.bridge.auditModel.count === 0; title: "No activity yet"; description: "Team actions will appear here."; icon: "logs" }
            }
        }

        ConfirmDialog { id: memberConfirm }
        ConfirmDialog { id: leaveConfirm }
        ConfirmDialog { id: inviteConfirm }
    }

    ConfirmDialog { id: syncConfirm }

    WorkspaceDialog {
        id: loginDialog
        objectName: "loginDialog"
        modal: true
        width: Math.min(460, root.width - 80)
        height: Math.min(implicitHeight, root.height - 24)
        anchors.centerIn: Overlay.overlay
        background: Rectangle { color: Theme.elevated; radius: Theme.radiusLg; border.color: Theme.border }
        padding: 24
        contentItem: Flickable {
            implicitHeight: loginContent.implicitHeight
            contentHeight: loginContent.implicitHeight
            clip: true
            ScrollBar.vertical: ScrollBar {}
            Column {
                id: loginContent
                width: parent.width
                spacing: 14

                Text { text: "Login"; color: Theme.text; font.pixelSize: 24; font.weight: Font.DemiBold }
                Text { text: "Connect your account to enable teams, roles, invites and cloud sync."; color: Theme.muted; font.pixelSize: 13; wrapMode: Text.WordWrap; width: parent.width }
                FormField { id: loginEmail; width: parent.width; label: "Email"; placeholder: "you@company.com" }
                FormField { id: loginPassword; width: parent.width; label: "Password"; placeholder: "Password"; echoMode: TextInput.Password }
                Row {
                    width: parent.width
                    spacing: 10
                    PrimaryButton { width: (parent.width - 10) / 2; text: "Cancel"; secondary: true; onClicked: loginDialog.close() }
                    PrimaryButton {
                        width: (parent.width - 10) / 2
                        text: "Login"
                        enabled: root.bridge && !root.bridge.authBusy
                        icon: "link"
                        onClicked: {
                            if (root.bridge) root.bridge.login(loginEmail.text, loginPassword.text)
                        }
                    }
                }
                Rectangle { width: parent.width; height: 1; color: Theme.borderSubtle }
                Text { text: "OR SIGN IN WITH GOOGLE"; color: Theme.dim; font.pixelSize: 10; font.weight: Font.DemiBold; font.letterSpacing: 1 }
                PrimaryButton {
                    width: parent.width
                    text: "Continue with Google"
                    enabled: root.bridge && !root.bridge.authBusy
                    icon: "user"
                    onClicked: { if (root.bridge) root.bridge.googleLogin() }
                }
                FormField { id: loginPairCode; width: parent.width; label: "Pairing code from browser"; placeholder: "cf_…" }
                PrimaryButton {
                    width: parent.width
                    text: "Link app"
                    enabled: root.bridge && !root.bridge.authBusy && loginPairCode.text.trim() !== ""
                    secondary: true
                    onClicked: {
                        if (root.bridge) root.bridge.loginWithPairCode(loginPairCode.text)
                    }
                }
                Text {
                    width: parent.width
                    visible: text !== ""
                    text: root.bridge ? root.bridge.authMessage : ""
                    color: Theme.muted
                    font.pixelSize: 12
                    wrapMode: Text.Wrap
                }
            }
        }
        Connections {
            target: root.bridge
            function onLoginSucceeded() {
                loginPassword.text = ""
                loginPairCode.text = ""
                loginDialog.close()
            }
        }
    }

    WorkspaceDialog {
        id: conflictDialog
        objectName: "conflictDialog"
        anchors.centerIn: Overlay.overlay
        modal: true
        width: Math.min(680, root.width - 60)
        height: Math.min(460, root.height - 60)
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: Theme.radiusLg; border.color: Theme.border }
        contentItem: Column {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14
            Text { text: "Conflict center"; color: Theme.text; font.pixelSize: 20; font.weight: Font.DemiBold }
            Text { text: "Items changed both locally and on the server. Pick which version wins."; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap; width: parent.width }
            ListView {
                id: conflictList
                width: parent.width
                height: parent.height - 120
                clip: true
                spacing: 8
                model: root.bridge && root.bridge.conflictCount > 0 ? root.bridge.conflictModel : null
                delegate: Rectangle {
                    width: conflictList.width
                    height: 52
                    radius: 10
                    color: Theme.subtle
                    border.color: Theme.border
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8
                        Column {
                            Layout.fillWidth: true
                            Text { text: model.resource + (model.reason === "remote_deleted" ? " / deleted on server" : model.reason === "local_deleted" ? " / deleted locally" : ""); color: Theme.primaryLight; font.pixelSize: 10; font.weight: Font.DemiBold; font.capitalization: Font.AllUppercase }
                            Text { width: parent.width; text: model.key; color: Theme.text; font.pixelSize: 12; elide: Text.ElideMiddle }
                        }
                        PrimaryButton { Layout.preferredWidth: 96; text: model.reason === "local_deleted" ? "Delete remote" : "Keep local"; secondary: true; onClicked: syncConfirm.ask("Apply the local version for " + model.key + "? If deleted locally, this deletes the server record.", function() { root.bridge.resolveConflict(model.resource + "|" + model.key + "|local") }) }
                        PrimaryButton { Layout.preferredWidth: 104; text: model.reason === "remote_deleted" ? "Delete local" : "Keep remote"; secondary: true; onClicked: syncConfirm.ask("Apply the server version for " + model.key + "? If deleted on the server, this deletes the local record.", function() { root.bridge.resolveConflict(model.resource + "|" + model.key + "|remote") }) }
                    }
                }
                EmptyState { anchors.centerIn: parent; width: Math.min(320, parent.width); visible: root.bridge && root.bridge.conflictCount === 0; title: "No conflicts"; description: "Local and cloud versions agree."; icon: "check" }
            }
            PrimaryButton { width: parent.width; text: "Close"; secondary: true; onClicked: conflictDialog.close() }
        }
    }

}
