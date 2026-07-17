import QtQuick
import theme 1.0

Item {
    id: root
    property alias content: content.data
    default property alias contentData: content.data
    property int padding: 20
    clip: false

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: Theme.borderSubtle
        opacity: 0.9
    }

    Item {
        id: content
        anchors.fill: parent
        anchors.margins: root.padding
    }
}
