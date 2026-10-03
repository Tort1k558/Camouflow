import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import theme 1.0

ColumnLayout {
    id: root
    objectName: "taskBatchPanel"
    property string profileName: ""
    property bool canRun: false
    property bool expanded: false
    readonly property var rows: tasksBridge.csvRows
    readonly property int duplicateCount: rows.filter(function(row) { return row.duplicate > 0 }).length
    readonly property int runCount: rows.length - (skipDuplicates.checked ? duplicateCount : 0)
    readonly property string delimiter: separator.currentIndex === 0 ? "," : ";"
    Layout.fillWidth: true
    spacing: 12

    FileDialog { id: importDialog; title: "Import task inputs"; nameFilters: ["CSV (*.csv)"]; onAccepted: tasksBridge.importCsv(selectedFile.toString(), root.delimiter) }
    FileDialog { id: templateDialog; title: "Save CSV template"; fileMode: FileDialog.SaveFile; nameFilters: ["CSV (*.csv)"]; onAccepted: tasksBridge.exportCsvTemplate(selectedFile.toString(), root.delimiter) }
    ConfirmDialog { id: confirmation; objectName: "taskBatchConfirmation"; width: Math.min(560, root.width) }

    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.border }
    PrimaryButton { objectName: "expandTaskBatch"; text: root.expanded ? "Hide CSV batch" : "Run from CSV"; secondary: true; onClicked: root.expanded = !root.expanded }
    ColumnLayout {
        Layout.fillWidth: true; visible: root.expanded; spacing: 12
        Text { Layout.fillWidth: true; text: "One row, one run"; color: Theme.text; font.pixelSize: 16; font.weight: Font.DemiBold }
        Text { Layout.fillWidth: true; text: "Download the headers, fill your inputs and import a UTF-8 CSV. Up to 200 rows / 1 MiB. Every row is checked before queuing."; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap }
        RowLayout {
            Layout.fillWidth: true
            ComboBox { id: separator; objectName: "taskCsvSeparator"; model: ["Comma (,)", "Semicolon (;)"]; enabled: root.rows.length === 0 }
            PrimaryButton { text: "CSV template"; secondary: true; onClicked: templateDialog.open() }
            PrimaryButton { text: root.rows.length ? "Replace CSV" : "Import CSV"; secondary: true; onClicked: importDialog.open() }
        }
        Text { Layout.fillWidth: true; visible: root.rows.length > 0; text: tasksBridge.csvName + " · " + root.rows.length + " rows · " + root.duplicateCount + " duplicates"; textFormat: Text.PlainText; color: Theme.text; wrapMode: Text.WordWrap }
        ListView {
            objectName: "taskCsvPreview"
            Layout.fillWidth: true; Layout.preferredHeight: Math.min(180, root.rows.length * 42)
            model: root.rows; clip: true; ScrollBar.vertical: ScrollBar {}
            delegate: Text {
                required property var modelData
                width: ListView.view.width; height: 42
                text: "Row " + modelData.row + (modelData.duplicate ? " (same as " + modelData.duplicate + ")" : "") + "  " + modelData.summary
                textFormat: Text.PlainText; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
                color: modelData.duplicate ? Theme.muted : Theme.text; font.pixelSize: 12
            }
        }
        CheckBox { id: skipDuplicates; objectName: "taskCsvSkipDuplicates"; visible: root.duplicateCount > 0; text: "Skip rows with identical inputs"; checked: false }
        Text { Layout.fillWidth: true; visible: root.rows.length > 0; text: "Rows run sequentially on this profile. A failed row does not stop other rows; nothing is automatically retried. Write file results get separate run folders. Scripts and website changes are not isolated."; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap }
        PrimaryButton {
            objectName: "queueTaskBatch"; visible: root.rows.length > 0
            text: "Queue " + root.runCount + " rows"; icon: "play"; enabled: root.canRun && root.runCount > 0
            onClicked: {
                var profile = root.profileName
                var skip = skipDuplicates.checked
                confirmation.ask("Queue " + root.runCount + " rows on “" + profile + "”? Website changes may be irreversible. Other rows continue after a failure. Inputs are saved in the local queue. Resume the queue separately; keep the app open.", function() {
                    if (tasksBridge.runBatch(profile, skip)) appState.setPage("ScenarioRuns")
                }, "Queue batch")
            }
        }
    }
    ColumnLayout {
        Layout.fillWidth: true; visible: tasksBridge.batchRuns.length > 0; spacing: 8
        RowLayout {
            Layout.fillWidth: true
            Text { Layout.fillWidth: true; text: "Latest batch · " + tasksBridge.batchRuns.filter(function(row) { return ["success", "failed", "canceled", "interrupted"].indexOf(row.status) >= 0 }).length + "/" + tasksBridge.batchRuns.length + " finished"; color: Theme.text; font.pixelSize: 14 }
            PrimaryButton { text: "Results folder"; secondary: true; onClicked: tasksBridge.openBatchOutputs() }
        }
        ListView {
            objectName: "taskBatchRuns"
            Layout.fillWidth: true; Layout.preferredHeight: Math.min(240, tasksBridge.batchRuns.length * 48)
            model: tasksBridge.batchRuns; clip: true; ScrollBar.vertical: ScrollBar {}
            delegate: RowLayout {
                required property var modelData
                width: ListView.view.width; height: 48
                Text { Layout.fillWidth: true; text: "Row " + modelData.batch_row + " · " + modelData.status + (modelData.error ? " — " + modelData.error : ""); textFormat: Text.PlainText; elide: Text.ElideRight; color: modelData.status === "failed" ? Theme.warning : Theme.muted; font.pixelSize: 12 }
                PrimaryButton { text: "Details"; secondary: true; onClicked: tasksBridge.inspectBatchRun(modelData.id) }
            }
        }
    }
}
