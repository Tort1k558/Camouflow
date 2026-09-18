import QtQuick
import QtQuick.Controls
import theme 1.0

Rectangle {
    id: root
    property string text: "Button"
    property string icon: ""
    property bool danger: false
    property bool secondary: false
    property bool iconOnly: false
    property string tooltip: ""
    signal clicked()
    implicitWidth: iconOnly || text === "" ? 36 : label.implicitWidth + (icon ? 54 : 32)
    implicitHeight: 38
    width: implicitWidth
    height: implicitHeight
    radius: Theme.radiusSm
    activeFocusOnTab: enabled
    Accessible.role: Accessible.Button
    Accessible.name: tooltip || text || icon
    Accessible.onPressAction: if (enabled) clicked()
    Keys.onSpacePressed: if (enabled) clicked()
    Keys.onReturnPressed: if (enabled) clicked()
    opacity: enabled ? 1 : 0.4
    color: danger ? (mouse.containsMouse ? "#f3d9d6" : Theme.dangerSurface) : secondary ? (mouse.containsMouse ? Theme.subtle : Theme.card) : (mouse.containsMouse ? Theme.primaryDark : Theme.primary)
    border.color: activeFocus ? Theme.primaryInk : danger ? "#eac9c6" : secondary ? Theme.border : "transparent"
    border.width: activeFocus ? 2 : 1
    Row {
        anchors.centerIn: parent
        spacing: root.iconOnly || root.text === "" ? 0 : 8
        LineIcon { visible: root.icon !== ""; name: root.icon; color: root.danger ? Theme.danger : root.secondary ? Theme.muted : Theme.primaryText; size: 16; anchors.verticalCenter: parent.verticalCenter }
        Text { id: label; visible: !root.iconOnly && root.text !== ""; text: root.text; color: root.danger ? Theme.danger : Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
    }
    MouseArea { id: mouse; anchors.fill: parent; enabled: root.enabled; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: { root.forceActiveFocus(); root.clicked() } }
    ToolTip.visible: mouse.containsMouse && (root.tooltip !== "" || root.iconOnly || root.text === "")
    ToolTip.text: root.tooltip || root.text || root.icon
    ToolTip.delay: 600
}
