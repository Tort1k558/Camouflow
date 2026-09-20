import QtQuick
import QtQuick.Layouts
import theme 1.0
import "."

Rectangle {
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

    height: 46
    radius: 9
    color: root.selected ? Theme.selection : (rowHover.hovered ? Theme.input : "transparent")
    border.color: root.selected ? Theme.primary : Theme.borderSubtle
    border.width: 1

    HoverHandler { id: rowHover }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 6
        spacing: 10

        Rectangle {
            Layout.preferredWidth: 18
            Layout.preferredHeight: 18
            radius: 9
            color: root.selected ? Theme.primary : "transparent"
            border.color: root.selected ? Theme.primaryLight : Theme.border
            Text { anchors.centerIn: parent; text: root.selected ? "✓" : ""; color: Theme.primaryText; font.weight: Font.DemiBold; font.pixelSize: 11 }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.selectionToggled(root.pool, root.proxyIndex, !root.selected) }
        }

        Rectangle {
            Layout.preferredWidth: 8
            Layout.preferredHeight: 8
            radius: 4
            color: root.accent
        }

        Column {
            Layout.preferredWidth: 168
            Layout.minimumWidth: 110
            spacing: 1
            Text { text: root.name; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight; width: parent.width }
            Text { text: root.location; color: Theme.dim; font.pixelSize: 10; elide: Text.ElideRight; width: parent.width }
        }

        Text {
            Layout.fillWidth: true
            Layout.minimumWidth: 140
            text: root.address
            color: Theme.muted
            font.family: Theme.monoFamily
            font.pixelSize: 11
            elide: Text.ElideMiddle
        }

        Rectangle {
            Layout.preferredWidth: typeLabel.implicitWidth + 16
            Layout.preferredHeight: 19
            radius: 6
            color: Theme.subtle
            Text { id: typeLabel; anchors.centerIn: parent; text: root.type; color: Theme.primaryLight; font.pixelSize: 9; font.weight: Font.DemiBold; font.letterSpacing: 0.5 }
        }

        Text {
            Layout.preferredWidth: 56
            text: root.latency
            color: Theme.dim
            font.family: Theme.monoFamily
            font.pixelSize: 11
            horizontalAlignment: Text.AlignRight
        }

        Rectangle {
            Layout.preferredWidth: statusLabel.implicitWidth + 16
            Layout.preferredHeight: 19
            radius: 10
            color: root.status === "Active" ? Theme.selection : root.status === "Failed" ? Theme.dangerSurface : Theme.subtle
            Text {
                id: statusLabel
                anchors.centerIn: parent
                text: root.status.toUpperCase()
                color: root.status === "Active" ? Theme.primaryInk : root.status === "Failed" ? Theme.danger : Theme.dim
                font.pixelSize: 8
                font.weight: Font.DemiBold
                font.letterSpacing: 0.6
            }
        }

        Row {
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            spacing: 5
            visible: rowHover.hovered || root.selected
            PrimaryButton {
                width: 30; height: 26
                icon: "zap"
                text: ""
                iconOnly: true
                secondary: true
                onClicked: root.checkClicked(root.pool, root.proxyIndex)
            }
            PrimaryButton {
                width: 30; height: 26
                icon: "settings"
                text: ""
                iconOnly: true
                secondary: true
                onClicked: root.settingsClicked(root.pool, root.proxyIndex)
            }
            PrimaryButton {
                width: 30; height: 26
                icon: "trash"
                text: ""
                iconOnly: true
                danger: true
                onClicked: root.deleteClicked(root.pool, root.proxyIndex)
            }
        }
    }
}
