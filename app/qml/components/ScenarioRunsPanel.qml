import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import theme 1.0
import "../components"

Flickable {
    id: root
    contentWidth: width
    contentHeight: body.implicitHeight + 56
    clip: true
    ScrollBar.vertical: ScrollBar {}
    property string selectedJob: ""
    ConfirmDialog { id: confirmation; width: Math.min(460, root.width - 32) }
    ColumnLayout {
        id: body
        x: 28; y: 24; width: parent.width - 56; spacing: 16
        PageHeader { title: "Scenario runs"; subtitle: "Schedule, monitor and inspect your executions"; Layout.fillWidth: true }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 12
            Text { Layout.fillWidth: true; text: "Desktop must remain open. Queue starts paused after restart; interrupted jobs are never retried automatically. Pausing prevents new jobs; running steps continue."; color: Theme.muted; wrapMode: Text.WordWrap }
            CheckBox { text: "Debug in separate window"; checked: operationsBridge.debugEnabled; onToggled: operationsBridge.setDebugEnabled(checked) }
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                    Text { text: "Profiles"; color: Theme.muted }
                    ScrollView {
                        Layout.fillWidth: true; Layout.preferredHeight: 120
                        Column {
                            width: parent.width
                            Repeater {
                                model: profilesBridge.selectionModel
                                CheckBox {
                                    text: model.name
                                    checked: operationsBridge.selectedProfiles.split("\n").indexOf(model.name) >= 0
                                    onClicked: operationsBridge.selectProfile(model.name, checked)
                                }
                            }
                        }
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                    Text { text: "Scenario"; color: Theme.muted }
                    ComboBox { id: scenario; Layout.fillWidth: true; model: scenariosBridge.model; textRole: "name"; onCountChanged: { var selected = find(scenariosBridge.selectedName); if (selected >= 0) currentIndex = selected } }
                    FormField { id: scheduled; Layout.fillWidth: true; label: "Local time (empty = now)"; placeholder: "YYYY-MM-DD HH:MM" }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                ComboBox { id: policy; Layout.preferredWidth: 260; model: ["Keep assigned proxy", "Check assigned proxy; stop if failed", "Replace failed from selected pool"] }
                FormField { id: pool; Layout.fillWidth: true; label: "Replacement pool"; enabled: policy.currentIndex === 2 }
                PrimaryButton { text: "Add to queue"; enabled: scenariosBridge.canRun && operationsBridge.selectedProfiles !== "" && scenario.currentIndex >= 0; onClicked: confirmation.ask("Queue these profiles? Scenario steps are saved with the job. Proxy replacement, if selected, persists the new assignment before launch.", function() { operationsBridge.enqueue(operationsBridge.selectedProfiles, scenario.currentText, scheduled.text, ["unchanged", "check", "replace_failed"][policy.currentIndex], pool.text) }, "Add to queue") }
            }
            RowLayout {
                Text { text: "Parallel browsers"; color: Theme.text }
                SpinBox { id: parallel; from: 1; to: 8; value: operationsBridge.parallelism }
                PrimaryButton { text: operationsBridge.paused ? "Resume queue" : "Pause queue"; onClicked: operationsBridge.configure(parallel.value, !operationsBridge.paused) }
                PrimaryButton { text: "Apply limit"; secondary: true; onClicked: operationsBridge.configure(parallel.value, operationsBridge.paused) }
                PrimaryButton { text: "Cancel all"; danger: true; onClicked: confirmation.ask("Cancel queued jobs and request cooperative cancellation of running jobs?", function() { operationsBridge.cancel("") }, "Cancel jobs") }
                PrimaryButton { text: "Clear finished"; secondary: true; onClicked: confirmation.ask("Remove finished queue records? Artifact files will be retained.", function() { operationsBridge.clearFinished() }, "Clear records") }
            }
            ListView {
                id: queueList
                Layout.fillWidth: true; Layout.preferredHeight: 260; clip: true; spacing: 6
                model: operationsBridge.jobsModel
                ScrollBar.vertical: ScrollBar {}
                EmptyState { anchors.centerIn: parent; width: Math.min(360, parent.width); visible: queueList.count === 0; title: "No queued jobs"; description: "Select profiles and a scenario, then add them to the queue."; icon: "play" }
                delegate: Rectangle {
                    width: ListView.view.width; height: 64; radius: 8
                    color: root.selectedJob === model.id ? Theme.subtle : Theme.card
                    border.color: Theme.border
                    RowLayout {
                        anchors.fill: parent; anchors.margins: 10
                        ColumnLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: model.scenario + " / " + model.profile; color: Theme.text; elide: Text.ElideRight }
                            Text { text: model.status + " · " + model.due + " · " + model.duration; color: Theme.muted; font.pixelSize: 11 }
                        }
                        PrimaryButton { text: "Details"; secondary: true; onClicked: { root.selectedJob = model.id; operationsBridge.selectJob(model.id) } }
                        PrimaryButton { text: "Cancel"; secondary: true; visible: model.status === "queued" || model.status === "running"; onClicked: operationsBridge.cancel(model.id) }
                    }
                }
            }
            RowLayout {
                PrimaryButton { text: "Open artifacts"; secondary: true; enabled: root.selectedJob !== ""; onClicked: operationsBridge.openArtifacts(root.selectedJob) }
                PrimaryButton { text: "Screenshot"; secondary: true; enabled: root.selectedJob !== ""; onClicked: operationsBridge.openResultFile(root.selectedJob, "screenshot") }
                PrimaryButton { text: "Trace viewer"; secondary: true; enabled: root.selectedJob !== ""; onClicked: operationsBridge.openResultFile(root.selectedJob, "trace") }
                PrimaryButton { text: "Retry from start"; secondary: true; enabled: root.selectedJob !== ""; onClicked: confirmation.ask("Repeat the entire scenario on this profile? Previously completed actions, payments or submissions may run again. Review the error and artifacts first.", function() { operationsBridge.retry(root.selectedJob) }, "Retry") }
            }
            Text { Layout.fillWidth: true; text: "Artifacts may contain signed-in pages and sensitive data. Open trace.zip with the local Playwright trace viewer; do not upload it to untrusted services."; color: Theme.muted; wrapMode: Text.WordWrap }
            ScrollView {
                Layout.fillWidth: true; Layout.preferredHeight: 250
                TextArea { text: operationsBridge.details; readOnly: true; selectByMouse: true; color: Theme.text; wrapMode: TextEdit.Wrap }
            }
        }
    }
}
