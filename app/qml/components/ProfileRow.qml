import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "."

GlassCard {
    id: root
    property string name: "Profile"
    property string ident: "#0000"
    property string browser: "Camoufox"
    property string proxy: "None"
    property string health: "Not checked"
    property string lastActive: "idle"
    property string status: "Stopped"
    property string tags: "#profile"
    property string lockedBy: ""
    property string lockExpires: ""
    property bool chosen: false
    signal selectionToggled(bool selected)
    property bool running: false
    property bool startAllowed: false
    property bool stopAllowed: false
    property bool canRun: true
    property bool canManage: true
    property bool canAdmin: true
    signal startClicked()
    signal stopClicked()
    signal settingsClicked()
    signal deleteClicked()
    signal contextRequested(real x, real y)
    height: 78
    padding: 18

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        propagateComposedEvents: true
        onClicked: function(mouse) {
            if (mouse.button === Qt.RightButton)
                root.contextRequested(mouse.x, mouse.y)
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: Math.max(8, Math.min(18, root.width / 80))

        CheckBox { checked: root.chosen; onClicked: root.selectionToggled(checked) }
        Rectangle {
            Layout.preferredWidth: 42; Layout.preferredHeight: 42; radius: 14
            Layout.alignment: Qt.AlignVCenter
            color: "transparent"
            border.color: running ? Theme.success : Theme.borderSubtle
            LineIcon { anchors.centerIn: parent; name: "globe"; color: running ? Theme.success : Theme.dim; size: 22 }
        }

        Column {
            Layout.fillWidth: true
            Layout.preferredWidth: 260
            Layout.minimumWidth: 100
            Layout.maximumWidth: 360
            Layout.alignment: Qt.AlignVCenter
            spacing: 5
            Text { text: root.name; color: Theme.text; font.pixelSize: 15; font.weight: Font.DemiBold; elide: Text.ElideRight; width: parent.width }

            Text { text: root.tags + "  /  " + root.ident.substring(0, 8); color: Theme.primaryLight; font.pixelSize: 12; elide: Text.ElideRight; width: parent.width }
        }

        InfoColumn { title: "Browser"; value: root.browser; Layout.minimumWidth: 110; Layout.preferredWidth: 110 }
        InfoColumn { title: "Proxy"; value: root.proxy; Layout.fillWidth: true; Layout.minimumWidth: 90; Layout.preferredWidth: 180 }
        InfoColumn { visible: root.width >= 1050; title: "Health"; value: root.health; Layout.minimumWidth: 72; Layout.preferredWidth: 86 }
        InfoColumn { visible: root.width >= 1150; title: "Last Active"; value: root.lastActive; Layout.minimumWidth: 68; Layout.preferredWidth: 90 }

        Row {
            Layout.minimumWidth: 24
            Layout.preferredWidth: 96
            Layout.alignment: Qt.AlignVCenter
            spacing: 8
            Rectangle { width: 7; height: 7; radius: 4; color: running ? Theme.success : root.lockedBy ? Theme.warning : Theme.dim; anchors.verticalCenter: parent.verticalCenter }
            Text {
                text: root.lockedBy && !root.running
                    ? "Locked: " + root.lockedBy + (root.lockExpires ? " until " + new Date(root.lockExpires).toLocaleTimeString(Qt.locale(), "HH:mm") : "")
                    : root.status
                color: Theme.muted
                font.pixelSize: 13
                anchors.verticalCenter: parent.verticalCenter
                elide: Text.ElideRight
                width: parent.width - 15
            }
        }

        Row {
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            Layout.minimumWidth: 124
            spacing: 8
            PrimaryButton { width: 36; icon: stopAllowed ? "stop" : "play"; text: ""; secondary: true; tooltip: stopAllowed ? "Stop browser" : "Open browser"; enabled: root.startAllowed || root.stopAllowed; onClicked: stopAllowed ? root.stopClicked() : root.startClicked() }
            PrimaryButton { width: 36; icon: "settings"; text: ""; secondary: true; tooltip: "Profile settings"; enabled: root.canManage; onClicked: root.settingsClicked() }
            PrimaryButton { width: 36; text: "..."; tooltip: "Profile actions"; secondary: true; onClicked: root.contextRequested(root.width - 220, root.height) }
        }
    }
}
