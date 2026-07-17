import QtQuick
import QtQuick.Layouts
import theme 1.0
import "."

GlassCard {
    id: root
    property string pool: ""
    property int proxyIndex: -1
    property string name: "Proxy"
    property string location: "Location"
    property string address: "0.0.0.0:0"
    property string type: "HTTP"
    property string latency: "?"
    property string status: "Active"
    property color accent: Theme.success
    property bool selected: false
    signal settingsClicked(string pool, int index)
    signal checkClicked(string pool, int index)
    signal selectionToggled(string pool, int index, bool selected)
    signal deleteClicked(string pool, int index)
    height: 80
    padding: 18

    RowLayout {
        anchors.fill: parent
        spacing: Math.max(10, Math.min(24, root.width / 70))

        Rectangle {
            Layout.preferredWidth: 22
            Layout.preferredHeight: 22
            Layout.alignment: Qt.AlignVCenter
            radius: 6
            color: root.selected ? Theme.primary : "transparent"
            border.color: root.selected ? Theme.primaryLight : Theme.border
            Text { anchors.centerIn: parent; text: root.selected ? "✓" : ""; color: "white"; font.bold: true; font.pixelSize: 13 }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.selectionToggled(root.pool, root.proxyIndex, !root.selected) }
        }

        Rectangle {
            Layout.preferredWidth: 42
            Layout.preferredHeight: 42
            Layout.alignment: Qt.AlignVCenter
            radius: 14
            color: "transparent"
            border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.35)
            LineIcon { anchors.centerIn: parent; name: "globe"; color: root.accent; size: 22 }
        }

        Column {
            Layout.preferredWidth: 220
            Layout.minimumWidth: 90
            Layout.maximumWidth: 340
            Layout.alignment: Qt.AlignVCenter
            spacing: 4
            Text { text: root.name; color: Theme.text; font.pixelSize: 15; font.bold: true; elide: Text.ElideRight; width: parent.width }
            Text { text: root.location; color: Theme.muted; font.pixelSize: 13; elide: Text.ElideRight; width: parent.width }
        }

        InfoColumn { title: "IP Address"; value: root.address; Layout.fillWidth: true; Layout.minimumWidth: 150; Layout.preferredWidth: 260 }
        InfoColumn { title: "Type"; value: root.type; Layout.minimumWidth: 52; Layout.preferredWidth: 70 }
        InfoColumn { title: "Latency"; value: root.latency; Layout.minimumWidth: 40; Layout.preferredWidth: 65 }

        Row {
            Layout.minimumWidth: 24
            Layout.preferredWidth: 96
            Layout.alignment: Qt.AlignVCenter
            spacing: 8
            Rectangle { width: 7; height: 7; radius: 4; color: root.accent; anchors.verticalCenter: parent.verticalCenter }
            Text { text: root.status; color: Theme.muted; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight; width: parent.width - 15 }
        }

        Row {
            Layout.preferredWidth: 124
            Layout.minimumWidth: 124
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            spacing: 8
            PrimaryButton {
                width: 36
                icon: "zap"
                text: ""
                secondary: true
                onClicked: root.checkClicked(root.pool, root.proxyIndex)
            }
            PrimaryButton {
                width: 36
                icon: "settings"
                text: ""
                secondary: true
                onClicked: root.settingsClicked(root.pool, root.proxyIndex)
            }
            PrimaryButton {
                width: 36
                icon: "trash"
                text: ""
                danger: true
                onClicked: root.deleteClicked(root.pool, root.proxyIndex)
            }
        }
    }
}
