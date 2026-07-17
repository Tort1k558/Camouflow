import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import theme 1.0
import "../components"

Flickable {
    id: root
    contentWidth: width
    contentHeight: content.height + 48
    clip: true
    property var bridge: typeof proxiesBridge !== "undefined" ? proxiesBridge : null

    Column {
        id: content
        width: parent.width - 56
        x: 28; y: 24; spacing: 22

        RowLayout {
            width: parent.width
            PageHeader {
                Layout.fillWidth: true
                title: "Proxies"
                subtitle: appState && appState.cloudEnabled
                    ? "Team: " + (appState.cloudTeamName || "No team") + " / Role: " + (appState.cloudRole || "none")
                    : "Proxy pools, assignments and health checks"
            }
            PrimaryButton { width: 38; text: ""; icon: "save"; iconOnly: true; secondary: true; enabled: root.bridge && root.bridge.canManage; onClicked: addPanel.visible = true }
            PrimaryButton { width: 38; text: ""; icon: "plus"; iconOnly: true; enabled: root.bridge && root.bridge.canManage; onClicked: addPanel.visible = !addPanel.visible }
        }

        GridLayout { width: parent.width; columns: 4; columnSpacing: 0; rowSpacing: 0
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 118; color: "transparent"; StatCard { anchors.fill: parent; anchors.rightMargin: 20; label: "Active"; value: root.bridge ? root.bridge.active : 0; icon: "globe"; accent: Theme.success } Rectangle { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 1; color: Theme.borderSubtle } }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 118; color: "transparent"; StatCard { anchors.fill: parent; anchors.leftMargin: 20; anchors.rightMargin: 20; label: "Checking"; value: root.bridge ? root.bridge.checking : 0; icon: "zap"; accent: Theme.warning } Rectangle { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 1; color: Theme.borderSubtle } }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 118; color: "transparent"; StatCard { anchors.fill: parent; anchors.leftMargin: 20; anchors.rightMargin: 20; label: "Failed"; value: root.bridge ? root.bridge.failed : 0; icon: "trash"; accent: Theme.danger } Rectangle { anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 1; color: Theme.borderSubtle } }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 118; color: "transparent"; StatCard { anchors.fill: parent; anchors.leftMargin: 20; label: "Locations"; value: root.bridge ? root.bridge.locations : 0; icon: "network"; accent: Theme.primary } }
        }

        GlassCard { id: addPanel; width: parent.width; height: visible ? 150 : 0; visible: false; padding: 18
            Row { anchors.fill: parent; spacing: 12
                Column { width: parent.width - 150; spacing: 8
                    Text { text: "Proxy list"; color: Theme.text; font.pixelSize: 12; font.bold: true }
                    Rectangle { width: parent.width; height: 92; radius: 11; color: Theme.subtle; border.color: Theme.border
                        TextArea {
                            id: proxyInput
                            anchors.fill: parent
                            anchors.margins: 10
                            color: Theme.text
                            placeholderText: "socks5://host:port:user:password\nhttp://user:pass@host:port"
                            placeholderTextColor: Theme.dim
                            background: Item {}
                            font.pixelSize: 13
                        }
                    }
                }
                PrimaryButton { width: 120; text: "Add"; icon: "plus"; enabled: root.bridge && root.bridge.canManage; anchors.bottom: parent.bottom; onClicked: { if (root.bridge) root.bridge.addProxies(proxyInput.text); proxyInput.text = "" } }
            }
        }

        ColumnLayout {
            width: parent.width
            height: 640
            spacing: 14

            GlassCard {
                Layout.fillWidth: true
                Layout.preferredHeight: 76
                padding: 14

                RowLayout {
                    anchors.fill: parent
                    spacing: 12

                    Column {
                        Layout.preferredWidth: 170
                        Layout.alignment: Qt.AlignVCenter
                        spacing: 3
                        Text { text: "Proxy groups"; color: Theme.dim; font.pixelSize: 11; font.weight: Font.DemiBold }
                        Text {
                            width: parent.width
                            text: root.bridge && root.bridge.selectedPool ? root.bridge.selectedPool : "All groups"
                            color: Theme.text
                            font.pixelSize: 15
                            font.bold: true
                            elide: Text.ElideRight
                        }
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        orientation: ListView.Horizontal
                        model: root.bridge ? root.bridge.poolsModel : null
                        spacing: 8
                        clip: true
                        delegate: Rectangle {
                            width: Math.min(190, Math.max(104, groupName.implicitWidth + groupMeta.implicitWidth + 42))
                            height: 36
                            radius: 18
                            color: model.selected ? Theme.primary : "transparent"
                            border.color: model.selected ? Theme.primary : Theme.border
                            border.width: 1

                            Row {
                                anchors.centerIn: parent
                                spacing: 7
                                Text {
                                    id: groupName
                                    text: model.name === "All pools" ? "All" : model.name
                                    color: model.selected ? "white" : Theme.text
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                    maximumLineCount: 1
                                }
                                Text {
                                    id: groupMeta
                                    text: model.total
                                    color: model.selected ? "#e9ddff" : Theme.dim
                                    font.pixelSize: 11
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (root.bridge) root.bridge.selectPool(model.name)
                            }
                        }
                    }

                    PrimaryButton { width: 34; text: ""; icon: "plus"; iconOnly: true; enabled: root.bridge && root.bridge.canManage; onClicked: { poolNameInput.text = ""; poolDialog.mode = "new"; poolDialog.open() } }
                    PrimaryButton { width: 34; text: ""; icon: "settings"; iconOnly: true; secondary: true; enabled: root.bridge && root.bridge.selectedPool && root.bridge.canManage; onClicked: { poolNameInput.text = root.bridge ? root.bridge.selectedPool : ""; poolDialog.mode = "rename"; poolDialog.open() } }
                    PrimaryButton { width: 34; text: ""; icon: "trash"; iconOnly: true; danger: true; enabled: root.bridge && root.bridge.selectedPool && root.bridge.canAdmin; onClicked: if (root.bridge) root.bridge.deleteSelectedPool() }

                    Rectangle { Layout.preferredWidth: 1; Layout.preferredHeight: 28; color: Theme.borderSubtle }

                    PrimaryButton { width: 34; text: ""; icon: "refresh"; iconOnly: true; secondary: true; enabled: root.bridge && root.bridge.canRun; onClicked: if (root.bridge) root.bridge.checkAll() }
                    PrimaryButton { width: 34; text: ""; icon: "stop"; iconOnly: true; secondary: true; enabled: root.bridge && root.bridge.canManage; onClicked: if (root.bridge) root.bridge.releaseSelected() }
                    PrimaryButton { width: 34; text: ""; icon: "trash"; iconOnly: true; danger: true; enabled: root.bridge && root.bridge.canAdmin; onClicked: if (root.bridge) root.bridge.removeSelected() }
                    PrimaryButton { width: 34; text: ""; icon: "close"; iconOnly: true; secondary: true; onClicked: if (root.bridge) root.bridge.clearSelection() }
                }
            }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: root.bridge ? root.bridge.model : null
                spacing: 12
                clip: true
                delegate: ProxyRow {
                    width: ListView.view.width
                    pool: model.pool
                    proxyIndex: model.index
                    name: model.name
                    location: model.location
                    address: model.address
                    type: model.type
                    latency: model.latency
                    status: model.status
                    accent: model.accent
                    selected: model.selected
                    onSelectionToggled: function(pool, index, selected) {
                        if (root.bridge) root.bridge.setProxySelected(pool, index, selected)
                    }
                    onSettingsClicked: function(pool, index) {
                        if (!root.bridge || !root.bridge.canManage) return
                        var payload = root.bridge ? root.bridge.getProxy(pool, index) : {}
                        proxyEditPool.text = payload.pool || pool
                        proxyEditIndex.text = String(payload.index !== undefined ? payload.index : index)
                        proxyEditName.text = payload.name || ""
                        proxyEditValue.text = payload.value || ""
                        proxyEditDialog.open()
                    }
                    onCheckClicked: function(pool, index) {
                        if (root.bridge && root.bridge.canRun) root.bridge.checkProxy(pool, index)
                    }
                    onDeleteClicked: function(pool, index) {
                        if (root.bridge && root.bridge.canAdmin) root.bridge.deleteProxy(pool, index)
                    }
                }
            }
        }
    }

    Dialog {
        id: poolDialog
        property string mode: "new"
        modal: true
        width: 420; height: 210
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: 18; border.color: Theme.border }
        contentItem: Column { anchors.fill: parent; anchors.margins: 22; spacing: 16
            Text { text: poolDialog.mode === "rename" ? "Rename proxy group" : "New proxy group"; color: Theme.text; font.pixelSize: 20; font.bold: true }
            FormField { id: poolNameInput; width: parent.width; label: "Group name"; placeholder: "US residential" }
            Row { spacing: 10
                PrimaryButton { width: 120; text: "Save"; icon: "save"; enabled: root.bridge && root.bridge.canManage; onClicked: { if (root.bridge) { if (poolDialog.mode === "rename") root.bridge.renameSelectedPool(poolNameInput.text); else root.bridge.createPool(poolNameInput.text) } poolDialog.close() } }
                PrimaryButton { width: 120; text: "Cancel"; secondary: true; onClicked: poolDialog.close() }
            }
        }
    }

    Dialog {
        id: proxyEditDialog
        modal: true
        width: 560
        height: 330
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: 18; border.color: Theme.border }
        contentItem: Column {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14
            Text { text: "Proxy Settings"; color: Theme.text; font.pixelSize: 20; font.bold: true }
            FormField { id: proxyEditPool; visible: false; width: parent.width; label: "Pool" }
            FormField { id: proxyEditIndex; visible: false; width: parent.width; label: "Index" }
            FormField { id: proxyEditName; width: parent.width; label: "Name"; placeholder: "Optional display name" }
            FormField { id: proxyEditValue; width: parent.width; label: "Proxy"; placeholder: "socks5://host:port:user:password" }
            Row {
                spacing: 10
                PrimaryButton {
                    width: 130
                    text: "Save"
                    icon: "save"
                    enabled: root.bridge && root.bridge.canManage
                    onClicked: {
                        if (root.bridge) root.bridge.saveProxy(proxyEditPool.text, parseInt(proxyEditIndex.text), proxyEditName.text, proxyEditValue.text)
                        proxyEditDialog.close()
                    }
                }
                PrimaryButton { width: 120; text: "Cancel"; secondary: true; onClicked: proxyEditDialog.close() }
            }
        }
    }
}
