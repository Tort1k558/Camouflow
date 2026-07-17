import QtQuick
import theme 1.0

Rectangle {
    id: root
    property string text: "Button"
    property string icon: ""
    property bool danger: false
    property bool secondary: false
    property bool iconOnly: false
    signal clicked()
    height: root.iconOnly || root.text === "" ? 34 : 36
    radius: root.iconOnly || root.text === "" ? height / 2 : 9
    opacity: enabled ? 1 : 0.45
    color: secondary || danger ? (mouse.containsMouse ? (danger ? "#231016" : "#151520") : "transparent") : (mouse.containsMouse ? Theme.primaryDark : Theme.primary)
    border.color: danger ? "#6f2530" : secondary || root.iconOnly || root.text === "" ? Theme.border : Theme.primary
    border.width: secondary || danger || root.iconOnly || root.text === "" ? 1 : 0

    Row {
        anchors.centerIn: parent
        spacing: root.iconOnly || root.text === "" ? 0 : 8
        LineIcon { visible: root.icon !== ""; name: root.icon; color: root.danger ? "#ff8585" : root.secondary || root.iconOnly || root.text === "" ? Theme.muted : "white"; size: 16 }
        Text { visible: !root.iconOnly && root.text !== ""; text: root.text; color: root.danger ? "#ff8585" : root.secondary ? Theme.text : "white"; font.pixelSize: 13; font.weight: Font.DemiBold }
    }
    MouseArea { id: mouse; anchors.fill: parent; enabled: root.enabled; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.clicked() }
}
