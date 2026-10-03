import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

Flickable {
    id: root
    objectName: "scenarioRecorderPanel"
    property string recordingProblem: "Choose a profile"
    property string candidateSignature: ""
    function syncCandidates() {
        if (recorderBridge.active) return
        var signature = JSON.stringify(recorderBridge.parameterCandidates)
        if (signature === candidateSignature) return
        candidateSignature = signature
        inputs.clear()
        var candidates = recorderBridge.parameterCandidates
        for (var i = 0; i < candidates.length; i++) inputs.append({value: candidates[i].value, label: candidates[i].label, name: "input_" + (i + 1), selected: false})
    }
    function selectedInputs() {
        var result = []
        for (var i = 0; i < inputs.count; i++) {
            var field = inputs.get(i)
            if (field.selected) result.push({name: field.name, label: field.label, value: field.value})
        }
        return result
    }
    ListModel { id: inputs }
    Component.onCompleted: syncCandidates()
    Connections { target: recorderBridge; function onChanged() { root.syncCandidates() } }
    Connections { target: profilesBridge; function onModelChanged() { root.recordingProblem = recorderBridge.recordingIssue(profile.currentText) } }
    clip: true
    contentWidth: width
    contentHeight: body.implicitHeight + 48
    ScrollBar.vertical: ScrollBar {}
    ConfirmDialog { id: discardDialog; width: Math.min(460, root.width - 48) }
    ColumnLayout {
        id: body
        x: 28; y: 24; width: parent.width - 56; spacing: 16
        PageHeader { title: "Record a task"; subtitle: "1. Show the actions   →   2. Choose changing inputs   →   3. Save your task"; Layout.fillWidth: true }
        Text {
            Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.muted
            text: "Camoufox / local and cloud profiles. Cloud profiles are locked while recording. Close the profile browser before starting. This version records one tab: clicks, text, single-choice selects, checkboxes and Enter. CloakBrowser, iframes, uploads and popup actions are not supported."
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            ColumnLayout {
                Layout.preferredWidth: 220
                Text { text: "Profile"; color: Theme.muted }
                ComboBox { id: profile; onCurrentTextChanged: root.recordingProblem = recorderBridge.recordingIssue(currentText); Layout.fillWidth: true; model: profilesBridge.selectionModel; textRole: "name"; visible: !recorderBridge.active && !recorderBridge.hasDraft }
                Text { text: recorderBridge.profileName; visible: recorderBridge.active || recorderBridge.hasDraft; Layout.fillWidth: true; Layout.preferredHeight: 38; color: Theme.text; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
            }
            FormField { id: startUrl; Layout.fillWidth: true; label: "Start URL"; text: recorderBridge.startUrl; placeholder: "https://example.com"; enabled: !recorderBridge.active && !recorderBridge.hasDraft }
        }
        Text { Layout.fillWidth: true; visible: !recorderBridge.active && !recorderBridge.hasDraft && root.recordingProblem !== ""; text: root.recordingProblem; color: Theme.warning; wrapMode: Text.WordWrap }
        RowLayout {
            PrimaryButton { text: "Start recording"; icon: "play"; enabled: !recorderBridge.active && !recorderBridge.hasDraft && profile.currentIndex >= 0 && root.recordingProblem === "" && startUrl.text.trim() !== ""; onClicked: recorderBridge.start(profile.currentText, startUrl.text) }
            PrimaryButton { text: "Stop"; secondary: true; enabled: recorderBridge.active; onClicked: recorderBridge.stop() }
            Text { text: recorderBridge.status; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
        Text {
            Layout.fillWidth: true; color: Theme.muted; wrapMode: Text.WordWrap
            text: "Password fields become {{password}}; other recognized sensitive fields use recorded_secret_N profile variables. Other typed text and URLs are recorded as entered: review them before sharing. Cloud saves require manager access. Stopping closes the recording browser. Unsaved drafts remain only until the application exits."
        }
        Text { Layout.fillWidth: true; visible: text !== ""; text: recorderBridge.warnings; color: Theme.warning; wrapMode: Text.WordWrap }
        Text { text: "Recorded actions"; color: Theme.text; font.pixelSize: 16; font.weight: Font.DemiBold; visible: recorderBridge.hasDraft }
        ListView {
            objectName: "recordedActionsList"
            Layout.fillWidth: true; Layout.preferredHeight: 230; visible: recorderBridge.hasDraft
            model: recorderBridge.recordedActions; clip: true; spacing: 6; ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                required property var modelData
                width: ListView.view.width; height: actionBody.implicitHeight + 20; radius: Theme.radiusSm; color: Theme.card; border.color: Theme.border
                ColumnLayout {
                    id: actionBody; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 10; spacing: 4
                    Text { text: modelData.number + ". " + modelData.title; color: Theme.text; font.weight: Font.DemiBold }
                    Text { Layout.fillWidth: true; text: modelData.detail; textFormat: Text.PlainText; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap }
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; visible: recorderBridge.hasDraft && !recorderBridge.active; spacing: 10
            Text { text: "What changes between runs?"; color: Theme.text; font.pixelSize: 16; font.weight: Font.DemiBold }
            Text { Layout.fillWidth: true; text: "Select values to ask for when running the task. Equal recorded values change together. Secrets stay in profile variables."; color: Theme.muted; wrapMode: Text.WordWrap }
            Repeater {
                model: inputs
                ColumnLayout {
                    required property int index
                    required property var model
                    Layout.fillWidth: true; spacing: 6
                    CheckBox { text: model.label + ": " + model.value.substring(0, 100); checked: model.selected; onClicked: inputs.setProperty(index, "selected", checked) }
                    RowLayout {
                        Layout.fillWidth: true; visible: model.selected
                        FormField { Layout.fillWidth: true; label: "Field label"; text: model.label; onTextChanged: inputs.setProperty(index, "label", text) }
                        FormField { Layout.preferredWidth: 200; visible: showDefinition.checked; label: "Variable name"; text: model.name; onTextChanged: inputs.setProperty(index, "name", text) }
                    }
                }
            }
            CheckBox { id: showDefinition; text: "Show technical definition" }
            ScrollView {
                Layout.fillWidth: true; Layout.preferredHeight: 200; visible: showDefinition.checked
                TextArea { text: recorderBridge.preview; readOnly: true; selectByMouse: true; font.family: Theme.monoFamily; font.pixelSize: 12; color: Theme.text; wrapMode: TextEdit.Wrap }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            FormField { id: recordingName; Layout.fillWidth: true; label: "Task name"; placeholder: "Download monthly report" }
            PrimaryButton { objectName: "saveRecordedTask"; text: "Save task"; icon: "save"; enabled: !recorderBridge.active && !recorderBridge.saving && recorderBridge.hasDraft && recordingName.text.trim() !== "" && scenariosBridge.canManage; onClicked: recorderBridge.saveTask(recordingName.text, root.selectedInputs()) }
            PrimaryButton { text: "Save & edit"; secondary: true; icon: "save"; enabled: !recorderBridge.active && !recorderBridge.saving && recorderBridge.hasDraft && recordingName.text.trim() !== "" && scenariosBridge.canManage; onClicked: recorderBridge.save(recordingName.text) }
            PrimaryButton { text: "Discard"; danger: true; enabled: !recorderBridge.active && !recorderBridge.saving && recorderBridge.hasDraft; onClicked: discardDialog.ask("Discard this unsaved recording?", function() { recorderBridge.discard() }, "Discard") }
        }
    }
}
