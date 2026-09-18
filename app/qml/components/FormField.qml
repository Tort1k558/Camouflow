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
            leftPadding: 12
            rightPadding: 12
            background: Rectangle {
                color: Theme.input
                radius: Theme.radiusSm
                border.color: input.activeFocus ? Theme.primaryInk : Theme.border
                border.width: input.activeFocus ? 2 : 1
            }
            font.pixelSize: 13
            selectionColor: Theme.primary
            selectedTextColor: Theme.primaryText
            onEditingFinished: root.editingFinished()
        }
    }
}
