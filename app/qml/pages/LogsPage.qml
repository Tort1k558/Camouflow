import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import theme 1.0
import "../components"

Item {
    id: root

    component FilterChip: Rectangle {
        id: chip
        property string label: "All"
        property string value: "all"
        property int count: 0
        readonly property bool active: logsBridge.levelFilter === chip.value
        height: 34
        radius: Theme.radiusSm
        implicitWidth: chipRow.implicitWidth + 30
        color: active ? Theme.selection : "transparent"
        border.color: active ? Theme.primary : Theme.border
        Row {
            id: chipRow
            anchors.centerIn: parent
            spacing: 7
            Text { anchors.verticalCenter: parent.verticalCenter; text: chip.label; color: chip.active ? Theme.primaryLight : Theme.muted; font.pixelSize: 12; font.weight: Font.DemiBold }
            Rectangle {
                visible: chip.count > 0
                width: countText.implicitWidth + 14; height: 20; radius: 10
                anchors.verticalCenter: parent.verticalCenter
                color: chip.active ? Theme.primary : Theme.subtle
                Text { id: countText; anchors.centerIn: parent; text: chip.count; color: chip.active ? Theme.primaryText : Theme.dim; font.pixelSize: 11; font.weight: Font.DemiBold }
            }
        }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: logsBridge.setLevelFilter(chip.value) }
    }

    ConfirmDialog { id: confirmDialog }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 28
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            PageHeader { Layout.fillWidth: true; height: 72; title: "Logs"; subtitle: "Application and automation events" }
            PrimaryButton { text: "Refresh"; icon: "refresh"; secondary: true; onClicked: logsBridge.refresh() }
            PrimaryButton { text: "Clear log"; icon: "trash"; danger: true; enabled: logsBridge.totalCount > 0; onClicked: confirmDialog.ask("Clear the captured log events? Log files on disk are kept.", function() { logsBridge.clear() }, "Clear") }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            FilterChip { label: "All events"; value: "all"; count: logsBridge.totalCount }
            FilterChip { label: "Errors"; value: "errors"; count: logsBridge.errorCount }
            FilterChip { label: "Warnings + errors"; value: "warnings"; count: logsBridge.warningCount }
            Item { Layout.fillWidth: true }
            Text { text: logList.count + " events shown"; color: Theme.dim; font.pixelSize: 11 }
        }

        GlassCard {
            Layout.fillWidth: true
            Layout.fillHeight: true
            padding: 0

            Rectangle {
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                height: 40
                color: Theme.subtle
                radius: Theme.radiusSm
                Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.borderSubtle }
                Text { anchors.left: parent.left; anchors.leftMargin: 16; anchors.verticalCenter: parent.verticalCenter; text: "LEVEL"; color: Theme.dim; font.pixelSize: 10; font.weight: Font.DemiBold; font.letterSpacing: 0.8 }
                Text { anchors.left: parent.left; anchors.leftMargin: 118; anchors.verticalCenter: parent.verticalCenter; text: "TIME"; color: Theme.dim; font.pixelSize: 10; font.weight: Font.DemiBold; font.letterSpacing: 0.8 }
                Text { anchors.left: parent.left; anchors.leftMargin: 252; anchors.verticalCenter: parent.verticalCenter; text: "EVENT"; color: Theme.dim; font.pixelSize: 10; font.weight: Font.DemiBold; font.letterSpacing: 0.8 }
            }

            ListView {
                id: logList
                anchors.fill: parent
                anchors.topMargin: 40
                model: logsBridge.model
                spacing: 0
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
                EmptyState { anchors.centerIn: parent; width: Math.min(360, parent.width); visible: logList.count === 0; title: logsBridge.levelFilter === "all" ? "A clear activity log" : "No events at this level"; description: logsBridge.levelFilter === "all" ? "Application and automation events will appear here." : "Switch the filter or refresh to see more events."; icon: "logs" }
                delegate: Rectangle {
                    width: ListView.view.width
                    height: Math.max(44, line.implicitHeight + 22)
                    radius: 0
                    color: index % 2 === 0 ? "transparent" : Theme.input
                    border.color: Theme.borderSubtle
                    Text {
                        id: levelText
                        anchors.left: parent.left; anchors.leftMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        width: 86
                        text: model.level
                        color: model.level === "ERROR" ? Theme.danger : model.level === "WARNING" ? Theme.warning : Theme.success
                        font.pixelSize: 11; font.weight: Font.DemiBold
                    }
                    Text {
                        anchors.left: parent.left; anchors.leftMargin: 118
                        anchors.verticalCenter: parent.verticalCenter
                        width: 116
                        text: model.time
                        color: Theme.dim
                        elide: Text.ElideRight
                        font.family: Theme.monoFamily
                        font.pixelSize: 11
                    }
                    Text {
                        id: line
                        anchors.left: parent.left; anchors.leftMargin: 252
                        anchors.right: parent.right; anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        text: model.message
                        color: Theme.muted
                        font.family: Theme.monoFamily
                        font.pixelSize: 12
                        wrapMode: Text.Wrap
                    }
                }
            }
        }
    }
}
