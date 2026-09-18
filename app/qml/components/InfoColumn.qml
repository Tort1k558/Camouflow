import QtQuick
import QtQuick.Layouts
import theme 1.0

Column {
    property string title: "Title"
    property string value: "Value"
    spacing: 4
    Layout.minimumWidth: 44
    Layout.fillWidth: true
    Text { text: parent.title; color: Theme.dim; font.pixelSize: 11; elide: Text.ElideRight; width: parent.width }
    Text { text: parent.value; color: Theme.text; font.pixelSize: 13; font.weight: Font.DemiBold; elide: Text.ElideRight; width: parent.width }
}
