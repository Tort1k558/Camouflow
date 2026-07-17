import QtQuick
import QtQuick.Layouts
import theme 1.0
import "../components"

Flickable {
    id: root
    contentWidth: width
    contentHeight: Math.max(height + 1, content.implicitHeight + 80)
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    Column {
        id: content
        width: parent.width - 56
        x: 28
        y: 24
        spacing: 22

        PageHeader { width: parent.width; title: "Settings"; subtitle: "Local application preferences" }

        SettingsSection {
            width: parent.width
            height: 170
            title: "App Settings"
            subtitle: "Runtime configuration"
            icon: "settings"
            accent: Theme.primary
            Column {
                anchors.fill: parent
                spacing: 12
                Text { text: "Data root"; color: Theme.text; font.bold: true; font.pixelSize: 12 }
                Rectangle {
                    width: parent.width
                    height: 42
                    radius: 11
                    color: Theme.subtle
                    border.color: Theme.border
                    Text { anchors.fill: parent; anchors.margins: 12; text: settingsBridge ? settingsBridge.dataRoot : ""; color: Theme.muted; elide: Text.ElideMiddle; font.pixelSize: 12 }
                }
            }
        }
    }
}
