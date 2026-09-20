import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

Flickable {
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    id: root
    property var bridge: typeof dashboardBridge !== "undefined" ? dashboardBridge : null
    contentWidth: width
    contentHeight: content.height + 64
    clip: true

    Column {
        id: content
        width: parent.width - 56
        x: 28
        y: 24
        spacing: 26

        PageHeader {
            width: parent.width
            title: "Workspace overview"
            subtitle: root.bridge ? root.bridge.operatorSummary : "Workspace overview"
        }

        Rectangle {
            width: parent.width
            height: 174
            radius: Theme.radiusLg
            color: Theme.primary
            clip: true
            Column {
                x: 26; y: 23
                width: parent.width - 240
                spacing: 10
                Text { text: "KEEP YOUR CONTEXT. FIND YOUR FLOW."; color: Theme.primaryInk; font.family: Theme.monoFamily; font.pixelSize: 9; font.letterSpacing: 1.2 }
                Text { text: "Different profiles. One workflow."; color: Theme.primaryText; font.pixelSize: 28; font.weight: Font.Medium; font.letterSpacing: -0.8 }
                Text { width: parent.width; text: appState && appState.cloudEnabled ? "Team: " + (appState.cloudTeamName || "No team") + " / " + appState.cloudStatus : "Your browser sessions, proxies and automation. In one place."; color: Theme.primaryInk; font.pixelSize: 12; elide: Text.ElideRight }
                Row { spacing: 10
                    PrimaryButton { width: 144; text: "Open profiles"; icon: "user"; secondary: true; onClicked: appState.setPage("Profiles") }
                    PrimaryButton { width: 146; text: "Build a scenario"; icon: "workflow"; secondary: true; onClicked: appState.setPage("Scenarios") }
                }
            }
            Rectangle {
                width: 158; height: 106; radius: 9; rotation: 12
                anchors.right: parent.right; anchors.rightMargin: 32; y: 27
                color: "#c3df76"; border.color: "#9bb34f"
            }
            Rectangle {
                width: 158; height: 106; radius: 9; rotation: -8
                anchors.right: parent.right; anchors.rightMargin: 54; y: 44
                color: Theme.primary; border.color: "#9bb34f"
                Rectangle { y: 24; width: parent.width; height: 1; color: "#9bb34f" }
                Text { x: 12; y: 7; text: "profile_01"; font.family: Theme.monoFamily; font.pixelSize: 8; color: Theme.primaryInk }
                Brand { compact: true; anchors.centerIn: parent; scale: 1.6; ink: Theme.primaryText }
                Text { anchors.bottom: parent.bottom; anchors.bottomMargin: 9; x: 12; text: "LOCAL / ISOLATED"; font.family: Theme.monoFamily; font.pixelSize: 7; font.letterSpacing: 1; color: Theme.primaryInk }
            }
        }

        GridLayout {
            width: parent.width
            columns: 4
            columnSpacing: 14
            rowSpacing: 0
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 132; color: "transparent"; StatCard { anchors.fill: parent; label: "Profiles"; value: root.bridge ? root.bridge.profiles : 0; change: (root.bridge ? root.bridge.locked : 0) + " locked"; icon: "user"; accent: Theme.primaryInk } }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 132; color: "transparent"; StatCard { anchors.fill: parent; label: "Active profiles"; value: root.bridge ? root.bridge.running : 0; change: "+" + (root.bridge ? root.bridge.running : 0); icon: "globe"; accent: Theme.success } }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 132; color: "transparent"; StatCard { anchors.fill: parent; label: "Failed Runs"; value: root.bridge ? root.bridge.failedRuns : 0; change: "recent"; icon: "play"; accent: root.bridge && root.bridge.failedRuns > 0 ? Theme.danger : Theme.warning } }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 132; color: "transparent"; StatCard { anchors.fill: parent; label: "Proxy Issues"; value: root.bridge ? root.bridge.failedProxies : 0; change: (root.bridge ? root.bridge.proxies : 0) + " total"; icon: "zap"; accent: root.bridge && root.bridge.failedProxies > 0 ? Theme.danger : Theme.pink } }
        }

        RowLayout {
            width: parent.width
            spacing: 20

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 330
                padding: 22

                Row {
                    id: liveHeader
                    anchors.left: parent.left
                    anchors.top: parent.top
                    spacing: 12
                    Rectangle { width: 36; height: 36; radius: 12; color: "transparent"; border.color: Theme.primaryInk; LineIcon { anchors.centerIn: parent; name: "zap"; color: Theme.primaryInk; size: 19 } }
                    Column { anchors.verticalCenter: parent.verticalCenter; spacing: 2; Text { text: "Activity feed"; color: Theme.text; font.pixelSize: 17; font.weight: Font.DemiBold } Text { text: "Locks, runs and team activity"; color: Theme.muted; font.pixelSize: 12 } }
                }

                ListView {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: liveHeader.bottom
                    anchors.topMargin: 18
                    anchors.bottom: parent.bottom
                    spacing: 0
                    model: root.bridge ? root.bridge.activityModel : null
                    clip: true

                    delegate: Rectangle {
                        width: ListView.view.width
                        height: 58
                        color: "transparent"
                        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.borderSubtle }
                        Row {
                            anchors.fill: parent
                            anchors.leftMargin: 2
                            anchors.rightMargin: 2
                            spacing: 12
                            Rectangle { width: 7; height: 7; radius: 4; color: model.type === "warning" ? Theme.warning : model.type === "success" ? Theme.success : Theme.primary; anchors.verticalCenter: parent.verticalCenter }
                            Column { width: parent.width - 92; anchors.verticalCenter: parent.verticalCenter; spacing: 3; Text { text: model.title; color: Theme.text; font.pixelSize: 13; font.weight: Font.DemiBold; elide: Text.ElideRight; width: parent.width } Text { text: model.desc; color: Theme.muted; font.pixelSize: 12; elide: Text.ElideRight; width: parent.width } }
                            Text { text: model.time; color: Theme.dim; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        }
                    }
                }
            }

            GlassCard {
                Layout.preferredWidth: 360
                Layout.preferredHeight: 330
                padding: 22

                Row {
                    id: qaHead
                    anchors.left: parent.left
                    anchors.top: parent.top
                    spacing: 12
                    Rectangle { width: 36; height: 36; radius: 12; color: "transparent"; border.color: Theme.emerald; LineIcon { anchors.centerIn: parent; name: "zap"; color: Theme.emerald; size: 18 } }
                    Text { text: "Workspace health"; color: Theme.text; font.weight: Font.DemiBold; font.pixelSize: 17; anchors.verticalCenter: parent.verticalCenter }
                }

                ListView {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: qaHead.bottom
                    anchors.topMargin: 18
                    anchors.bottom: parent.bottom
                    spacing: 8
                    clip: true
                    model: root.bridge ? root.bridge.issuesModel : null
                    delegate: Rectangle {
                        width: ListView.view.width
                        height: 58
                        radius: 12
                        color: "transparent"
                        border.color: Theme.borderSubtle
                        Rectangle { width: 4; height: parent.height - 18; radius: 2; anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter; color: model.accent }
                        Column {
                            anchors.left: parent.left
                            anchors.leftMargin: 20
                            anchors.right: parent.right
                            anchors.rightMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 3
                            Text { text: model.title; color: Theme.text; font.pixelSize: 13; font.weight: Font.DemiBold; elide: Text.ElideRight; width: parent.width }
                            Text { text: model.desc; color: Theme.muted; font.pixelSize: 11; elide: Text.ElideRight; width: parent.width }
                            Text { text: model.meta; color: Theme.dim; font.pixelSize: 10; elide: Text.ElideRight; width: parent.width }
                        }
                    }
                }
            }
        }

        GlassCard {
            width: parent.width
            height: 210
            padding: 22
            Text { id: rsTitle; text: "Active operations"; color: Theme.text; font.pixelSize: 17; font.weight: Font.DemiBold }
            ListView {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: rsTitle.bottom
                anchors.topMargin: 16
                anchors.bottom: parent.bottom
                orientation: ListView.Horizontal
                spacing: 14
                model: root.bridge ? root.bridge.operatorModel : null
                delegate: GlassCard {
                    width: 300
                    height: 126
                    padding: 16
                    Rectangle { width: 4; height: 42; radius: 2; color: model.accent }
                    Text { x: 14; text: model.title; color: Theme.text; font.weight: Font.DemiBold; font.pixelSize: 14; width: parent.width - 20; elide: Text.ElideRight }
                    Text { x: 14; y: 28; text: model.desc; color: Theme.muted; font.pixelSize: 12; width: parent.width - 20; elide: Text.ElideRight }
                    Text { x: 14; y: 78; text: model.meta; color: Theme.dim; font.pixelSize: 11; width: parent.width - 20; elide: Text.ElideRight }
                }
            }
        }
    }
}
