import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import theme 1.0

Flickable {
    id: root
    objectName: "aiAssistantPanel"
    property string sessionProblem: ""
    property string demoProfileName: ""
    function selectDemoProfile() {
        if (!demoProfileName) return
        for (let i = 0; i < profile.count; i++) {
            if (profile.textAt(i) === demoProfileName) { profile.currentIndex = i; demoProfileName = ""; return }
        }
    }
    function ensureProfileSelection() {
        selectDemoProfile()
        if (profile.currentIndex < 0 && profile.count > 0) profile.currentIndex = 0
        sessionProblem = aiBridge.sessionIssue(profile.currentText)
    }
    property int maxSteps: aiBridge ? aiBridge.defaultMaxSteps : 25
    onMaxStepsChanged: stepsField.text = String(maxSteps)
    Connections { target: profilesBridge; function onModelChanged() { Qt.callLater(root.ensureProfileSelection) } }
    Connections { target: aiBridge; function onChanged() { root.sessionProblem = aiBridge.sessionIssue(profile.currentText); if (!aiBridge.active && aiBridge.task !== "") taskInput.text = aiBridge.task } }
    Connections {
        target: aiBridge
        function onDemoPrepared(name, url, task) { root.demoProfileName = name; startUrl.text = url; taskInput.text = task; root.selectDemoProfile() }
    }
    clip: true
    contentWidth: width
    contentHeight: body.implicitHeight + 48
    ScrollBar.vertical: ScrollBar {}
    FileDialog { id: exportDialog; title: "Export AI results"; fileMode: FileDialog.SaveFile; nameFilters: ["JSON (*.json)", "CSV (*.csv)"]; onAccepted: aiBridge.exportResults(selectedFile.toString()) }
    FileDialog { id: shareDialog; title: "Share workflow"; fileMode: FileDialog.SaveFile; nameFilters: ["JSON (*.json)"]; onAccepted: aiBridge.exportWorkflow(selectedFile.toString()) }
    ConfirmDialog { id: discardDialog; width: Math.min(460, root.width - 48) }

    ColumnLayout {
        id: body
        x: 28; y: 24; width: parent.width - 56; spacing: 16
        PageHeader { title: "AI browser task"; subtitle: "Describe a task — the agent drives the profile's browser and can save its actions as a scenario."; Layout.fillWidth: true }
        Text {
            Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.muted
            text: "Works with Camoufox and CloakBrowser profiles. The page structure (page text, URLs and labels; editable field contents are excluded) is sent to your configured AI provider; use a local Ollama endpoint to keep model requests local. Close the profile browser before starting. Cloud profiles are locked during the session."
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            PrimaryButton { text: "Configure AI"; secondary: true; onClicked: appState.setPage("Settings") }
            Text { text: aiBridge.configured ? "Provider ready" : "Set up your provider first"; color: Theme.muted; Layout.fillWidth: true }
        }
        GridLayout {
            columns: root.width > 850 ? 4 : 2
            Layout.fillWidth: true; columnSpacing: 8; rowSpacing: 8
            PrimaryButton { text: "Try isolated demo"; secondary: true; enabled: !aiBridge.busy && !aiBridge.hasDraft; onClicked: aiBridge.prepareDemo() }
            PrimaryButton { text: "Catalog starter"; secondary: true; enabled: !aiBridge.busy && !aiBridge.hasDraft; onClicked: aiBridge.installTemplate("catalog") }
            PrimaryButton { text: "Page report"; secondary: true; enabled: !aiBridge.busy && !aiBridge.hasDraft; onClicked: aiBridge.installTemplate("report") }
            PrimaryButton { text: "Form preview"; secondary: true; enabled: !aiBridge.busy && !aiBridge.hasDraft; onClicked: aiBridge.installTemplate("form") }
        }
        FormField { id: startUrl; Layout.fillWidth: true; label: "Starting URL"; placeholder: "https://example.com"; enabled: !aiBridge.busy && !aiBridge.hasDraft }
        GridLayout {
            columns: root.width > 850 ? 3 : 1
            Layout.fillWidth: true
            CheckBox { id: stayOnHost; text: "Stay on starting host"; checked: true; enabled: !aiBridge.busy }
            CheckBox { id: reviewActions; text: "Confirm browser changes"; checked: true; enabled: !aiBridge.busy }
            CheckBox { id: localFiles; text: "Allow local files"; checked: false; enabled: !aiBridge.busy }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            ColumnLayout {
                Layout.preferredWidth: 220
                Text { text: "Profile"; color: Theme.muted }
                ComboBox { id: profile; objectName: "aiProfileSelector"; onCountChanged: Qt.callLater(root.ensureProfileSelection); onCurrentIndexChanged: Qt.callLater(root.ensureProfileSelection); onCurrentTextChanged: root.sessionProblem = aiBridge.sessionIssue(currentText); Layout.fillWidth: true; model: profilesBridge.selectionModel; textRole: "name"; enabled: !aiBridge.active && !aiBridge.hasDraft }
                Text { text: aiBridge.profileName; visible: aiBridge.active || aiBridge.hasDraft; Layout.fillWidth: true; Layout.preferredHeight: 38; color: Theme.text; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
            }
            ColumnLayout {
                Layout.preferredWidth: 130
                Text { text: "Max steps"; color: Theme.muted }
                FormField { id: stepsField; Layout.fillWidth: true; text: String(root.maxSteps); enabled: !aiBridge.busy; validator: IntValidator { bottom: 5; top: 100 } }
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
                onClicked: { root.maxSteps = parseInt(stepsField.text, 10) || 25; aiBridge.configureTask(startUrl.text, stayOnHost.checked, localFiles.checked, reviewActions.checked); aiBridge.start(profile.currentText, taskInput.text, root.maxSteps) }
            }
            PrimaryButton { text: aiBridge.paused ? "Resume" : "Pause"; secondary: true; enabled: aiBridge.active && !aiBridge.waiting; onClicked: aiBridge.togglePause() }
            PrimaryButton { text: "Stop"; secondary: true; enabled: aiBridge.active; onClicked: aiBridge.stop() }
            Text { text: aiBridge.status; color: Theme.muted; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
        ColumnLayout {
            Layout.fillWidth: true; visible: aiBridge.waiting
            Text { Layout.fillWidth: true; text: aiBridge.question; color: Theme.text; wrapMode: Text.WordWrap }
            FormField { id: response; Layout.fillWidth: true; label: "Response (sent to the provider; do not enter credentials)" }
            RowLayout {
                PrimaryButton { text: "Approve / Continue"; onClicked: { aiBridge.respond(response.text); response.text = "" } }
                PrimaryButton { text: "Decline & stop"; secondary: true; onClicked: aiBridge.stop() }
            }
        }
        Text { Layout.fillWidth: true; visible: aiBridge.usageText !== ""; text: aiBridge.usageText; color: Theme.muted; font.pixelSize: 11 }
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
                    Text { text: model.text || model.action; color: model.type === "error" ? Theme.warning : Theme.text; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
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
                Layout.fillWidth: true; Layout.preferredHeight: 180
                TextArea { text: aiBridge.resultText; readOnly: true; wrapMode: TextEdit.Wrap; font.pixelSize: 12; color: Theme.text; background: Rectangle { radius: 10; color: Theme.subtle; border.color: Theme.border } }
            }
            Text { visible: aiBridge.artifactsDir !== ""; text: "Transcript: " + aiBridge.artifactsDir; color: Theme.dim; font.pixelSize: 11; elide: Text.ElideMiddle; Layout.fillWidth: true }
        }
        ColumnLayout {
            Layout.fillWidth: true; visible: aiBridge.outputsJson !== ""
            Text { text: "Extracted data and sources"; color: Theme.text }
            ScrollView {
                Layout.fillWidth: true; Layout.preferredHeight: aiBridge.tableColumns.length > 0 ? 240 : 0
                visible: aiBridge.tableColumns.length > 0
                GridLayout {
                    columns: Math.max(1, aiBridge.tableColumns.length); columnSpacing: 8; rowSpacing: 4
                    Repeater { model: aiBridge.tableColumns; delegate: Text { Layout.preferredWidth: 170; text: modelData; color: Theme.text; font.bold: true; wrapMode: Text.WordWrap } }
                    Repeater { model: aiBridge.tableCells; delegate: TextArea { Layout.preferredWidth: 170; Layout.preferredHeight: 44; text: modelData; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; color: Theme.text; background: Rectangle { color: Theme.subtle; radius: 4 } } }
                }
            }
            Text { visible: aiBridge.tableColumns.length > 0; text: "Preview: first 30 rows. Export contains all extracted rows."; color: Theme.dim; font.pixelSize: 11 }
            ScrollView { Layout.fillWidth: true; Layout.preferredHeight: 120; TextArea { text: aiBridge.outputsJson; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap; color: Theme.text } }
            PrimaryButton { text: "Export JSON / CSV"; secondary: true; onClicked: exportDialog.open() }
        }
        ColumnLayout {
            Layout.fillWidth: true; visible: aiBridge.hasDraft
            Text { text: "Repeatable workflow"; color: Theme.text }
            Text { Layout.fillWidth: true; text: "Inputs map variable names to exact values used in this task, e.g. {\"catalog_url\":\"https://example.com\"}. Configure those variables on the profile before replay."; color: Theme.muted; wrapMode: Text.WordWrap; font.pixelSize: 11 }
            ScrollView { Layout.fillWidth: true; Layout.preferredHeight: 80; TextArea { id: inputs; text: aiBridge.inputsJson; enabled: !aiBridge.busy; wrapMode: TextEdit.Wrap; color: Theme.text } }
            GridLayout {
                columns: root.width > 850 ? 3 : 1
                PrimaryButton { text: "Apply inputs"; secondary: true; enabled: !aiBridge.busy; onClicked: aiBridge.setInputs(inputs.text) }
                PrimaryButton { text: "Check read-only replay"; secondary: true; enabled: !aiBridge.busy; onClicked: aiBridge.verifyDraft() }
                PrimaryButton { text: "Share workflow"; secondary: true; enabled: !aiBridge.busy; onClicked: shareDialog.open() }
            }
            Text { text: aiBridge.workflowStatus; color: Theme.muted }
        }
        RowLayout {
            Layout.fillWidth: true
            FormField { id: draftName; Layout.fillWidth: true; label: "Save as scenario"; placeholder: "My AI workflow"; enabled: !aiBridge.busy && aiBridge.hasDraft }
            PrimaryButton { text: "Save & edit"; icon: "save"; enabled: !aiBridge.busy && aiBridge.hasDraft && draftName.text.trim() !== "" && scenariosBridge.canManage; onClicked: aiBridge.save(draftName.text) }
            PrimaryButton { text: "Discard"; danger: true; enabled: !aiBridge.busy && aiBridge.hasDraft; onClicked: discardDialog.ask("Discard this AI session draft?", function() { aiBridge.discard() }, "Discard") }
        }
        PrimaryButton { text: "Open artifacts"; secondary: true; visible: aiBridge.artifactsDir !== ""; onClicked: aiBridge.openArtifacts() }
        Text { text: "Recent AI tasks"; color: Theme.text }
        ListView {
            Layout.fillWidth: true; Layout.preferredHeight: Math.min(contentHeight, 180); clip: true
            model: aiBridge.historyModel; ScrollBar.vertical: ScrollBar {}
            delegate: RowLayout {
                width: ListView.view.width; spacing: 8
                Text { text: model.scenario + " / " + model.status; color: Theme.muted; Layout.fillWidth: true; elide: Text.ElideRight }
                PrimaryButton { text: "Open"; secondary: true; enabled: !aiBridge.busy && !aiBridge.hasDraft; onClicked: aiBridge.loadRun(model.id) }
            }
        }
        Text {
            Layout.fillWidth: true; visible: aiBridge.hasDraft; wrapMode: Text.WordWrap; color: Theme.muted; font.pixelSize: 11
            text: "The draft contains the agent's actions as replayable steps. Password typing is stored as recorded_secret_N profile variables — review everything in the editor before replay."
        }
    }
}
