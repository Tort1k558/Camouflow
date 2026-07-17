import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

Column {
    id: root
    Layout.minimumWidth: 180
    Layout.preferredWidth: 260
    property string label: "Label"
    property alias text: input.text
    property string placeholder: ""
    property int echoMode: TextInput.Normal
    signal editingFinished()
    spacing: 7

    Text { text: root.label; color: Theme.dim; font.pixelSize: 11; font.bold: true }
    Item {
        width: parent.width
        height: 40
        TextField {
            id: input
            anchors.fill: parent
            anchors.leftMargin: 0
            anchors.rightMargin: 0
            color: Theme.text
            placeholderText: root.placeholder
            placeholderTextColor: Theme.dim
            echoMode: root.echoMode
            background: Item {}
            font.pixelSize: 13
            selectionColor: Theme.primary
            onEditingFinished: root.editingFinished()
        }
        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: input.activeFocus ? Theme.primary : Theme.border }
    }
}
