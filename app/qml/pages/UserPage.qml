import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import theme 1.0
import "../components"

Flickable {
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
            title: "User"
            subtitle: "Account, teams, roles and invitations"
            badge: root.bridge && root.bridge.serverEnabled ? "Cloud" : "Local mode"
        }

        RowLayout {
            width: parent.width
            spacing: 22

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 150
                padding: 26

                Rectangle {
                    width: 58
                    height: 58
                    radius: 20
                    color: "transparent"
                    border.color: root.bridge && root.bridge.serverEnabled ? Theme.success : Theme.primary
                    LineIcon { anchors.centerIn: parent; name: "user"; color: root.bridge && root.bridge.serverEnabled ? Theme.success : Theme.primary; size: 28 }
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
                        font.bold: true
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

                Row {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    spacing: 12
                    visible: root.bridge && root.bridge.serverEnabled
                    PrimaryButton {
                        width: 170
                        text: "Sync Cloud"
                        icon: "save"
                        secondary: true
                        enabled: root.bridge ? root.bridge.canManageCloud : false
                        onClicked: root.bridge.syncCloudWorkspace()
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
                        width: 130
                        text: "Logout"
                        icon: "stop"
                        secondary: true
                        visible: root.bridge && root.bridge.serverEnabled
                        onClicked: root.bridge.logout()
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
                Layout.preferredHeight: 230
                padding: 24
                Text { id: localTitle; text: root.bridge && root.bridge.serverEnabled ? "Cloud features" : "Local mode loses"; color: Theme.text; font.pixelSize: 18; font.bold: true }
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
                Rectangle { width: 42; height: 42; radius: 14; color: "transparent"; border.color: Theme.primary; LineIcon { anchors.centerIn: parent; name: "mail"; color: Theme.primary; size: 21 } }
                Column {
                    width: parent.width - 180
                    Text { text: "Pending invites"; color: Theme.text; font.pixelSize: 19; font.bold: true }
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
                        Text { Layout.fillWidth: true; text: model.team_name + " / " + model.team_slug; color: Theme.text; font.pixelSize: 14; font.bold: true; elide: Text.ElideRight }
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
                Rectangle { width: 42; height: 42; radius: 14; color: "transparent"; border.color: Theme.primary; LineIcon { anchors.centerIn: parent; name: "network"; color: Theme.primary; size: 21 } }
                Column {
                    width: parent.width - 220
                    Text { text: "My teams"; color: Theme.text; font.pixelSize: 19; font.bold: true }
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
                            LineIcon { anchors.centerIn: parent; name: "network"; color: model.selected ? "white" : Theme.primaryLight; size: 23 }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 5
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10
                                Text { text: model.name; color: Theme.text; font.pixelSize: 16; font.bold: true; elide: Text.ElideRight; Layout.fillWidth: true }
                                Text { text: model.selected ? "ACTIVE" : ""; visible: model.selected; color: Theme.successLight; font.pixelSize: 11; font.bold: true }
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
            height: 360
            padding: 26
            visible: root.bridge && root.bridge.serverEnabled

            RowLayout {
                id: accessHeader
                anchors.left: parent.left
                anchors.right: parent.right
                spacing: 12
                Rectangle { Layout.preferredWidth: 42; Layout.preferredHeight: 42; radius: 14; color: "transparent"; border.color: Theme.primary; LineIcon { anchors.centerIn: parent; name: "users"; color: Theme.primary; size: 21 } }
                Column {
                    Layout.fillWidth: true
                    Text { text: "Team access"; color: Theme.text; font.pixelSize: 19; font.bold: true }
                    Text { text: root.bridge && root.bridge.canManageTeam ? "Invite users and manage roles for the active team." : "Only team admin/owner can manage members."; color: Theme.muted; font.pixelSize: 13 }
                }
            }

            RowLayout {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: accessHeader.bottom
                anchors.topMargin: 18
                spacing: 10

                FormField { id: inviteEmail; Layout.fillWidth: true; label: "Email"; placeholder: "user@company.com" }
                FormField { id: inviteRole; Layout.preferredWidth: 130; label: "Role"; text: "operator" }
                PrimaryButton {
                    Layout.preferredWidth: 120
                    Layout.alignment: Qt.AlignBottom
                    text: "Invite"
                    icon: "plus"
                    enabled: root.bridge ? root.bridge.canManageTeam : false
                    onClicked: root.bridge.createInvite(inviteEmail.text, inviteRole.text)
                }
            }

            ListView {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: accessHeader.bottom
                anchors.topMargin: 92
                anchors.bottom: parent.bottom
                clip: true
                spacing: 8
                model: root.bridge ? root.bridge.membersModel : null

                delegate: Rectangle {
                    width: ListView.view.width
                    height: 46
                    radius: 11
                    color: "transparent"
                    border.color: Theme.border
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 8
                        spacing: 8
                        Text { Layout.fillWidth: true; text: model.email + (model.full_name ? " / " + model.full_name : ""); color: Theme.text; font.pixelSize: 13; elide: Text.ElideRight }
                        TextField {
                            id: roleEdit
                            Layout.preferredWidth: 110
                            text: model.role
                            color: Theme.text
                            enabled: root.bridge ? root.bridge.canManageTeam : false
                            background: Rectangle { radius: 0; color: "transparent"; border.color: Theme.border }
                        }
                        PrimaryButton { Layout.preferredWidth: 76; text: "Save"; secondary: true; enabled: root.bridge ? root.bridge.canManageTeam : false; onClicked: root.bridge.updateMemberRole(model.id, roleEdit.text) }
                        PrimaryButton { Layout.preferredWidth: 76; text: "Reset"; secondary: true; enabled: root.bridge ? root.bridge.canManageTeam : false; onClicked: root.bridge.createPasswordReset(model.id) }
                        PrimaryButton { Layout.preferredWidth: 76; text: "Delete"; danger: true; enabled: root.bridge ? root.bridge.canManageTeam : false; onClicked: root.bridge.deleteMember(model.id) }
                    }
                }
            }
        }

        GlassCard {
            width: parent.width
            height: 320
            padding: 26
            visible: root.bridge && root.bridge.serverEnabled

            Text { id: auditTitle; text: "Audit log"; color: Theme.text; font.pixelSize: 19; font.bold: true }
            Text { anchors.left: parent.left; anchors.right: parent.right; anchors.top: auditTitle.bottom; anchors.topMargin: 6; text: "Recent activity for the active team."; color: Theme.muted; font.pixelSize: 13 }

            ListView {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: auditTitle.bottom
                anchors.topMargin: 34
                anchors.bottom: parent.bottom
                clip: true
                spacing: 8
                model: root.bridge ? root.bridge.auditModel : null

                delegate: Rectangle {
                    width: ListView.view.width
                    height: 46
                    radius: 11
                    color: "transparent"
                    border.color: Theme.border
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        Text { Layout.preferredWidth: 132; text: model.time; color: Theme.dim; font.pixelSize: 11 }
                        Text { Layout.preferredWidth: 150; text: model.action; color: Theme.text; font.pixelSize: 12; font.bold: true; elide: Text.ElideRight }
                        Text { Layout.preferredWidth: 130; text: model.entity; color: Theme.muted; font.pixelSize: 12; elide: Text.ElideRight }
                        Text { Layout.fillWidth: true; text: model.details; color: Theme.dim; font.pixelSize: 11; elide: Text.ElideRight }
                    }
                }
            }
        }
    }

    Dialog {
        id: loginDialog
        modal: true
        width: Math.min(460, root.width - 80)
        height: 300
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: 22; border.color: Theme.border }
        contentItem: Column {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 16

            Text { text: "Login"; color: Theme.text; font.pixelSize: 24; font.bold: true }
            Text { text: "Connect your account to enable teams, roles, invites and cloud sync."; color: Theme.muted; font.pixelSize: 13; wrapMode: Text.WordWrap; width: parent.width }
            FormField { id: loginEmail; width: parent.width; label: "Email"; placeholder: "you@company.com" }
            FormField { id: loginPassword; width: parent.width; label: "Password"; placeholder: "Password"; echoMode: TextInput.Password }
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 10
                PrimaryButton { width: 150; text: "Cancel"; secondary: true; onClicked: loginDialog.close() }
                PrimaryButton {
                    width: 150
                    text: "Login"
                    icon: "link"
                    onClicked: {
                        if (root.bridge) root.bridge.login(loginEmail.text, loginPassword.text)
                        loginDialog.close()
                    }
                }
            }
        }
    }
}
