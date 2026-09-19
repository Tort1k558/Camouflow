import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "components"
import "pages"

ApplicationWindow {
    id: root
    width: 1460
    height: 900
    minimumWidth: 1180
    minimumHeight: 720
    visible: true
    title: "CamouFlow"
    color: Theme.background
    font.family: Theme.fontFamily
    palette.window: Theme.background
    palette.windowText: Theme.text
    palette.base: Theme.input
    palette.alternateBase: Theme.subtle
    palette.text: Theme.text
    palette.button: Theme.card
    palette.buttonText: Theme.text
    palette.highlight: Theme.primary
    palette.highlightedText: Theme.primaryText
    palette.mid: Theme.border
    palette.dark: Theme.muted
    palette.light: Theme.card
    palette.toolTipBase: Theme.sidebar
    palette.toolTipText: Theme.sidebarText
    palette.placeholderText: Theme.dim

    Rectangle {
        anchors.fill: parent
        color: Theme.background
        RowLayout {
            anchors.fill: parent
            spacing: 0
            Sidebar { Layout.preferredWidth: Theme.sidebarWidth; Layout.fillHeight: true }
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: Theme.background
                Rectangle {
                    id: workspaceBar
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    height: 62
                    color: Theme.input
                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.border }
                    Row {
                        anchors.left: parent.left; anchors.leftMargin: 30; anchors.verticalCenter: parent.verticalCenter
                        spacing: 12
                        Text { text: "WORKSPACE"; font.family: Theme.monoFamily; font.pixelSize: 10; font.letterSpacing: 1.2; color: Theme.dim }
                        Text { text: "/"; color: Theme.border }
                        Text { text: appState ? appState.currentPage : "Dashboard"; color: Theme.text; font.pixelSize: 12 }
                    }
                    Row {
                        anchors.right: parent.right; anchors.rightMargin: 28; anchors.verticalCenter: parent.verticalCenter
                        spacing: 9
                        Rectangle { width: 6; height: 6; radius: 3; color: Theme.success; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: appState && appState.cloudEnabled ? "Team workspace" : "Local workspace"; font.pixelSize: 11; color: Theme.muted }
                    }
                }
                Loader {
                    id: pageLoader
                    anchors.fill: parent
                    anchors.topMargin: workspaceBar.height
                    objectName: "pageLoader"
                    sourceComponent: {
                        if (!appState) return dashboardPage
                        if (appState.currentPage === "User") return userPage
                        if (appState.currentPage === "Profiles") return profilesPage
                        if (appState.currentPage === "Browser") return browserPage
                        if (appState.currentPage === "Proxies") return proxiesPage
                        if (appState.currentPage === "Scenarios") return scenariosPage
                        if (appState.currentPage === "Logs") return logsPage
                        if (appState.currentPage === "Settings") return settingsPage
                        return dashboardPage
                    }
                }
            }
        }
    }

    WelcomeDialog {}

    // Global toast: appState.notify/message was previously invisible
    // (only the closed WelcomeDialog read it), so cloud errors and
    // "Opening Google sign-in…" feedback vanished silently.
    Rectangle {
        id: appToast
        property string text: ""
        visible: text !== ""
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 18
        width: Math.min(440, toastRow.implicitWidth + 30)
        height: 40
        radius: 10
        color: "#222e25"

        Row {
            id: toastRow
            anchors.centerIn: parent
            spacing: 9
            Rectangle { width: 7; height: 7; radius: 4; color: "#d1f366"; anchors.verticalCenter: parent.verticalCenter }
            Text {
                text: appToast.text
                color: "#edf4e6"
                font.pixelSize: 12
                elide: Text.ElideRight
                maximumLineCount: 2
                wrapMode: Text.WordWrap
                width: Math.min(380, contentWidth)
            }
        }

        Timer { id: toastTimer; interval: 4000; onTriggered: appToast.text = "" }

        Connections {
            target: appState
            function onMessageChanged() {
                if (appState && appState.message !== "") {
                    appToast.text = appState.message
                    toastTimer.restart()
                }
            }
        }
    }

    Component { id: dashboardPage; DashboardPage {} }
    Component { id: userPage; UserPage {} }
    Component { id: profilesPage; ProfilesPage {} }
    Component { id: browserPage; BrowserPage {} }
    Component { id: proxiesPage; ProxiesPage {} }
    Component { id: scenariosPage; ScenariosPage {} }
    Component { id: logsPage; LogsPage {} }
    Component { id: settingsPage; SettingsPage {} }
}
