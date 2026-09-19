import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

Rectangle {
    id: root
    width: Theme.sidebarWidth
    color: Theme.sidebar
    property var pages: [
        ["Dashboard", "dashboard", "Overview"], ["Profiles", "user", "Profiles"],
        ["Browser", "globe", "Browser engines"], ["Proxies", "network", "Proxies"],
        ["Scenarios", "workflow", "Scenarios"], ["Logs", "logs", "Activity log"],
        ["Settings", "settings", "Settings"]
    ]
    Brand { x: 23; y: 28; ink: Theme.sidebarText }
    Text {
        x: 26; y: 96; text: "YOUR WORKSPACE"; color: Theme.sidebarMuted
        font.family: Theme.monoFamily; font.pixelSize: 10; font.letterSpacing: 1.4
    }
    Column {
        x: 14; y: 128; width: parent.width - 28; spacing: 6
        Repeater {
            model: root.pages
            delegate: Button {
                id: navButton
                required property var modelData
                readonly property bool selected: appState && appState.currentPage === modelData[0]
                width: parent.width; height: 44
                text: modelData[2]
                Accessible.name: text
                background: Rectangle {
                    radius: Theme.radiusSm
                    color: navButton.selected ? Theme.primary : navButton.hovered ? Theme.sidebarHover : "transparent"
                    border.color: navButton.visualFocus ? Theme.primary : "transparent"
                }
                contentItem: Row {
                    spacing: 12
                    leftPadding: 6
                    LineIcon { name: navButton.modelData[1]; color: navButton.selected ? Theme.primaryText : Theme.sidebarMuted; size: 18; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: navButton.text; color: navButton.selected ? Theme.primaryText : Theme.sidebarMuted; font.pixelSize: 13; font.weight: navButton.selected ? Font.DemiBold : Font.Normal; anchors.verticalCenter: parent.verticalCenter }
                }
                onClicked: if (appState) appState.setPage(modelData[0])
            }
        }
    }
    Rectangle {
        id: accountPod
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        anchors.margins: 14
        height: 64; radius: Theme.radius
        color: accountMouse.containsMouse ? "#3c4d36" : Theme.sidebarHover
        readonly property string displayName: {
            if (typeof userBridge === "undefined" || !userBridge || !userBridge.serverEnabled) return ""
            return userBridge.fullName !== "" ? userBridge.fullName : (userBridge.email !== "" ? userBridge.email : "")
        }
        readonly property var tones: ["#d1f366", "#b9e58a", "#a3d79e", "#cfe08a", "#9ccf96", "#bfe0b0"]
        readonly property int tone: {
            var seed = displayName !== "" ? displayName : "local"
            var h = 0
            for (var i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) % 997
            return h % 6
        }
        readonly property string initials: {
            var n = displayName !== "" ? displayName : "You"
            var parts = n.trim().split(/\s+/)
            if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase()
            return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
        }

        Row {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 11

            Item {
                width: 38; height: 38
                anchors.verticalCenter: parent.verticalCenter
                Rectangle {
                    anchors.fill: parent; radius: 19
                    color: accountPod.tones[accountPod.tone]
                    Text { anchors.centerIn: parent; text: accountPod.initials; color: Theme.primaryText; font.pixelSize: 13; font.weight: Font.DemiBold }
                }
                Rectangle {
                    anchors.right: parent.right; anchors.bottom: parent.bottom
                    width: 11; height: 11; radius: 6
                    color: appState && appState.cloudEnabled ? Theme.primary : "#8fa383"
                    border.width: 2; border.color: accountPod.color
                }
            }

            Column {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                width: parent.width - 38 - 11 - 20
                Text {
                    width: parent.width
                    text: accountPod.displayName !== "" ? accountPod.displayName.split("@")[0] : "Local workspace"
                    color: Theme.sidebarText; font.pixelSize: 12; font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    text: appState && appState.cloudEnabled ? "CONNECTED · " + (appState.cloudTeamName || "team") : "LOCAL WORKSPACE"
                    color: Theme.sidebarMuted; font.family: Theme.monoFamily; font.pixelSize: 9; font.letterSpacing: 0.4
                    elide: Text.ElideRight
                }
            }
        }

        MouseArea {
            id: accountMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: if (appState) appState.setPage("User")
        }
    }
}
