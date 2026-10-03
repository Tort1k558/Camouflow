import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import theme 1.0

GlassCard {
    id: root
    objectName: "aiResultPanel"
    padding: 22
    implicitHeight: content.implicitHeight + 44
    property bool detailsOpen: false
    property int outputIndex: 0
    readonly property var outputs: aiBridge.outputPreviews
    readonly property var preview: outputs.length > 0 ? outputs[Math.min(outputIndex, outputs.length - 1)] : null
    Connections { target: aiBridge; function onChanged() { if (root.outputIndex >= root.outputs.length) root.outputIndex = 0 } }
    FileDialog { id: exportDialog; title: "Export results"; fileMode: FileDialog.SaveFile; nameFilters: root.preview && root.preview.format === "table" ? ["JSON (*.json)", "CSV (*.csv)"] : ["JSON (*.json)"]; onAccepted: aiBridge.exportResults(selectedFile.toString(), root.preview ? root.preview.name : "") }

    ColumnLayout {
        id: content; anchors.left: parent.left; anchors.right: parent.right; spacing: 16
        RowLayout {
            Layout.fillWidth: true
            Text { Layout.fillWidth: true; text: "Result"; color: Theme.text; font.pixelSize: 20; font.weight: Font.DemiBold }
            PrimaryButton { objectName: "aiExportButton"; text: root.preview && root.preview.format === "table" ? "Export JSON / CSV" : "Export JSON"; icon: "save"; secondary: true; visible: root.outputs.length > 0; tooltip: "JSON includes all outputs. CSV exports the selected table."; onClicked: exportDialog.open() }
        }
        ComboBox {
            objectName: "aiOutputSelector"; Layout.fillWidth: true; visible: root.outputs.length > 1
            model: root.outputs; textRole: "name"; currentIndex: root.outputIndex
            onActivated: function(index) { root.outputIndex = index }
        }
        RowLayout {
            visible: root.preview !== null; Layout.fillWidth: true
            Text { text: root.preview ? root.preview.name : ""; color: Theme.muted; font.pixelSize: 12; font.weight: Font.DemiBold }
            Item { Layout.fillWidth: true }
            Text { text: root.preview && root.preview.format === "table" ? root.preview.count + " rows · " + root.preview.columns.length + " columns" : "Text"; color: Theme.dim; font.pixelSize: 11 }
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.preview && root.preview.format === "table" ? Math.min(350, 42 + Math.min(30, root.preview.count) * 54) : 0
            visible: root.preview !== null && root.preview.format === "table"
            color: Theme.input; border.color: Theme.border; radius: Theme.radiusSm; clip: true
            Flickable {
                id: tableScroll; objectName: "aiResultTable"
                anchors.fill: parent; anchors.margins: 1; clip: true
                contentWidth: table.implicitWidth; contentHeight: table.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
                ScrollBar.horizontal: ScrollBar {}
                GridLayout {
                    id: table
                    columns: root.preview ? Math.max(1, root.preview.columns.length) : 1
                    columnSpacing: 1; rowSpacing: 1
                    readonly property real cellWidth: Math.max(160, (tableScroll.width - 2) / columns)
                    Repeater {
                        model: root.preview ? root.preview.columns : []
                        delegate: Rectangle {
                            required property var modelData
                            Layout.preferredWidth: table.cellWidth; Layout.preferredHeight: 40; color: Theme.subtle
                            Text { anchors.fill: parent; anchors.margins: 10; text: modelData; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
                        }
                    }
                    Repeater {
                        model: root.preview ? root.preview.cells : []
                        delegate: TextArea {
                            required property var modelData
                            Layout.preferredWidth: table.cellWidth; Layout.preferredHeight: 53
                            text: modelData; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; clip: true
                            color: Theme.text; font.pixelSize: 12; padding: 10
                            background: Rectangle { color: Theme.card }
                        }
                    }
                }
            }
        }
        Text { visible: root.preview !== null && root.preview.format === "table" && root.preview.count > 30; text: "Preview shows the first 30 rows. Export includes every row."; color: Theme.dim; font.pixelSize: 11 }
        ScrollView {
            Layout.fillWidth: true; Layout.preferredHeight: 240; visible: root.preview === null || root.preview.format === "text"
            TextArea { objectName: "aiTextResult"; text: root.preview ? root.preview.text : aiBridge.resultText; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; color: Theme.text; font.pixelSize: 13; padding: 14; background: Rectangle { color: Theme.input; radius: Theme.radiusSm } }
        }
        Text {
            Layout.fillWidth: true; visible: root.preview !== null && root.preview.source !== ""
            text: root.preview ? "Source: " + root.preview.source : ""; textFormat: Text.PlainText
            color: Theme.dim; font.pixelSize: 11; wrapMode: Text.WrapAnywhere
        }
        PrimaryButton { objectName: "aiResultDetails"; text: root.detailsOpen ? "Hide technical details" : "Technical details"; secondary: true; onClicked: root.detailsOpen = !root.detailsOpen }
        ColumnLayout {
            Layout.fillWidth: true; visible: root.detailsOpen; spacing: 10
            Text { Layout.fillWidth: true; text: aiBridge.resultText; textFormat: Text.PlainText; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap; visible: root.outputs.length > 0 }
            ScrollView {
                Layout.fillWidth: true; Layout.preferredHeight: 200; visible: aiBridge.outputsJson !== ""
                TextArea { text: aiBridge.outputsJson; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; color: Theme.text; font.family: Theme.monoFamily; font.pixelSize: 12 }
            }
        }
    }
}
