import QtQuick
import QtQuick.Controls

ComboBox {
    id: root
    delegate: ItemDelegate {
        id: entry
        required property int index
        width: ListView.view.width
        text: root.textAt(index)
        palette.text: root.palette.text
        palette.highlightedText: root.palette.highlightedText
        font.weight: root.currentIndex === index ? Font.DemiBold : Font.Normal
        highlighted: root.highlightedIndex === index
        hoverEnabled: root.hoverEnabled
        contentItem: Text {
            text: entry.text
            textFormat: Text.PlainText
            font: entry.font
            color: entry.highlighted ? entry.palette.highlightedText : entry.palette.text
            horizontalAlignment: entry.mirrored ? Text.AlignRight : Text.AlignLeft
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }
}
