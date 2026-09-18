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
        ["User", "user", "Account & teams"], ["Settings", "settings", "Settings"]
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
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        anchors.margins: 20
        height: 116; radius: Theme.radius
        color: Theme.sidebarHover
        Column {
            anchors.fill: parent; anchors.margins: 14; spacing: 10
            Row {
                spacing: 8
                Rectangle { width: 6; height: 6; radius: 3; color: Theme.primary; anchors.verticalCenter: parent.verticalCenter }
                Text { text: appState && appState.cloudEnabled ? "CONNECTED WORKSPACE" : "LOCAL WORKSPACE"; color: Theme.sidebarText; font.family: Theme.monoFamily; font.pixelSize: 9; font.letterSpacing: 0.5 }
            }
            Text {
                width: parent.width
                text: appState && appState.cloudEnabled ? (appState.cloudTeamName || "No team selected") + " / " + appState.cloudStatus : "Your profiles. Your device.\nYour control."
                color: Theme.sidebarMuted; font.pixelSize: 11; lineHeight: 1.3
                wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight
            }
        }
    }
}
