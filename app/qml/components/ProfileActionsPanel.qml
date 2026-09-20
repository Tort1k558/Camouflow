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
    property string mode: "bulk"
    ConfirmDialog { id: confirmation; width: Math.min(460, root.width - 32) }
    FolderDialog {
        id: bulkExportDialog
        onAccepted: operationsBridge.exportSelected(bulkNames.text, selectedFolder.toString())
    }
    FileDialog {
        id: exportDialog
        fileMode: FileDialog.SaveFile
        nameFilters: ["CamouFlow archive (*.zip)"]
        defaultSuffix: "zip"
        onAccepted: operationsBridge.exportBackup(backupName.text, selectedFile.toString(), sessions.checked, secrets.checked)
    }
    FileDialog {
        id: restoreDialog
        fileMode: FileDialog.OpenFile
        nameFilters: ["CamouFlow archive (*.zip)"]
        onAccepted: operationsBridge.restoreBackup(selectedFile.toString(), restoreName.text, restoreScenarios.checked)
    }
    ColumnLayout {
        id: body
        x: 24; y: 20; width: parent.width - 48; spacing: 16
        ColumnLayout {
            visible: root.mode === "bulk"; Layout.fillWidth: true; spacing: 12
            Text { text: "Local profiles only. Stop their browsers first. Preview is required; changed profiles invalidate the preview."; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            MultiField { id: bulkNames; text: operationsBridge.selectedProfiles; Layout.fillWidth: true; label: "Profile names — one per line"; fieldHeight: 90 }
            ComboBox { id: bulkAction; model: ["Replace tag", "Assign proxy URL", "Replace engine settings JSON"] }
            MultiField { id: bulkValue; Layout.fillWidth: true; label: bulkAction.currentIndex === 2 ? 'Value: {"engine":"camoufox","settings":{...}}' : "New value"; fieldHeight: 110 }
            RowLayout {
                PrimaryButton { text: "Preview changes"; enabled: !operationsBridge.busy; onClicked: operationsBridge.previewBulk(bulkNames.text, ["tag", "proxy", "settings"][bulkAction.currentIndex], bulkValue.text) }
                PrimaryButton { text: "Apply preview"; enabled: !operationsBridge.busy; onClicked: confirmation.ask("Apply the previewed changes to all selected local profiles?", function() { operationsBridge.applyBulk() }, "Apply changes") }
                PrimaryButton { text: "Export selected…"; secondary: true; enabled: !operationsBridge.busy; onClicked: bulkExportDialog.open() }
            }
            Text { Layout.fillWidth: true; text: "Bulk export saves identity metadata without secrets or browser sessions. Use Backup & restore for full profile archives."; wrapMode: Text.WordWrap; color: Theme.muted }
            ScrollView { Layout.fillWidth: true; Layout.preferredHeight: 300; TextArea { text: operationsBridge.preview; readOnly: true; color: Theme.text; wrapMode: TextEdit.Wrap } }
        }
        ColumnLayout {
            visible: root.mode !== "bulk"; Layout.fillWidth: true; spacing: 16
            Text { Layout.fillWidth: true; text: "Local archives are not encrypted. Browser session files can contain passwords and cookies regardless of metadata settings. Close the browser before export. Restored browser sessions may remain machine-bound."; color: Theme.muted; wrapMode: Text.WordWrap }
            FormField { visible: root.mode === "backup"; id: backupName; text: operationsBridge.selectedProfiles.split("\n")[0] || ""; Layout.fillWidth: true; label: "Local profile to export" }
            CheckBox { visible: root.mode === "backup"; id: sessions; text: "Include browser directory, cookies and sessions (sensitive)" }
            CheckBox { visible: root.mode === "backup"; id: secrets; text: "Include profile secrets, scenarios and engine defaults (sensitive)" }
            PrimaryButton { visible: root.mode === "backup"; text: "Export archive…"; enabled: !operationsBridge.busy && backupName.text.trim() !== ""; onClicked: confirmation.ask("Create an unencrypted archive with the selected data? Store it securely. Existing files are never overwritten.", function() { exportDialog.open() }, "Export") }
            CheckBox { visible: root.mode === "restore"; id: restoreScenarios; text: "Also restore archived scenarios"; checked: false }
            FormField { visible: root.mode === "restore"; id: restoreName; Layout.fillWidth: true; label: "Restore under a NEW local profile name" }
            PrimaryButton { visible: root.mode === "restore"; text: "Verify & restore archive…"; enabled: !operationsBridge.busy && restoreName.text.trim() !== ""; onClicked: restoreDialog.open() }
            Text { visible: root.mode === "restore"; Layout.fillWidth: true; text: "Restore only trusted archives: checksums detect corruption, not a malicious author. Existing profiles are never replaced. Archived defaults apply only to the restored profile. Selected scenarios are imported under new names; originals and global settings are unchanged."; color: Theme.muted; wrapMode: Text.WordWrap }
        }
    }
}
