import QtQuick
import theme 1.0

Rectangle {
    id: root
    property int step: 1
    property string title: "Start scenario"
    property string subtitle: ""
    property color accent: Theme.primaryInk
    property bool selected: false
    signal moved()
    signal moveFinished()
    signal clicked()
    signal contextRequested(real localX, real localY)
    signal portPressed(string kind, real localX, real localY)
    signal portDragged(string kind, real localX, real localY)
    signal portReleased(string kind, real localX, real localY)
    property real pressX: 0
    property real pressY: 0
    property real startX: 0
    property real startY: 0
    property bool movedByUser: false
    width: 230
    height: 90
    z: selected ? 20 : (dragArea.drag.active ? 10 : 1)
    radius: 12
    color: selected ? Theme.selection : Theme.card
    border.color: selected ? Theme.primaryInk : Theme.border
    border.width: selected ? 2 : 1
    Text { anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 18; text: "Step " + root.step + "."; color: accent; font.pixelSize: 12; font.bold: true }
    Text { anchors.left: parent.left; anchors.top: parent.top; anchors.topMargin: 42; anchors.leftMargin: 18; width: parent.width - 36; elide: Text.ElideRight; text: root.title; color: Theme.text; font.pixelSize: 14; font.bold: true }
    Text { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.topMargin: 62; anchors.leftMargin: 18; anchors.rightMargin: 18; text: root.subtitle; color: Theme.muted; font.pixelSize: 12; elide: Text.ElideRight }
    Rectangle { width: 9; height: 9; radius: 5; color: Theme.primary; anchors.left: parent.left; anchors.leftMargin: -5; anchors.verticalCenter: parent.verticalCenter }
    Rectangle {
        width: 13; height: 13; radius: 7; color: Theme.success; z: 40
        anchors.right: parent.right; anchors.rightMargin: -7; anchors.verticalCenter: parent.verticalCenter; anchors.verticalCenterOffset: -14
        border.color: Theme.card; border.width: 1
        MouseArea {
            anchors.fill: parent
            anchors.margins: -8
            cursorShape: Qt.CrossCursor
            preventStealing: true
            onPressed: function(mouse) { root.portPressed("ok", parent.x + mouse.x, parent.y + mouse.y) }
            onPositionChanged: function(mouse) { if (mouse.buttons & Qt.LeftButton) root.portDragged("ok", parent.x + mouse.x, parent.y + mouse.y) }
            onReleased: function(mouse) { root.portReleased("ok", parent.x + mouse.x, parent.y + mouse.y) }
        }
    }
    Rectangle {
        width: 13; height: 13; radius: 7; color: Theme.danger; z: 40
        anchors.right: parent.right; anchors.rightMargin: -7; anchors.verticalCenter: parent.verticalCenter; anchors.verticalCenterOffset: 18
        border.color: Theme.card; border.width: 1
        MouseArea {
            anchors.fill: parent
            anchors.margins: -8
            cursorShape: Qt.CrossCursor
            preventStealing: true
            onPressed: function(mouse) { root.portPressed("err", parent.x + mouse.x, parent.y + mouse.y) }
            onPositionChanged: function(mouse) { if (mouse.buttons & Qt.LeftButton) root.portDragged("err", parent.x + mouse.x, parent.y + mouse.y) }
            onReleased: function(mouse) { root.portReleased("err", parent.x + mouse.x, parent.y + mouse.y) }
        }
    }
    MouseArea {
        id: dragArea
        anchors.fill: parent
        preventStealing: true
        drag.target: root
        drag.axis: Drag.XAndYAxis
        drag.minimumX: -100000
        drag.maximumX: 100000
        drag.minimumY: -100000
        drag.maximumY: 100000
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.OpenHandCursor
        onPressed: function(mouse) {
            root.pressX = mouse.x
            root.pressY = mouse.y
            root.startX = root.x
            root.startY = root.y
            root.movedByUser = false
        }
        onPositionChanged: function(mouse) {
            if (mouse.buttons & Qt.LeftButton) {
                if (Math.abs(root.x - root.startX) > 1 || Math.abs(root.y - root.startY) > 1)
                    root.movedByUser = true
                root.moved()
            }
        }
        onReleased: function(mouse) {
            if (mouse.button === Qt.LeftButton) {
                if (root.movedByUser)
                    root.moveFinished()
                else
                    root.clicked()
            } else if (mouse.button === Qt.RightButton) {
                root.contextRequested(mouse.x, mouse.y)
            }
        }
    }
}
