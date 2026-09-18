import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

WorkspaceDialog {
    id: root
    objectName: "welcomeDialog"
    anchors.centerIn: Overlay.overlay
    width: Math.min(880, Overlay.overlay.width - 64)
    height: 480
    padding: 0
    closePolicy: Popup.NoAutoClose
    visible: settingsBridge ? settingsBridge.onboardingRequired : false
    contentItem: RowLayout {
        spacing: 0
        Rectangle {
            Layout.preferredWidth: 330
            Layout.fillHeight: true
            color: Theme.sidebar
            radius: Theme.radiusLg
            Rectangle { anchors.right: parent.right; width: 12; height: parent.height; color: Theme.sidebar }
            Column {
                anchors.fill: parent; anchors.margins: 32; spacing: 24
                Brand { ink: Theme.sidebarText }
                Item { width: 1; height: 24 }
                Text { width: parent.width; text: "Keep your context.\nFind your flow."; font.pixelSize: 34; font.weight: Font.Medium; font.letterSpacing: -1; color: Theme.primary; wrapMode: Text.WordWrap }
                Text { width: parent.width; text: "Independent profiles.\nOne focused workspace."; color: Theme.sidebarMuted; font.pixelSize: 14; lineHeight: 1.4 }
                Rectangle { width: parent.width; height: 1; color: Theme.sidebarHover }
                Text { text: "CAMOUFOX + CLOAKBROWSER\nDESKTOP FIRST"; font.family: Theme.monoFamily; font.pixelSize: 10; font.letterSpacing: 1; lineHeight: 1.6; color: Theme.sidebarMuted }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 34
            spacing: 18
            Text { text: "YOUR WORKSPACE STARTS HERE"; color: Theme.primaryInk; font.family: Theme.monoFamily; font.pixelSize: 9; font.letterSpacing: 1 }
            Text { text: "Welcome to CamouFlow"; color: Theme.text; font.pixelSize: 27; font.weight: Font.Medium; font.letterSpacing: -0.6 }
            Text { Layout.fillWidth: true; text: "Work locally on this device, or connect your account for shared team access."; color: Theme.muted; font.pixelSize: 13; wrapMode: Text.WordWrap; lineHeight: 1.3 }
            PrimaryButton { Layout.fillWidth: true; text: "Start a local workspace"; icon: "folder"; onClicked: settingsBridge.startLocalMode() }
            PrimaryButton { Layout.fillWidth: true; text: "Connect an account"; icon: "user"; secondary: true; onClicked: settingsBridge.openUserLogin() }
            Text { Layout.fillWidth: true; text: "Local profiles, proxies and scenarios stay on this computer. Team roles, shared resources and cloud backups require a server connection."; color: Theme.dim; font.pixelSize: 12; wrapMode: Text.WordWrap; lineHeight: 1.3 }
            Text { Layout.fillWidth: true; text: appState ? appState.message : ""; color: Theme.primaryInk; font.pixelSize: 12; wrapMode: Text.WordWrap }
            Item { Layout.fillHeight: true }
        }
    }
}
