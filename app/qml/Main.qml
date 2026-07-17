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
                gradient: Gradient {
                    GradientStop { position: 0; color: "#0b0b14" }
                    GradientStop { position: 1; color: "#10101d" }
                }
                Loader {
                    id: pageLoader
                    anchors.fill: parent
                    sourceComponent: {
                        if (!appState) return dashboardPage
                        if (appState.currentPage === "User") return userPage
                        if (appState.currentPage === "Billing") return billingPage
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

    Rectangle {
        id: onboardingOverlay
        anchors.fill: parent
        z: 20
        visible: settingsBridge ? settingsBridge.onboardingRequired : false
        color: "#dd070812"

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.AllButtons
            hoverEnabled: true
            preventStealing: true
            propagateComposedEvents: false
            onWheel: function(wheel) { wheel.accepted = true }
        }

        Rectangle {
            anchors.centerIn: parent
            width: 920
            height: 620
            radius: 18
            color: "#f00f1018"
            border.color: Theme.borderSubtle
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.margins: 28
                spacing: 24

                Item {
                    Layout.preferredWidth: 360
                    Layout.fillHeight: true

                    Column {
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 18

                        Rectangle { width: 58; height: 58; radius: 18; color: Theme.primary
                            Text { anchors.centerIn: parent; text: "C"; color: "white"; font.pixelSize: 28; font.bold: true }
                        }
                        Text { text: "Welcome to CamouFlow"; color: Theme.text; font.pixelSize: 30; font.bold: true; wrapMode: Text.WordWrap; width: parent.width }
                        Text {
                            width: parent.width
                            text: "Open User to sign in, accept invites and manage teams. Or continue locally."
                            color: Theme.muted
                            font.pixelSize: 14
                            lineHeight: 1.25
                            wrapMode: Text.WordWrap
                        }

                        Rectangle { width: parent.width; height: 1; color: Theme.borderSubtle }

                        Text { text: "Local mode limitations"; color: Theme.text; font.pixelSize: 15; font.bold: true }
                        Text {
                            width: parent.width
                            text: settingsBridge ? settingsBridge.localModeLimitations : ""
                            color: "#d7d1ff"
                            font.pixelSize: 13
                            lineHeight: 1.25
                            wrapMode: Text.WordWrap
                        }

                        Item { width: 1; height: 1; Layout.fillHeight: true }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 14

                    Text { text: "Account"; color: Theme.text; font.pixelSize: 24; font.bold: true }
                    Text {
                        Layout.fillWidth: true
                        text: "Account login, invites, team selection and access management are inside the User tab."
                        color: Theme.muted
                        font.pixelSize: 14
                        wrapMode: Text.WordWrap
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12

                        PrimaryButton {
                            Layout.fillWidth: true
                            text: "Open User"
                            icon: "user"
                            onClicked: settingsBridge.openUserLogin()
                        }
                        PrimaryButton {
                            Layout.fillWidth: true
                            text: "Use local mode"
                            icon: "folder"
                            secondary: true
                            onClicked: settingsBridge.startLocalMode()
                        }
                    }

                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 86
                        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; height: 1; color: Theme.borderSubtle }
                        Text {
                            anchors.fill: parent
                            anchors.topMargin: 16
                            text: "You can connect later from the User tab. Local data stays on this computer until Cloud is connected."
                            color: Theme.muted
                            font.pixelSize: 13
                            wrapMode: Text.WordWrap
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: appState ? appState.message : ""
                        color: Theme.primaryLight
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                    }

                    Item { Layout.fillHeight: true }
                }
            }
        }
    }

    Component { id: dashboardPage; DashboardPage {} }
    Component { id: userPage; UserPage {} }
    Component { id: billingPage; BillingPage {} }
    Component { id: profilesPage; ProfilesPage {} }
    Component { id: browserPage; BrowserPage {} }
    Component { id: proxiesPage; ProxiesPage {} }
    Component { id: scenariosPage; ScenariosPage {} }
    Component { id: logsPage; LogsPage {} }
    Component { id: settingsPage; SettingsPage {} }
}
