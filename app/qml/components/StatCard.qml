import QtQuick
import theme 1.0

Item {
    id: root
    property string label: "Metric"
    property string value: "0"
    property string change: ""
    property string icon: "dashboard"
    property color accent: Theme.primaryInk
    property bool compact: height < 120
    implicitHeight: 132
    height: implicitHeight
    property int padding: 18

    Rectangle {
        anchors.fill: parent
        radius: Theme.radius
        color: Theme.card
        border.color: Theme.border
    }

    Rectangle {
        id: iconBadge
        width: 36
        height: width
        radius: Theme.radiusSm
        color: Theme.subtle
        border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.5)
        anchors.left: parent.left
        anchors.leftMargin: root.padding
        anchors.top: parent.top
        anchors.topMargin: 14
        LineIcon { anchors.centerIn: parent; name: root.icon; color: root.accent; size: 19; lineWidth: 2.2 }
    }

    Text {
        anchors.right: parent.right
        anchors.rightMargin: root.padding
        anchors.top: parent.top
        anchors.topMargin: 14
        text: root.change
        color: Theme.muted
        font.pixelSize: 11
        font.bold: true
    }

    Column {
        anchors.left: parent.left
        anchors.leftMargin: root.padding
        anchors.right: parent.right
        anchors.rightMargin: root.padding
        anchors.top: iconBadge.bottom
        anchors.topMargin: 10
        spacing: 4
        Text { text: root.label; color: Theme.muted; font.pixelSize: 13; width: parent.width; elide: Text.ElideRight }
        Text { text: root.value; color: Theme.text; font.pixelSize: 32; font.weight: Font.Medium; width: parent.width }
    }
}
