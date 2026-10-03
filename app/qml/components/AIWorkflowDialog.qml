import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import theme 1.0

WorkspaceDialog {
    id: root
    objectName: "aiWorkflowDialog"
    title: "Create a reusable scenario"
    anchors.centerIn: Overlay.overlay
    width: Math.min(760, Overlay.overlay.width - 64)
    height: Math.min(720, Overlay.overlay.height - 64)
    padding: 24
    closePolicy: Popup.CloseOnEscape
    property bool inputsDirty: false
    ListModel { id: fields }
    function applyInputs() {
        const values = {}
        for (let i = 0; i < fields.count; i++) {
            const item = fields.get(i)
            const name = item.fieldName.trim()
            if (!name || Object.prototype.hasOwnProperty.call(values, name)) { appState.notify("Use a unique name for every input."); return false }
            values[name] = item.fieldValue
        }
        if (!aiBridge.setInputs(JSON.stringify(values))) return false
        root.inputsDirty = false
        return true
    }
    onOpened: {
        fields.clear()
        for (let item of aiBridge.inputFields) fields.append({fieldName: item.name, fieldValue: String(item.value)})
        root.inputsDirty = false
        draftName.text = ""
    }
    Connections { target: aiBridge; function onChanged() { if (!aiBridge.hasDraft && !aiBridge.busy) root.close() } }
    header: Item {
        implicitHeight: 64
        Text { anchors.left: parent.left; anchors.leftMargin: 24; anchors.verticalCenter: parent.verticalCenter; text: root.title; color: Theme.text; font.pixelSize: 20; font.weight: Font.DemiBold }
    }
    FileDialog { id: shareDialog; title: "Share workflow"; fileMode: FileDialog.SaveFile; nameFilters: ["JSON (*.json)"]; onAccepted: aiBridge.exportWorkflow(selectedFile.toString()) }
    contentItem: Flickable {
        id: scroll
        clip: true; contentWidth: width; contentHeight: content.implicitHeight
        boundsBehavior: Flickable.StopAtBounds; ScrollBar.vertical: ScrollBar {}
        ColumnLayout {
            id: content; width: scroll.width; spacing: 18
            Text { text: "1. Inputs"; color: Theme.text; font.pixelSize: 17; font.weight: Font.DemiBold }
            Text { Layout.fillWidth: true; text: "Optional. Name an exact URL or value used in this task to replace it with a profile variable. Add these variables to the profile before future runs."; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap }
            Repeater {
                model: fields
                delegate: RowLayout {
                    required property int index
                    required property string fieldName
                    required property string fieldValue
                    Layout.fillWidth: true; spacing: 10
                    FormField { objectName: "aiInputName"; Layout.preferredWidth: 190; Layout.minimumWidth: 140; label: "Variable name"; placeholder: "catalog_url"; text: fieldName; enabled: !aiBridge.busy; onTextChanged: { fields.setProperty(index, "fieldName", text); root.inputsDirty = true } }
                    FormField { objectName: "aiInputValue"; Layout.fillWidth: true; label: "Exact value used in this task"; placeholder: "https://example.com/catalog"; text: fieldValue; enabled: !aiBridge.busy; onTextChanged: { fields.setProperty(index, "fieldValue", text); root.inputsDirty = true } }
                    PrimaryButton { text: "Remove"; icon: "close"; iconOnly: true; secondary: true; Layout.alignment: Qt.AlignBottom; enabled: !aiBridge.busy; onClicked: { fields.remove(index); root.inputsDirty = true } }
                }
            }
            RowLayout {
                PrimaryButton { objectName: "aiAddInput"; text: "Add input"; icon: "plus"; secondary: true; enabled: !aiBridge.busy; onClicked: { fields.append({fieldName: "", fieldValue: ""}); root.inputsDirty = true } }
                PrimaryButton { text: "Apply inputs"; secondary: true; enabled: !aiBridge.busy && root.inputsDirty; onClicked: root.applyInputs() }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderSubtle }
            Text { text: "2. Check replay"; color: Theme.text; font.pixelSize: 17; font.weight: Font.DemiBold }
            Text { Layout.fillWidth: true; text: "Replays read-only steps in the original profile and checks output schemas. No model requests. Interactive drafts must be reviewed in the editor and run manually."; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap }
            RowLayout {
                PrimaryButton { objectName: "aiVerifyWorkflow"; text: aiBridge.verifying ? "Checking…" : "Check read-only replay"; icon: "refresh"; secondary: true; enabled: !aiBridge.busy && aiBridge.canCheckReplay; onClicked: { if (!root.inputsDirty || root.applyInputs()) aiBridge.verifyDraft() } }
                Text { Layout.fillWidth: true; text: !aiBridge.canCheckReplay ? "Requires extracted data and read-only steps" : root.inputsDirty ? "Inputs changed — apply and recheck" : aiBridge.workflowStatus; color: aiBridge.replayChecked && !root.inputsDirty ? Theme.success : Theme.muted; font.pixelSize: 11; wrapMode: Text.WordWrap }
            }
            Text { visible: aiBridge.verifying; Layout.fillWidth: true; text: "Checking the workflow in a browser. You can close this dialog without stopping the check."; color: Theme.muted; font.pixelSize: 11; wrapMode: Text.WordWrap }
            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.borderSubtle }
            Text { text: "3. Save in the editor"; color: Theme.text; font.pixelSize: 17; font.weight: Font.DemiBold }
            FormField { id: draftName; objectName: "aiScenarioName"; Layout.fillWidth: true; label: "Scenario name"; placeholder: "My catalog workflow"; enabled: !aiBridge.busy }
            Text { Layout.fillWidth: true; text: "Review selectors and actions before running. Password fields remain required profile variables. Saving does not run the scenario."; color: Theme.dim; font.pixelSize: 11; wrapMode: Text.WordWrap }
        }
    }
    footer: Item {
        implicitHeight: 78
        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 24; anchors.rightMargin: 24; anchors.bottomMargin: 24; spacing: 10
            PrimaryButton { text: "Share workflow"; icon: "link"; secondary: true; enabled: !aiBridge.busy && aiBridge.hasDraft; onClicked: { if (!root.inputsDirty || root.applyInputs()) shareDialog.open() } }
            Item { Layout.fillWidth: true }
            PrimaryButton { text: "Close"; secondary: true; onClicked: root.close() }
            PrimaryButton { objectName: "aiSaveWorkflow"; text: "Save & open editor"; icon: "save"; enabled: !aiBridge.busy && aiBridge.hasDraft && draftName.text.trim() !== "" && draftName.text.trim().length <= 100 && scenariosBridge.canManage; onClicked: { if (!root.inputsDirty || root.applyInputs()) aiBridge.save(draftName.text) } }
        }
    }
}
