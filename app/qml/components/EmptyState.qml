import QtQuick
import theme 1.0

Column {
    id: root
    property string title: "Nothing here yet"
    property string description: ""
    property string icon: "folder"
    spacing: 12
    Rectangle {
        width: 46; height: 46; radius: Theme.radius
        color: Theme.selection
        anchors.horizontalCenter: parent.horizontalCenter
        LineIcon { anchors.centerIn: parent; name: root.icon; color: Theme.primaryInk; size: 22 }
    }
    Text { width: parent.width; text: root.title; horizontalAlignment: Text.AlignHCenter; color: Theme.text; font.pixelSize: 15; font.weight: Font.Medium }
    Text { width: parent.width; text: root.description; horizontalAlignment: Text.AlignHCenter; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap }
}
