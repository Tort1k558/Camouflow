import QtQuick
import QtQuick.Controls
import theme 1.0

Item {
    id: root
    property alias text: input.text
    property string placeholder: "Search..."
    height: 44

    Rectangle { anchors.fill: parent; color: Theme.card; radius: Theme.radiusSm; border.color: input.activeFocus ? Theme.primaryInk : Theme.border }
    LineIcon { name: "search"; color: Theme.dim; size: 18; anchors.left: parent.left; anchors.leftMargin: 14; anchors.verticalCenter: parent.verticalCenter }
    TextField {
        id: input
        anchors.fill: parent
        anchors.leftMargin: 40
        anchors.rightMargin: 10
        placeholderText: root.placeholder
        color: Theme.text
        placeholderTextColor: Theme.dim
        font.pixelSize: 14
        background: Item {}
        selectionColor: Theme.primary
        selectedTextColor: Theme.primaryText
    }
}
