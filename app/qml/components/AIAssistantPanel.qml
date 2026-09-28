import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

Flickable {
    id: root
    objectName: "aiAssistantPanel"
    property string sessionProblem: ""
    property int maxSteps: aiBridge ? aiBridge.defaultMaxSteps : 25
    onMaxStepsChanged: stepsField.text = String(maxSteps)
    Connections { target: profilesBridge; function onModelChanged() { root.sessionProblem = aiBridge.sessionIssue(profile.currentText) } }
    clip: true
    contentWidth: width
    contentHeight: body.implicitHeight + 48
    ScrollBar.vertical: ScrollBar {}
    ConfirmDialog { id: discardDialog; width: Math.min(460, root.width - 48) }

    ColumnLayout {
        id: body
        x: 28; y: 24; width: parent.width - 56; spacing: 16
        PageHeader { title: "AI browser task"; subtitle: "Describe a task — the agent drives the profile's browser and can save its actions as a scenario."; Layout.fillWidth: true }
        Text {
            Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.muted
            text: "Works with Camoufox and CloakBrowser profiles. The page structure (no input values) is sent to your configured AI provider; use a local Ollama endpoint for full privacy. Close the profile browser before starting. Cloud profiles are locked during the session."
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            ColumnLayout {
                Layout.preferredWidth: 220
                Text { text: "Profile"; color: Theme.muted }
                ComboBox { id: profile; onCurrentTextChanged: root.sessionProblem = aiBridge.sessionIssue(currentText); Layout.fillWidth: true; model: profilesBridge.selectionModel; textRole: "name"; enabled: !aiBridge.active && !aiBridge.hasDraft }
                Text { text: aiBridge.profileName; visible: aiBridge.active || aiBridge.hasDraft; Layout.fillWidth: true; Layout.preferredHeight: 38; color: Theme.text; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
            }
            ColumnLayout {
                Layout.preferredWidth: 130
                Text { text: "Max steps"; color: Theme.muted }
                FormField { id: stepsField; Layout.fillWidth: true; text: String(root.maxSteps) }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 6
            Text { text: "Task"; color: Theme.muted }
            ScrollView {
                Layout.fillWidth: true; Layout.preferredHeight: 84
                TextArea {
                    id: taskInput
                    wrapMode: TextEdit.Wrap; font.pixelSize: 13; color: Theme.text
                    background: Rectangle { radius: 10; color: Theme.input; border.color: Theme.border }
                    enabled: !aiBridge.active && !aiBridge.hasDraft
                    placeholderText: "Open example.com, find the pricing section and report the Pro plan price"
                }
            }
        }
        Text { Layout.fillWidth: true; visible: !aiBridge.active && !aiBridge.hasDraft && root.sessionProblem !== ""; text: root.sessionProblem; color: Theme.warning; wrapMode: Text.WordWrap }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            PrimaryButton {
                text: aiBridge.active ? "Running…" : "Start AI task"; icon: "play"
                enabled: !aiBridge.busy && profile.currentIndex >= 0 && root.sessionProblem === "" && taskInput.text.trim() !== "" && aiBridge.configured
                onClicked: { root.maxSteps = parseInt(stepsField.text, 10) || 25; aiBridge.start(profile.currentText, taskInput.text, root.maxSteps) }
            }
            PrimaryButton { text: "Stop"; secondary: true; enabled: aiBridge.active; onClicked: aiBridge.stop() }
            Text { text: aiBridge.status; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 240
            radius: 10; color: Theme.input; border.color: Theme.border
            clip: true
            ListView {
                id: eventList
                anchors.fill: parent; anchors.margins: 8
                model: aiBridge.eventsModel
                clip: true
                ScrollBar.vertical: ScrollBar {}
                delegate: RowLayout {
                    width: eventList.width; spacing: 8
                    Text { text: model.step > 0 ? String(model.step).padStart(2, "0") : "·"; color: Theme.dim; font.family: Theme.monoFamily; font.pixelSize: 11; Layout.preferredWidth: 20 }
                    Text { text: symbolForType(model.type); color: colorForType(model.type); font.pixelSize: 12; Layout.preferredWidth: 18 }
                    Text { text: model.text || model.action; color: model.type === "error" ? Theme.warning : Theme.text; font.pixelSize: 12; wrapMode: Text.NoWrap; elide: Text.ElideRight; Layout.fillWidth: true }
                    function symbolForType(t) { return t === "thought" ? "◈" : t === "action" ? "▶" : t === "error" ? "✕" : t === "done" ? "✓" : "·" }
                    function colorForType(t) { return t === "thought" ? Theme.muted : t === "error" ? Theme.warning : t === "done" ? Theme.primary : Theme.dim }
                }
                onCountChanged: { if (count > 0) positionViewAtIndex(count - 1, ListView.End) }
            }
            Text { anchors.centerIn: parent; visible: eventList.count === 0; text: aiBridge.active ? "Waiting for the first step…" : "Session log will appear here"; color: Theme.dim }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 6; visible: aiBridge.resultText !== ""
            Text { text: "Result"; color: Theme.muted }
            ScrollView {
                Layout.fillWidth: true; Layout.preferredHeight: 72
                TextArea { text: aiBridge.resultText; readOnly: true; wrapMode: TextEdit.Wrap; font.pixelSize: 12; color: Theme.text; background: Rectangle { radius: 10; color: Theme.subtle; border.color: Theme.border } }
            }
            Text { visible: aiBridge.artifactsDir !== ""; text: "Transcript: " + aiBridge.artifactsDir; color: Theme.dim; font.pixelSize: 11; elide: Text.ElideMiddle; Layout.fillWidth: true }
        }
        RowLayout {
            Layout.fillWidth: true
            FormField { id: draftName; Layout.fillWidth: true; label: "Save as scenario"; placeholder: "My AI workflow"; enabled: !aiBridge.busy && aiBridge.hasDraft }
            PrimaryButton { text: "Save & edit"; icon: "save"; enabled: !aiBridge.busy && aiBridge.hasDraft && draftName.text.trim() !== "" && scenariosBridge.canManage; onClicked: aiBridge.save(draftName.text) }
            PrimaryButton { text: "Discard"; danger: true; enabled: !aiBridge.busy && aiBridge.hasDraft; onClicked: discardDialog.ask("Discard this AI session draft?", function() { aiBridge.discard() }, "Discard") }
        }
        Text {
            Layout.fillWidth: true; visible: aiBridge.hasDraft; wrapMode: Text.WordWrap; color: Theme.muted; font.pixelSize: 11
            text: "The draft contains the agent's actions as replayable steps. Password typing is stored as recorded_secret_N profile variables — review everything in the editor before replay."
        }
    }
}
