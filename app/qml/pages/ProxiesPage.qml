import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import theme 1.0
import "../components"

Item {
    id: root
    property var bridge: typeof proxiesBridge !== "undefined" ? proxiesBridge : null
    ConfirmDialog { id: confirmDialog }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 28; spacing: 14
        RowLayout {
            Layout.fillWidth: true
            PageHeader { Layout.fillWidth: true; height: 72; title: "Proxies"; subtitle: "Connections, pool management and health checks" }
            PrimaryButton { text: "New group"; secondary: true; enabled: root.bridge && root.bridge.canManage; onClicked: { poolNameInput.text = ""; poolDialog.mode = "new"; poolDialog.open() } }
            PrimaryButton { text: "Import proxies"; icon: "plus"; enabled: root.bridge && root.bridge.canManage; onClicked: proxyImportDialog.open() }
        }
        // compact stat strip instead of blocky cards
        RowLayout {
            Layout.fillWidth: true
            spacing: 0
            Repeater {
                model: [
                    { label: "ACTIVE", value: root.bridge ? root.bridge.active : 0, color: Theme.success },
                    { label: "CHECKING", value: root.bridge ? root.bridge.checking : 0, color: Theme.warning },
                    { label: "FAILED", value: root.bridge ? root.bridge.failed : 0, color: Theme.danger },
                    { label: "LOCATIONS", value: root.bridge ? root.bridge.locations : 0, color: Theme.primaryLight },
                ]
                delegate: RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.preferredWidth: index === 0 ? 0 : 22; Layout.fillHeight: true }
                    Rectangle { visible: index > 0; Layout.fillHeight: true; Layout.preferredWidth: 1; color: Theme.borderSubtle }
                    Column {
                        spacing: 2
                        Text { text: modelData.label; color: Theme.dim; font.family: Theme.monoFamily; font.pixelSize: 9; font.letterSpacing: 1.2 }
                        Text { text: modelData.value; color: modelData.color; font.pixelSize: 22; font.weight: Font.DemiBold }
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 12
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
                                    color: model.selected ? Theme.primaryText : Theme.text
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                    maximumLineCount: 1
                                }
                                Text {
                                    id: groupMeta
                                    text: model.total
                                    color: model.selected ? Theme.primaryInk : Theme.dim
                                    font.pixelSize: 11
                                }
                                Rectangle {
                                    visible: model.source === "shared"
                                    width: shareLabel.implicitWidth + 10; height: 16; radius: 8
                                    color: model.selected ? Theme.primaryText : Theme.selection
                                    Text { id: shareLabel; anchors.centerIn: parent; text: "SHARED"; color: model.selected ? Theme.primary : Theme.primaryInk; font.pixelSize: 8; font.weight: Font.DemiBold }
                                }
                                Rectangle {
                                    visible: model.source === "global"
                                    width: globalLabel.implicitWidth + 10; height: 16; radius: 8
                                    color: model.selected ? Theme.primaryText : Theme.subtle
                                    Text { id: globalLabel; anchors.centerIn: parent; text: "GLOBAL"; color: model.selected ? Theme.primary : Theme.dim; font.pixelSize: 8; font.weight: Font.DemiBold }
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (root.bridge) root.bridge.selectPool(model.name)
                            }
                        }
                    }
            PrimaryButton { text: "Group actions"; secondary: true; enabled: root.bridge && root.bridge.selectedPool; onClicked: groupMenu.popup() }
            PrimaryButton { text: "Check all proxies"; icon: "refresh"; secondary: true; enabled: root.bridge && root.bridge.canRun && proxyList.count > 0; onClicked: root.bridge.checkAll() }
        }
        Rectangle {
            visible: root.bridge && root.bridge.selectedCount > 0
            Layout.fillWidth: true; Layout.preferredHeight: 52
            radius: Theme.radiusSm; color: Theme.selection
            RowLayout {
                anchors.fill: parent; anchors.margins: 8; spacing: 8
                Text { text: (root.bridge ? root.bridge.selectedCount : 0) + " selected"; color: Theme.primaryInk; font.pixelSize: 12; Layout.leftMargin: 8 }
                Item { Layout.fillWidth: true }
                PrimaryButton { text: "Release assignment"; secondary: true; enabled: root.bridge && root.bridge.canManage; onClicked: root.bridge.releaseSelected() }
                PrimaryButton { text: "Remove quarantine"; secondary: true; enabled: root.bridge && root.bridge.canManage; onClicked: root.bridge.releaseQuarantineSelected() }
                PrimaryButton { text: "Delete selected"; danger: true; enabled: root.bridge && root.bridge.canAdmin; onClicked: confirmDialog.ask("Delete the selected proxies? This action cannot be undone.", function() { root.bridge.removeSelected() }) }
                PrimaryButton { text: "Clear selection"; secondary: true; onClicked: root.bridge.clearSelection() }
            }
        }
        ListView {
                id: proxyList
                EmptyState { anchors.centerIn: parent; width: Math.min(360, parent.width); visible: proxyList.count === 0; title: "No proxies in this group"; description: "Import your connections or create a proxy pool to get started."; icon: "network" }
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: root.bridge ? root.bridge.model : null
                spacing: 5
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
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
                        if (root.bridge && root.bridge.canAdmin) confirmDialog.ask("Delete this proxy? This action cannot be undone.", function() { root.bridge.deleteProxy(pool, index) })
                    }
                }
            }
        Text { text: proxyList.count + " proxies in this view"; color: Theme.dim; font.pixelSize: 11 }
    }
    Menu {
        id: groupMenu
        MenuItem { text: "Share pool…"; enabled: root.bridge && root.bridge.canManage; onTriggered: { shareSlug.text = ""; shareDialog.open() } }
        MenuItem { text: "Rename group"; enabled: root.bridge && root.bridge.canManage; onTriggered: { poolNameInput.text = root.bridge.selectedPool; poolDialog.mode = "rename"; poolDialog.open() } }
        MenuSeparator {}
        MenuItem { text: "Delete group"; enabled: root.bridge && root.bridge.canAdmin; onTriggered: confirmDialog.ask('Delete group "' + root.bridge.selectedPool + '" and its proxies?', function() { root.bridge.deleteSelectedPool() }) }
    }
    WorkspaceDialog {
        id: proxyImportDialog
        objectName: "proxyImportDialog"
        anchors.centerIn: Overlay.overlay
        width: Math.min(780, root.width - 48); height: 280; padding: 0
        contentItem: Item { Row { anchors.fill: parent; anchors.margins: 22; spacing: 12
                Column { width: parent.width - 150; spacing: 8
                    Text { text: "Proxy list"; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold }
                    Rectangle { width: parent.width; height: 180; radius: Theme.radiusSm; color: Theme.subtle; border.color: Theme.border
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
                PrimaryButton { width: 120; text: "Import"; icon: "plus"; enabled: root.bridge && root.bridge.canManage; anchors.bottom: parent.bottom; onClicked: { if (root.bridge) root.bridge.addProxies(proxyInput.text); proxyInput.text = ""; proxyImportDialog.close() } }
            } }
    }
    WorkspaceDialog {
        id: poolDialog
        objectName: "poolDialog"
        property string mode: "new"
        modal: true
        width: 420; height: 210
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: 18; border.color: Theme.border }
        contentItem: Column { anchors.fill: parent; anchors.margins: 22; spacing: 16
            Text { text: poolDialog.mode === "rename" ? "Rename proxy group" : "New proxy group"; color: Theme.text; font.pixelSize: 20; font.weight: Font.DemiBold }
            FormField { id: poolNameInput; width: parent.width; label: "Group name"; placeholder: "US residential" }
            Row { spacing: 10
                PrimaryButton { width: 120; text: "Save"; icon: "save"; enabled: root.bridge && root.bridge.canManage; onClicked: { if (root.bridge) { if (poolDialog.mode === "rename") root.bridge.renameSelectedPool(poolNameInput.text); else root.bridge.createPool(poolNameInput.text) } poolDialog.close() } }
                PrimaryButton { width: 120; text: "Cancel"; secondary: true; onClicked: poolDialog.close() }
            }
        }
    }

    WorkspaceDialog {
        id: proxyEditDialog
        objectName: "proxyEditDialog"
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
            Text { text: "Proxy Settings"; color: Theme.text; font.pixelSize: 20; font.weight: Font.DemiBold }
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

    WorkspaceDialog {
        id: shareDialog
        objectName: "shareDialog"
        anchors.centerIn: Overlay.overlay
        modal: true
        width: Math.min(460, root.width - 60)
        height: 300
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: Theme.radiusLg; border.color: Theme.border }
        contentItem: Column {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14
            Text { text: "Share pool"; color: Theme.text; font.pixelSize: 20; font.weight: Font.DemiBold }
            Text { text: root.bridge && root.bridge.selectedPool ? 'Pool "' + root.bridge.selectedPool + '" — share with another team by its slug.' : "Select a pool first."; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap; width: parent.width }
            FormField { id: shareSlug; width: parent.width; label: "Target team slug"; placeholder: "team-slug" }
            Column {
                width: parent.width
                spacing: 4
                Text { text: "Permission"; color: Theme.dim; font.pixelSize: 11; font.weight: Font.DemiBold }
                ComboBox {
                    id: sharePermission
                    width: parent.width
                    model: ["attach", "read"]
                    currentIndex: 0
                }
            }
            Row {
                spacing: 10
                PrimaryButton { width: 120; text: "Share"; icon: "link"; enabled: root.bridge && root.bridge.selectedPool && shareSlug.text !== ""; onClicked: { root.bridge.sharePool(root.bridge.selectedPool, shareSlug.text, sharePermission.currentText); shareDialog.close() } }
                PrimaryButton { width: 100; text: "Cancel"; secondary: true; onClicked: shareDialog.close() }
            }
        }
    }

}