import QtQuick
import QtQuick.Controls
import theme 1.0

Item {
    id: root
    property alias text: input.text
    property string placeholder: "Search..."
    height: 44

    LineIcon { name: "search"; color: Theme.dim; size: 18; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter }
    TextField {
        id: input
        anchors.fill: parent
        anchors.leftMargin: 30
        anchors.rightMargin: 0
        placeholderText: root.placeholder
        color: Theme.text
        placeholderTextColor: Theme.dim
        font.pixelSize: 14
        background: Item {}
        selectionColor: Theme.primary
    }
    Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: input.activeFocus ? Theme.primary : Theme.border }
}
