import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import theme 1.0
import "../components"

Flickable {
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    id: root
    property var bridge: typeof userBridge !== "undefined" ? userBridge : null
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

        RowLayout {
            width: parent.width
            spacing: 22

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 210
                padding: 26

                Rectangle {
                    width: 58
                    height: 58
                    radius: 20
                    color: "transparent"
                    border.color: root.bridge && root.bridge.serverEnabled ? Theme.success : Theme.primaryInk
                    LineIcon { anchors.centerIn: parent; name: "user"; color: root.bridge && root.bridge.serverEnabled ? Theme.success : Theme.primaryInk; size: 28 }
                }
                Column {
                    anchors.left: parent.left
                    anchors.leftMargin: 76
                    anchors.right: parent.right
                    spacing: 8
                    Text {
                        text: root.bridge && root.bridge.serverEnabled ? (root.bridge.fullName || root.bridge.email) : "Local workspace"
                        color: Theme.text
                        font.pixelSize: 24
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                        width: parent.width
                    }
                    Text {
                        text: root.bridge && root.bridge.serverEnabled ? root.bridge.email : "No account connected"
                        color: Theme.muted
                        font.pixelSize: 14
                        elide: Text.ElideRight
                        width: parent.width
                    }
                    Text {
                        text: root.bridge ? root.bridge.status : ""
                        color: Theme.primaryLight
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                        width: parent.width
                    }
                }

                Column {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    spacing: 10
                    visible: root.bridge && root.bridge.serverEnabled

                    Row {
                        spacing: 12
                        PrimaryButton {
                            width: 150
                            text: "Sync Cloud"
                            icon: "save"
                            secondary: true
                            enabled: root.bridge ? root.bridge.canManageCloud : false
                            onClicked: root.bridge.syncCloudWorkspace()
                        }
                        PrimaryButton {
                            width: 190
                            text: "Sync + cookies"
                            icon: "cookie"
                            secondary: true
                            enabled: root.bridge ? root.bridge.canManageCloud : false
                            onClicked: root.bridge.syncCloudWorkspace(true)
                        }
                        PrimaryButton {
                            width: 34
                            text: ""
                            icon: "refresh"
                            iconOnly: true
                            secondary: true
                            onClicked: root.bridge.refresh()
                        }
                        PrimaryButton {
                            width: 150
                            text: root.bridge && root.bridge.conflictCount > 0 ? "Conflicts (" + root.bridge.conflictCount + ")" : "Conflicts"
                            icon: "link"
                            visible: root.bridge && root.bridge.canManageCloud
                            secondary: true
                            onClicked: conflictDialog.open()
                        }
                        PrimaryButton {
                            width: 120
                            text: "Logout"
                            icon: "stop"
                            secondary: true
                            onClicked: root.bridge.logout()
                        }
                    }

                    Row {
                        spacing: 8
                        CheckBox {
                            id: autosyncCheck
                            checked: root.bridge ? root.bridge.autoSyncEnabled : false
                            onToggled: root.bridge.setAutoSyncEnabled(checked)
                            text: "Auto-sync on app start"
                        }
                    }
                }

                Row {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    visible: !root.bridge || !root.bridge.serverEnabled
                    PrimaryButton {
                        width: 110
                        text: "Login"
                        icon: "link"
                        onClicked: {
                            loginEmail.text = root.bridge ? root.bridge.serverEmail : ""
                            loginPassword.text = ""
                            loginDialog.open()
                        }
                    }
                }
            }

            GlassCard {
                Layout.preferredWidth: 390
                Layout.preferredHeight: 210
                padding: 24
                Text { id: localTitle; width: parent.width; wrapMode: Text.WordWrap; text: root.bridge && root.bridge.serverEnabled ? "Cloud features" : "Connect when you need a team"; color: Theme.text; font.pixelSize: 18; font.weight: Font.DemiBold }
                Text {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: localTitle.bottom
                    anchors.topMargin: 14
                    text: root.bridge && root.bridge.serverEnabled ? "Teams, roles, profile locks, audit log and cloud backups are available." : (root.bridge ? root.bridge.localLimitations : "")
                    color: Theme.muted
                    font.pixelSize: 13
                    lineHeight: 1.22
                    wrapMode: Text.WordWrap
                }
            }
        }

        GlassCard {
            width: parent.width
            height: 220
            padding: 26

            Row {
                id: invitesHeader
                anchors.left: parent.left
                anchors.right: parent.right
                spacing: 14
                Rectangle { width: 42; height: 42; radius: 14; color: "transparent"; border.color: Theme.primaryInk; LineIcon { anchors.centerIn: parent; name: "mail"; color: Theme.primaryInk; size: 21 } }
                Column {
                    width: parent.width - 180
                    Text { text: "Pending invites"; color: Theme.text; font.pixelSize: 19; font.weight: Font.DemiBold }
                    Text { text: "Invites sent to your account. Accept them here to join a team."; color: Theme.muted; font.pixelSize: 13 }
                }
                PrimaryButton {
                    width: 34
                    text: ""
                    icon: "refresh"
                    iconOnly: true
                    secondary: true
                    onClicked: root.bridge.refresh()
                }
            }

            Text {
                anchors.centerIn: parent
                visible: !root.bridge || !root.bridge.serverEnabled
                text: "Login to see pending invites."
                color: Theme.muted
                font.pixelSize: 15
            }

            ListView {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: invitesHeader.bottom
                anchors.topMargin: 20
                anchors.bottom: parent.bottom
                visible: root.bridge && root.bridge.serverEnabled
                clip: true
                spacing: 10
                model: root.bridge ? root.bridge.invitesModel : null

                delegate: Rectangle {
                    width: ListView.view.width
                    height: 58
                    radius: 14
                    color: "transparent"
                    border.color: Theme.border
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 10
                        spacing: 12
                        Text { Layout.fillWidth: true; text: model.team_name + " / " + model.team_slug; color: Theme.text; font.pixelSize: 14; font.weight: Font.DemiBold; elide: Text.ElideRight }
                        Text { Layout.preferredWidth: 110; text: model.role; color: Theme.primaryLight; font.pixelSize: 12; elide: Text.ElideRight }
                        Text { Layout.preferredWidth: 190; text: "From: " + (model.invited_by_email || "owner/admin"); color: Theme.muted; font.pixelSize: 12; elide: Text.ElideRight }
                        PrimaryButton { Layout.preferredWidth: 92; text: "Accept"; icon: "check"; onClicked: root.bridge.acceptInvite(model.id) }
                    }
                }
            }
        }

        GlassCard {
            width: parent.width
            height: 500
            padding: 26

            Row {
                id: teamsHeader
                anchors.left: parent.left
                anchors.right: parent.right
                spacing: 14
                Rectangle { width: 42; height: 42; radius: 14; color: "transparent"; border.color: Theme.primaryInk; LineIcon { anchors.centerIn: parent; name: "network"; color: Theme.primaryInk; size: 21 } }
                Column {
                    width: parent.width - 220
                    Text { text: "My teams"; color: Theme.text; font.pixelSize: 19; font.weight: Font.DemiBold }
                    Text { text: "Teams you joined. Click a team to make it active in the app."; color: Theme.muted; font.pixelSize: 13 }
                }
                PrimaryButton {
                    width: 34
                    text: ""
                    icon: "refresh"
                    iconOnly: true
                    secondary: true
                    onClicked: root.bridge.refresh()
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: teamsHeader.bottom
                anchors.topMargin: 18
                height: 1
                color: Theme.border
            }

            Text {
                anchors.centerIn: parent
                visible: !root.bridge || !root.bridge.serverEnabled
                text: "Login to see your teams, roles and who invited you."
                color: Theme.muted
                font.pixelSize: 15
            }

            ListView {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: teamsHeader.bottom
                anchors.topMargin: 34
                anchors.bottom: parent.bottom
                visible: root.bridge && root.bridge.serverEnabled
                clip: true
                spacing: 12
                model: root.bridge ? root.bridge.teamsModel : null

                delegate: Rectangle {
                    width: ListView.view.width
                    height: 104
                    radius: 16
                    color: "transparent"
                    border.color: model.selected ? Theme.primary : Theme.borderSubtle
                    border.width: 1

                    MouseArea {
                        anchors.fill: parent
                        enabled: !model.selected
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.bridge.selectTeam(model.id)
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 16

                        Rectangle {
                            Layout.preferredWidth: 48
                            Layout.preferredHeight: 48
                            radius: 16
                            color: "transparent"
                            border.color: model.selected ? Theme.primary : Theme.borderSubtle
                            LineIcon { anchors.centerIn: parent; name: "network"; color: model.selected ? Theme.primaryText : Theme.primaryLight; size: 23 }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 5
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10
                                Text { text: model.name; color: Theme.text; font.pixelSize: 16; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
                                Text { text: model.selected ? "ACTIVE" : ""; visible: model.selected; color: Theme.successLight; font.pixelSize: 11; font.weight: Font.DemiBold }
                            }
                            Text { text: model.slug + " / " + model.plan + " / " + model.license_status; color: Theme.muted; font.pixelSize: 12 }
                            Text {
                                text: "Role: " + model.role + "    Invited by: " + (model.invited_by_email || "owner/admin")
                                color: Theme.primaryLight
                                font.pixelSize: 12
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Text {
                                text: model.profiles + " profiles  /  " + model.proxies + " proxies  /  " + model.scenarios + " scenarios"
                                color: Theme.dim
                                font.pixelSize: 11
                            }
                        }

                        PrimaryButton {
                            Layout.preferredWidth: 120
                            text: model.selected ? "Selected" : "Select"
                            secondary: model.selected
                            enabled: !model.selected
                            onClicked: root.bridge.selectTeam(model.id)
                        }
                    }
                }
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

    WorkspaceDialog {
        id: loginDialog
        objectName: "loginDialog"
        modal: true
        width: Math.min(460, root.width - 80)
        height: 470
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: Theme.radiusLg; border.color: Theme.border }
        contentItem: Column {
            anchors.fill: parent
            anchors.margins: 24
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
                    icon: "link"
                    onClicked: {
                        if (root.bridge) root.bridge.login(loginEmail.text, loginPassword.text)
                        loginDialog.close()
                    }
                }
            }
            Rectangle { width: parent.width; height: 1; color: Theme.borderSubtle }
            Text { text: "OR SIGN IN WITH GOOGLE"; color: Theme.dim; font.pixelSize: 10; font.weight: Font.DemiBold; font.letterSpacing: 1 }
            PrimaryButton {
                width: parent.width
                text: "Continue with Google"
                icon: "user"
                onClicked: { if (root.bridge) root.bridge.googleLogin() }
            }
            FormField { id: loginPairCode; width: parent.width; label: "Pairing code from browser"; placeholder: "cf_…" }
            PrimaryButton {
                width: parent.width
                text: "Link app"
                secondary: true
                onClicked: {
                    if (root.bridge) root.bridge.loginWithPairCode(loginPairCode.text)
                    loginDialog.close()
                }
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
                            Text { text: model.resource; color: Theme.primaryLight; font.pixelSize: 10; font.weight: Font.DemiBold; font.capitalization: Font.AllUppercase }
                            Text { width: parent.width; text: model.key; color: Theme.text; font.pixelSize: 12; elide: Text.ElideMiddle }
                        }
                        PrimaryButton { Layout.preferredWidth: 96; text: "Keep local"; secondary: true; onClicked: root.bridge.resolveConflict(model.resource + "|" + model.key + "|local") }
                        PrimaryButton { Layout.preferredWidth: 104; text: "Keep remote"; secondary: true; onClicked: root.bridge.resolveConflict(model.resource + "|" + model.key + "|remote") }
                    }
                }
                EmptyState { anchors.centerIn: parent; width: Math.min(320, parent.width); visible: root.bridge && root.bridge.conflictCount === 0; title: "No conflicts"; description: "Local and cloud versions agree."; icon: "check" }
            }
            PrimaryButton { width: parent.width; text: "Close"; secondary: true; onClicked: conflictDialog.close() }
        }
    }

}
