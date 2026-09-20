import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

Flickable {
    id: root
    objectName: "scenarioRecorderPanel"
    property string recordingProblem: "Choose a profile"
    Connections { target: profilesBridge; function onModelChanged() { root.recordingProblem = recorderBridge.recordingIssue(profile.currentText) } }
    clip: true
    contentWidth: width
    contentHeight: body.implicitHeight + 48
    ScrollBar.vertical: ScrollBar {}
    ConfirmDialog { id: discardDialog; width: Math.min(460, root.width - 48) }
    ColumnLayout {
        id: body
        x: 28; y: 24; width: parent.width - 56; spacing: 16
        PageHeader { title: "Record a scenario"; subtitle: "Perform actions in the browser, then review them in the editor."; Layout.fillWidth: true }
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
        ScrollView {
            Layout.fillWidth: true; Layout.preferredHeight: 270
            TextArea { text: recorderBridge.preview; readOnly: true; selectByMouse: true; font.family: Theme.monoFamily; font.pixelSize: 12; color: Theme.text; wrapMode: TextEdit.Wrap }
        }
        RowLayout {
            Layout.fillWidth: true
            FormField { id: recordingName; Layout.fillWidth: true; label: "New scenario name"; placeholder: "My recorded workflow" }
            PrimaryButton { text: "Save & edit"; icon: "save"; enabled: !recorderBridge.active && !recorderBridge.saving && recorderBridge.hasDraft && recordingName.text.trim() !== "" && scenariosBridge.canManage; onClicked: recorderBridge.save(recordingName.text) }
            PrimaryButton { text: "Discard"; danger: true; enabled: !recorderBridge.active && !recorderBridge.saving && recorderBridge.hasDraft; onClicked: discardDialog.ask("Discard this unsaved recording?", function() { recorderBridge.discard() }, "Discard") }
        }
    }
}
