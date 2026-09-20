import QtQuick
import QtQuick.Controls
import theme 1.0

Column {
    id: mf
    property string label: "Label"
    property alias text: input.text
    property string placeholder: ""
    property int fieldHeight: 92
    signal editingFinished()
    spacing: 8
    Text { text: mf.label; color: Theme.dim; font.pixelSize: 11; font.weight: Font.DemiBold }
    Item { width: parent.width; height: mf.fieldHeight
        ScrollView { anchors.fill: parent; anchors.bottomMargin: 8; clip: true
            TextArea {
                id: input
                color: Theme.text
                placeholderText: mf.placeholder
                placeholderTextColor: Theme.dim
                background: Item {}
                wrapMode: TextArea.Wrap
                font.pixelSize: 13
                onActiveFocusChanged: if (!activeFocus) mf.editingFinished()
            }
        }
        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: input.activeFocus ? Theme.primary : Theme.border }
    }
}
