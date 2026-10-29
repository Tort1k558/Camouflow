import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

Column {
    id: root
    property string title: "Title"
    property string value: "Value"
    property string tooltip: ""
    HoverHandler { id: hover }
    ToolTip.visible: hover.hovered && root.tooltip.length > 0
    ToolTip.text: root.tooltip
    ToolTip.delay: 400
    spacing: 4
    Layout.minimumWidth: 44
    Layout.fillWidth: true
    Text { textFormat: Text.PlainText; text: parent.title; color: Theme.dim; font.pixelSize: 11; elide: Text.ElideRight; width: parent.width }
    Text { textFormat: Text.PlainText; text: parent.value; color: Theme.text; font.pixelSize: 13; font.weight: Font.DemiBold; elide: Text.ElideRight; width: parent.width }
}
