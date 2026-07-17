import QtQuick
import theme 1.0
import "."

GlassCard {
    id: root
    property string title: "Section"
    property string subtitle: ""
    property string icon: "settings"
    property color accent: Theme.primary
    height: 250
    padding: 18
    default property alias body: body.data

    Row {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: 10

        Rectangle {
            width: 3
            height: 32
            radius: 2
            color: root.accent
            anchors.verticalCenter: parent.verticalCenter
        }
        Column {
            width: parent.width - 18
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2
            Text { text: root.title; color: Theme.text; font.pixelSize: 15; font.bold: true }
            Text { text: root.subtitle; color: Theme.muted; font.pixelSize: 12; elide: Text.ElideRight; width: parent.width }
        }
    }

    Item {
        id: body
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.topMargin: 20
        anchors.bottom: parent.bottom
    }
}
