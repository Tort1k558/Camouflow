import QtQuick
import QtQuick.Layouts
import theme 1.0
import "."

Rectangle {
    id: root
    width: Theme.sidebarWidth
    color: Theme.sidebar
    border.color: Theme.borderSubtle
    property var pages: [
        ["Dashboard", "dashboard"], ["User", "user"], ["Profiles", "user"], ["Browser", "globe"], ["Proxies", "network"],
        ["Scenarios", "workflow"], ["Logs", "logs"], ["Settings", "settings"]
    ]
    Column {
        anchors.fill: parent
        Rectangle {
            width: parent.width; height: 64; color: "transparent"; border.color: Theme.borderSubtle
            Row { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 16; spacing: 10
                Rectangle { width: 31; height: 31; radius: 15; color: Theme.primary; clip: true
                    Image {
                        id: logoImage
                        anchors.fill: parent
                        anchors.margins: 2
                        source: typeof AppRoot !== "undefined" ? "file:///" + AppRoot.replace(/\\/g, "/") + "/logo.ico" : ""
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        visible: status === Image.Ready
                    }
                    Rectangle { width: 13; height: 13; radius: 5; color: Theme.background; anchors.centerIn: parent; visible: logoImage.status !== Image.Ready }
                }
                Text { text: "CamouFlow"; color: Theme.text; font.pixelSize: 18; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
            }
        }
        Column {
            width: parent.width; spacing: 7; padding: 12
            Repeater {
                model: root.pages
                delegate: Rectangle {
                    width: root.width - 24; height: 36; radius: 10
                    color: mouse.containsMouse ? "#10101b" : "transparent"
                    Rectangle {
                        width: 3
                        height: 18
                        radius: 2
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        color: appState && appState.currentPage === modelData[0] ? Theme.primary : "transparent"
                    }
                    Row { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 12; spacing: 12
                        LineIcon { name: modelData[1]; color: appState && appState.currentPage === modelData[0] ? Theme.primary : Theme.muted; size: 19 }
                        Text { text: modelData[0]; color: appState && appState.currentPage === modelData[0] ? Theme.primaryLight : Theme.muted; font.pixelSize: 13; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
                    }
                    MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (appState) appState.setPage(modelData[0]) }
                }
            }
        }
        Item { height: 1; width: 1 }
    }
    Column {
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 12
        spacing: 8
        Rectangle {
            width: parent.width
            height: 74
            color: "transparent"
            border.color: "transparent"
            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 1; color: Theme.borderSubtle }
            Column {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 5
                Text {
                    width: parent.width
                    text: appState && appState.cloudEnabled
                        ? "Cloud / " + (appState.cloudRole || "no role")
                        : "Local mode"
                    color: appState && appState.cloudEnabled ? "#8ef0bd" : "#d7d1ff"
                    font.pixelSize: 12
                    font.bold: true
                }
                Text {
                    width: parent.width
                    text: appState && appState.cloudEnabled
                        ? ((appState.cloudTeamName || "No team selected") + " · " + appState.cloudStatus)
                        : (settingsBridge ? settingsBridge.modeSummary : "")
                    color: Theme.muted
                    font.pixelSize: 11
                    lineHeight: 1.1
                    wrapMode: Text.WordWrap
                    elide: Text.ElideRight
                    maximumLineCount: 3
                }
            }
        }
        Rectangle {
            width: parent.width; height: 28; radius: 0; color: "transparent"
            Text { anchors.centerIn: parent; text: "v1.0.0"; color: Theme.muted; font.pixelSize: 12; font.weight: Font.DemiBold }
        }
    }
}
