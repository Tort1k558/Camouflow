import QtQuick
import QtQuick.Layouts
import theme 1.0
import "../components"

Flickable {
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
            title: "Operator Dashboard"
            subtitle: root.bridge ? root.bridge.operatorSummary : "Workspace overview"
        }

        Item {
            width: parent.width
            height: 72

            Rectangle {
                anchors.fill: parent
                radius: 16
                color: "#0d0d16"
                border.color: Theme.borderSubtle
            }

            Rectangle {
                width: 3
                height: 34
                radius: 2
                anchors.left: parent.left
                anchors.leftMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                color: settingsBridge && settingsBridge.serverEnabled ? Theme.success : Theme.primary
            }

            LineIcon {
                anchors.left: parent.left
                anchors.leftMargin: 34
                anchors.verticalCenter: parent.verticalCenter
                name: settingsBridge && settingsBridge.serverEnabled ? "cloud" : "folder"
                color: settingsBridge && settingsBridge.serverEnabled ? Theme.success : Theme.primary
                size: 20
            }

            Column {
                anchors.left: parent.left
                anchors.leftMargin: 68
                anchors.right: userButton.left
                anchors.rightMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                Text { text: appState && appState.cloudEnabled ? "Cloud team operations" : "Local operations"; color: Theme.text; font.pixelSize: 16; font.bold: true }
                Text {
                    width: parent.width
                    text: appState && appState.cloudEnabled
                        ? ((appState.cloudTeamName || "No team") + " / Role: " + (appState.cloudRole || "none") + " / " + appState.cloudStatus)
                        : (settingsBridge ? settingsBridge.modeSummary : "")
                    color: Theme.muted
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                }
            }
            PrimaryButton {
                id: userButton
                anchors.right: parent.right
                anchors.rightMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                width: 36
                text: ""
                icon: "user"
                iconOnly: true
                secondary: true
                onClicked: appState.setPage("User")
            }
        }

        GridLayout {
            width: parent.width
            columns: 4
            columnSpacing: 0
            rowSpacing: 0
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 132; color: "transparent"; StatCard { anchors.fill: parent; anchors.rightMargin: 22; label: "Profiles"; value: root.bridge ? root.bridge.profiles : 0; change: (root.bridge ? root.bridge.locked : 0) + " locked"; icon: "user"; accent: Theme.primary } Rectangle { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 1; color: Theme.borderSubtle } }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 132; color: "transparent"; StatCard { anchors.fill: parent; anchors.leftMargin: 22; anchors.rightMargin: 22; label: "Running Browsers"; value: root.bridge ? root.bridge.running : 0; change: "+" + (root.bridge ? root.bridge.running : 0); icon: "globe"; accent: Theme.success } Rectangle { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 1; color: Theme.borderSubtle } }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 132; color: "transparent"; StatCard { anchors.fill: parent; anchors.leftMargin: 22; anchors.rightMargin: 22; label: "Failed Runs"; value: root.bridge ? root.bridge.failedRuns : 0; change: "recent"; icon: "play"; accent: root.bridge && root.bridge.failedRuns > 0 ? Theme.danger : Theme.warning } Rectangle { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 1; color: Theme.borderSubtle } }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 132; color: "transparent"; StatCard { anchors.fill: parent; anchors.leftMargin: 22; label: "Proxy Issues"; value: root.bridge ? root.bridge.failedProxies : 0; change: (root.bridge ? root.bridge.proxies : 0) + " total"; icon: "zap"; accent: root.bridge && root.bridge.failedProxies > 0 ? Theme.danger : Theme.pink } }
        }

        RowLayout {
            width: parent.width
            spacing: 28

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 430
                padding: 22

                Row {
                    id: liveHeader
                    anchors.left: parent.left
                    anchors.top: parent.top
                    spacing: 12
                    Rectangle { width: 36; height: 36; radius: 12; color: "transparent"; border.color: Theme.primary; LineIcon { anchors.centerIn: parent; name: "zap"; color: Theme.primary; size: 19 } }
                    Column { anchors.verticalCenter: parent.verticalCenter; spacing: 2; Text { text: "Operator Feed"; color: Theme.text; font.pixelSize: 17; font.bold: true } Text { text: "Locks, runs and team activity"; color: Theme.muted; font.pixelSize: 12 } }
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
                            Column { width: parent.width - 92; anchors.verticalCenter: parent.verticalCenter; spacing: 3; Text { text: model.title; color: Theme.text; font.pixelSize: 13; font.bold: true; elide: Text.ElideRight; width: parent.width } Text { text: model.desc; color: Theme.muted; font.pixelSize: 12; elide: Text.ElideRight; width: parent.width } }
                            Text { text: model.time; color: Theme.dim; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        }
                    }
                }
            }

            GlassCard {
                Layout.preferredWidth: 360
                Layout.preferredHeight: 430
                padding: 22

                Row {
                    id: qaHead
                    anchors.left: parent.left
                    anchors.top: parent.top
                    spacing: 12
                    Rectangle { width: 36; height: 36; radius: 12; color: "transparent"; border.color: Theme.emerald; LineIcon { anchors.centerIn: parent; name: "zap"; color: Theme.emerald; size: 18 } }
                    Text { text: "Critical Issues"; color: Theme.text; font.bold: true; font.pixelSize: 17; anchors.verticalCenter: parent.verticalCenter }
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
                            Text { text: model.title; color: Theme.text; font.pixelSize: 13; font.bold: true; elide: Text.ElideRight; width: parent.width }
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
            Text { id: rsTitle; text: "Active Operations"; color: Theme.text; font.pixelSize: 17; font.bold: true }
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
                    Text { x: 14; text: model.title; color: Theme.text; font.bold: true; font.pixelSize: 14; width: parent.width - 20; elide: Text.ElideRight }
                    Text { x: 14; y: 28; text: model.desc; color: Theme.muted; font.pixelSize: 12; width: parent.width - 20; elide: Text.ElideRight }
                    Text { x: 14; y: 78; text: model.meta; color: Theme.dim; font.pixelSize: 11; width: parent.width - 20; elide: Text.ElideRight }
                }
            }
        }
    }
}
