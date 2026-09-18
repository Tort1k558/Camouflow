import QtQuick
import theme 1.0

Item {
    id: root
    property alias content: content.data
    default property alias contentData: content.data
    property int padding: 20
    clip: false

    Rectangle {
        anchors.fill: parent
        radius: Theme.radius
        color: Theme.card
        border.color: Theme.border
    }

    Item {
        id: content
        anchors.fill: parent
        anchors.margins: root.padding
    }
}
