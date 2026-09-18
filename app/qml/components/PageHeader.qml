import QtQuick
import theme 1.0

Item {
    id: root
    property string title: "Page"
    property string subtitle: ""
    property string badge: ""
    implicitHeight: 92
    height: implicitHeight
    Column {
        anchors.left: parent.left
        anchors.right: badgeItem.visible ? badgeItem.left : parent.right
        anchors.rightMargin: badgeItem.visible ? 20 : 0
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8
        Text { width: parent.width; text: root.title; color: Theme.text; font.pixelSize: 32; font.weight: Font.Medium; font.letterSpacing: -1; elide: Text.ElideRight }
        Text { width: parent.width; text: root.subtitle; color: Theme.muted; font.pixelSize: 12; elide: Text.ElideRight }
    }
    Rectangle {
        id: badgeItem
        visible: root.badge.length > 0
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: badgeText.implicitWidth + 36; height: 32; radius: Theme.radiusSm
        color: Theme.selection; border.color: Theme.border
        Row { anchors.centerIn: parent; spacing: 8
            Rectangle { width: 6; height: 6; radius: 3; color: Theme.success; anchors.verticalCenter: parent.verticalCenter }
            Text { id: badgeText; text: root.badge; color: Theme.primaryInk; font.pixelSize: 11 }
        }
    }
}
