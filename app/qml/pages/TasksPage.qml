import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

Item {
    id: root
    objectName: "tasksPage"
    property string inputSignature: ""
    function syncInputs() {
        var signature = tasksBridge.selectedName + JSON.stringify(tasksBridge.inputFields)
        if (signature === inputSignature) return
        inputSignature = signature
        fields.clear()
        for (var field of tasksBridge.inputFields) fields.append(field)
    }
    Component.onCompleted: {
        if (tasksBridge.selectedName === "" && scenariosBridge.selectedName !== "") tasksBridge.select(scenariosBridge.selectedName)
        syncInputs()
    }
    Connections { target: tasksBridge; function onChanged() { root.syncInputs() } }
    ListModel { id: fields }
    ConfirmDialog { id: confirmation; objectName: "taskRunConfirmation"; width: Math.min(540, root.width - 48) }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 28; spacing: 20
        RowLayout {
            Layout.fillWidth: true
            PageHeader { Layout.fillWidth: true; title: "Your tasks"; subtitle: "Choose a saved task, fill its inputs and queue it. No editor or AI request needed." }
            PrimaryButton { text: "Record a task"; icon: "plus"; onClicked: appState.setPage("ScenarioRecord") }
            PrimaryButton { text: "Runs"; secondary: true; onClicked: appState.setPage("ScenarioRuns") }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 24
            ListView {
                id: taskList
                objectName: "savedTaskList"
                Layout.preferredWidth: 380; Layout.fillHeight: true; clip: true; spacing: 10
                model: tasksBridge.model
                ScrollBar.vertical: ScrollBar {}
                EmptyState { anchors.centerIn: parent; width: parent.width - 24; visible: taskList.count === 0; title: "No saved tasks"; description: "Record your browser actions or save an AI workflow. Existing scenarios appear here too."; icon: "workflow" }
                delegate: Rectangle {
                    width: ListView.view.width; height: cardContent.implicitHeight + 32; radius: Theme.radius
                    color: tasksBridge.selectedName === model.name ? Theme.subtle : Theme.card
                    border.color: tasksBridge.selectedName === model.name ? Theme.primary : Theme.border
                    ColumnLayout {
                        id: cardContent
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 16; spacing: 8
                        Text { Layout.fillWidth: true; text: model.name; textFormat: Text.PlainText; color: Theme.text; font.pixelSize: 15; font.weight: Font.DemiBold; wrapMode: Text.WordWrap }
                        Text { Layout.fillWidth: true; text: model.steps + " steps · " + model.status + (model.profile ? " · " + model.profile : ""); textFormat: Text.PlainText; color: Theme.muted; font.pixelSize: 11; wrapMode: Text.WordWrap }
                        PrimaryButton { text: tasksBridge.selectedName === model.name ? "Selected" : "Open task"; secondary: true; onClicked: tasksBridge.select(model.name) }
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true; radius: Theme.radius; color: Theme.card; border.color: Theme.border
                EmptyState { anchors.centerIn: parent; width: Math.min(380, parent.width - 48); visible: tasksBridge.selectedName === ""; title: "Select a task"; description: "Its input form and run controls will appear here."; icon: "play" }
                ScrollView {
                    anchors.fill: parent; anchors.margins: 24; visible: tasksBridge.selectedName !== ""; clip: true
                    contentWidth: availableWidth
                    ColumnLayout {
                        width: parent.width; spacing: 18
                        Text { Layout.fillWidth: true; text: tasksBridge.selectedName; textFormat: Text.PlainText; color: Theme.text; font.pixelSize: 22; font.weight: Font.DemiBold; wrapMode: Text.WordWrap }
                        RowLayout {
                            Layout.fillWidth: true; visible: tasksBridge.lastRun.id !== ""
                            Text { Layout.fillWidth: true; text: "Last run: " + tasksBridge.lastRun.status + " · " + tasksBridge.lastRun.profile; textFormat: Text.PlainText; color: Theme.muted; wrapMode: Text.WordWrap }
                            PrimaryButton { text: "Run details"; secondary: true; onClicked: tasksBridge.inspect() }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 6
                            Text { text: "Browser profile"; color: Theme.muted; font.pixelSize: 12 }
                            ComboBox { id: profile; objectName: "taskProfileSelector"; Layout.fillWidth: true; model: profilesBridge.selectionModel; textRole: "name" }
                        }
                        Repeater {
                            model: fields
                            FormField {
                                required property int index
                                required property var model
                                objectName: "taskInput_" + model.name
                                visible: !batch.expanded
                                Layout.fillWidth: true
                                label: model.label
                                text: model.value
                                placeholder: "Required"
                                onTextChanged: fields.setProperty(index, "value", text)
                            }
                        }
                        Text { Layout.fillWidth: true; visible: fields.count === 0; text: "No changing inputs. This task uses its saved steps and profile variables."; color: Theme.muted; wrapMode: Text.WordWrap }
                        Text { Layout.fillWidth: true; text: tasksBridge.review; textFormat: Text.PlainText; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap }
                        Text { Layout.fillWidth: true; visible: tasksBridge.problem !== ""; text: tasksBridge.problem; textFormat: Text.PlainText; color: Theme.warning; wrapMode: Text.WordWrap }
                        RowLayout {
                            visible: !batch.expanded
                            PrimaryButton {
                                objectName: "queueSavedTask"
                                text: "Queue task"; icon: "play"
                                enabled: scenariosBridge.canRun && profile.currentIndex >= 0 && tasksBridge.problem === ""
                                onClicked: {
                                    var inputs = {}
                                    for (var i = 0; i < fields.count; i++) inputs[fields.get(i).name] = fields.get(i).value
                                    var selectedProfile = profile.currentText
                                    confirmation.ask("Queue “" + tasksBridge.selectedName + "” on “" + selectedProfile + "”? Website changes may be irreversible. The queue must be resumed separately; keep the application open.", function() {
                                        if (tasksBridge.run(selectedProfile, inputs)) appState.setPage("ScenarioRuns")
                                    }, "Queue task")
                                }
                            }
                            PrimaryButton { text: "Review in editor"; secondary: true; onClicked: tasksBridge.edit() }
                        }
                        TaskBatchPanel {
                            id: batch
                            visible: fields.count > 0
                            profileName: profile.currentText
                            canRun: scenariosBridge.canRun && profile.currentIndex >= 0 && tasksBridge.problem === ""
                        }
                    }
                }
            }
        }
    }
}
