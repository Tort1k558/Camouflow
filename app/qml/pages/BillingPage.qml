import QtQuick
import QtQuick.Layouts
import theme 1.0
import "../components"

Flickable {
    id: root
    property var bridge: typeof billingBridge !== "undefined" ? billingBridge : null
    contentWidth: width
    contentHeight: content.height + 64
    clip: true

    Column {
        id: content
        width: parent.width - 56
        x: 28
        y: 24
        spacing: 24

        PageHeader {
            width: parent.width
            title: "Billing & Plan"
            subtitle: appState && appState.cloudEnabled ? "Your plan, usage and upgrade options." : "Connect to Cloud in the User tab to manage billing."
        }

        // License banner
        Rectangle {
            width: parent.width
            height: 48
            radius: 10
            visible: appState && appState.cloudEnabled && root.bridge && !root.bridge.licenseActive && root.bridge.subscriptionStatus.length > 0
            color: "#3a2a12"
            border.color: "#b8791f"
            border.width: 1
            Text {
                anchors.centerIn: parent
                text: "License is " + (root.bridge ? root.bridge.subscriptionStatus : "") + " — some actions are restricted. Contact your admin to renew."
                color: "#ffcf8a"
                font.pixelSize: 13
                font.bold: true
            }
        }

        // Current plan + usage
        GlassCard {
            width: parent.width
            height: 230
            padding: 22

            Column {
                anchors.fill: parent
                spacing: 14

                RowLayout {
                    width: parent.width
                    spacing: 14
                    Text { text: "Plan"; color: Theme.muted; font.pixelSize: 12 }
                    Text { text: root.bridge ? (root.bridge.plan || "—") : "—"; color: Theme.text; font.pixelSize: 20; font.bold: true }
                    Item { Layout.fillWidth: true }
                    Text { text: "Status"; color: Theme.muted; font.pixelSize: 12 }
                    Rectangle {
                        width: statusText.implicitWidth + 20; height: 26; radius: 13
                        color: (root.bridge && root.bridge.licenseActive) ? "#13351f" : "#3a2a12"
                        border.color: (root.bridge && root.bridge.licenseActive) ? "#2f8a4d" : "#b8791f"; border.width: 1
                        Text { id: statusText; anchors.centerIn: parent; text: root.bridge ? (root.bridge.subscriptionStatus || "—") : "—"; color: (root.bridge && root.bridge.licenseActive) ? "#8ef0bd" : "#ffcf8a"; font.pixelSize: 12; font.bold: true }
                    }
                }

                Rectangle { width: parent.width; height: 1; color: Theme.borderSubtle }

                GridLayout {
                    width: parent.width
                    columns: 4
                    columnSpacing: 18
                    rowSpacing: 8
                    Repeater {
                        model: [
                            { label: "Users", used: root.bridge ? root.bridge.usageUsers : 0, max: root.bridge ? root.bridge.maxUsers : 0 },
                            { label: "Profiles", used: root.bridge ? root.bridge.usageProfiles : 0, max: root.bridge ? root.bridge.maxProfiles : 0 },
                            { label: "Proxies", used: root.bridge ? root.bridge.usageProxies : 0, max: root.bridge ? root.bridge.maxProxies : 0 },
                            { label: "Scenarios", used: root.bridge ? root.bridge.usageScenarios : 0, max: root.bridge ? root.bridge.maxScenarios : 0 }
                        ]
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text { text: modelData.label; color: Theme.muted; font.pixelSize: 12 }
                            Text { text: modelData.used + " / " + modelData.max; color: Theme.text; font.pixelSize: 15; font.bold: true }
                        }
                    }
                }

                RowLayout {
                    width: parent.width
                    spacing: 10
                    PrimaryButton {
                        text: "Manage billing"
                        icon: "credit-card"
                        enabled: appState && appState.cloudEnabled && root.bridge && root.bridge.portalUrl.length > 0
                        onClicked: if (root.bridge) root.bridge.openPortal()
                    }
                    PrimaryButton {
                        text: "Refresh"
                        icon: "refresh"
                        secondary: true
                        enabled: appState && appState.cloudEnabled
                        onClicked: if (root.bridge) root.bridge.refresh()
                    }
                    Item { Layout.fillWidth: true }
                    Text { text: root.bridge ? root.bridge.billingError : ""; color: "#ff8a8a"; font.pixelSize: 12; visible: root.bridge && root.bridge.billingError.length > 0; Layout.alignment: Qt.AlignVCenter }
                }
            }
        }

        Text { text: "Available plans"; color: Theme.text; font.pixelSize: 16; font.bold: true }

        Column {
            width: parent.width
            spacing: 12
            Repeater {
                model: root.bridge ? root.bridge.plansModel : []
                GlassCard {
                    width: parent.width
                    height: 96
                    padding: 18
                    RowLayout {
                        anchors.fill: parent
                        spacing: 14
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            Text { text: model.name; color: Theme.text; font.pixelSize: 16; font.bold: true }
                            Text { text: model.price; color: Theme.primaryLight; font.pixelSize: 14; font.bold: true }
                        }
                        Text {
                            color: Theme.muted; font.pixelSize: 12
                            text: model.maxUsers + " users · " + model.maxProfiles + " profiles · " + model.maxProxies + " proxies · " + model.maxScenarios + " scenarios"
                            Layout.alignment: Qt.AlignVCenter
                        }
                        PrimaryButton {
                            text: model.current ? "Current" : "Upgrade"
                            secondary: model.current
                            enabled: appState && appState.cloudEnabled && !model.current
                            onClicked: if (root.bridge) root.bridge.checkout(model.planId)
                        }
                    }
                }
            }
        }

        Item { width: 1; height: 16 }
    }

    Component.onCompleted: if (root.bridge) root.bridge.refresh()
}
