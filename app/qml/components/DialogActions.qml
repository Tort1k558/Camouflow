import QtQuick
import QtQuick.Layouts
import theme 1.0

Rectangle {
    id: root
    property string acceptText: "Save"
    property string cancelText: "Cancel"
    property bool canAccept: true
    property bool destructive: false
    signal accepted()
    signal rejected()
    implicitHeight: 72
    color: Theme.card
    Rectangle { width: parent.width; height: 1; color: Theme.borderSubtle }
    RowLayout {
        anchors.fill: parent; anchors.leftMargin: 22; anchors.rightMargin: 22
        spacing: 12
        Item { Layout.fillWidth: true }
        PrimaryButton { text: root.cancelText; secondary: true; onClicked: root.rejected() }
        PrimaryButton { text: root.acceptText; danger: root.destructive; enabled: root.canAccept; onClicked: root.accepted() }
    }
}
