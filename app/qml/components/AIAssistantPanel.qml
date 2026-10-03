import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

Item {
    id: root
    objectName: "aiAssistantPanel"
    property string sessionProblem: ""
    property string demoProfileName: ""
    property bool historyOpen: width >= 1100
    property bool optionsOpen: false
    property bool logOpen: false
    property int maxSteps: aiBridge.defaultMaxSteps
    property bool wasActive: aiBridge.active
    property bool wasWaiting: aiBridge.waiting
    readonly property bool showingSession: aiBridge.active || aiBridge.task !== ""
    readonly property bool finished: showingSession && !aiBridge.active
    readonly property bool succeeded: aiBridge.outcome === "success" || aiBridge.outcome === "done"
    readonly property string phaseLabel: aiBridge.verifying ? "Checking replay" : aiBridge.waiting ? "Needs your approval" : aiBridge.paused ? "Paused" : aiBridge.active ? "Working" : succeeded ? "Completed" : aiBridge.outcome === "stopped" ? "Stopped" : aiBridge.outcome === "partial" ? "Partial result" : "Not completed"

    function ensureProfileSelection() {
        if (demoProfileName) {
            for (let i = 0; i < profile.count; i++) {
                if (profile.textAt(i) === demoProfileName) {
                    profile.currentIndex = i
                    demoProfileName = ""
                    break
                }
            }
        }
        if (profile.currentIndex < 0 && profile.count > 0) profile.currentIndex = 0
        sessionProblem = aiBridge.sessionIssue(profile.currentText)
    }
    function startTask() {
        if (!startButton.enabled) return
        root.maxSteps = Number(stepsField.text)
        aiBridge.configureTask(startUrl.text, stayOnHost.checked, localFiles.checked, reviewActions.checked)
        aiBridge.start(profile.currentText, taskInput.text, root.maxSteps)
    }
    function resetTask() {
        aiBridge.discard()
        taskInput.text = ""
        root.logOpen = false
        taskScroll.contentY = 0
        taskInput.forceActiveFocus()
    }
    Connections { target: profilesBridge; function onModelChanged() { Qt.callLater(root.ensureProfileSelection) } }
    Connections {
        target: aiBridge
        function onChanged() {
            root.sessionProblem = aiBridge.sessionIssue(profile.currentText)
            if (!aiBridge.waiting) response.text = ""
            if ((aiBridge.waiting && !root.wasWaiting) || (!aiBridge.active && root.wasActive)) taskScroll.contentY = 0
            root.wasWaiting = aiBridge.waiting
            root.wasActive = aiBridge.active
        }
        function onDemoPrepared(name, url, task) {
            root.demoProfileName = name
            startUrl.text = url
            taskInput.text = task
            root.ensureProfileSelection()
            taskInput.forceActiveFocus()
        }
    }
    AIWorkflowDialog { id: workflowDialog }
    ConfirmDialog { id: discardDialog }

    ColumnLayout {
        anchors.fill: parent; anchors.margins: 28; spacing: 22
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            Rectangle {
                width: 42; height: 42; radius: 12; color: Theme.selection
                LineIcon { anchors.centerIn: parent; name: "zap"; color: Theme.primaryInk; size: 23 }
            }
            ColumnLayout {
                Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 3
                Text { text: "AI workspace"; color: Theme.text; font.pixelSize: 25; font.weight: Font.DemiBold }
                Text { Layout.fillWidth: true; text: "Describe a task. Review the result. Reuse the workflow."; color: Theme.muted; font.pixelSize: 12; elide: Text.ElideRight }
            }
            Rectangle {
                implicitWidth: providerLabel.implicitWidth + 28; implicitHeight: 30; radius: 15
                color: aiBridge.configured ? Theme.subtle : Theme.dangerSurface
                Text { id: providerLabel; anchors.centerIn: parent; text: aiBridge.configured ? "AI ready" : "AI not configured"; color: aiBridge.configured ? Theme.success : Theme.danger; font.pixelSize: 11 }
            }
            PrimaryButton { text: "Settings"; icon: "settings"; secondary: true; onClicked: appState.setPage("Settings") }
            PrimaryButton { objectName: "aiHistoryToggle"; text: "History"; icon: "logs"; secondary: !root.historyOpen; onClicked: root.historyOpen = !root.historyOpen }
            PrimaryButton {
                objectName: "aiNewTask"; text: "New task"; icon: "plus"; secondary: true; visible: root.finished; enabled: !aiBridge.busy
                onClicked: {
                    if (aiBridge.hasDraft) discardDialog.ask("Start a new task without saving this draft? Exported files and run history are kept.", root.resetTask, "New task")
                    else root.resetTask()
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 22
            Flickable {
                id: taskScroll; objectName: "aiTaskScroll"
                Layout.fillWidth: true; Layout.fillHeight: true
                clip: true; contentWidth: width; contentHeight: content.implicitHeight + 16
                boundsBehavior: Flickable.StopAtBounds; ScrollBar.vertical: ScrollBar {}
                ColumnLayout {
                    id: content; width: taskScroll.width; spacing: 18
                    GlassCard {
                        Layout.fillWidth: true; implicitHeight: composer.implicitHeight + 48; padding: 24; visible: !root.showingSession
                        ColumnLayout {
                            id: composer; anchors.left: parent.left; anchors.right: parent.right; spacing: 18
                            Text { text: "What would you like to do?"; color: Theme.text; font.pixelSize: 21; font.weight: Font.DemiBold }
                            ScrollView {
                                Layout.fillWidth: true; Layout.preferredHeight: 124
                                TextArea {
                                    id: taskInput; objectName: "aiTaskInput"; text: aiBridge.task
                                    wrapMode: TextEdit.Wrap; selectByMouse: true; font.pixelSize: 15; color: Theme.text
                                    placeholderText: "Extract products and prices from a catalog, or summarize a page…"
                                    padding: 14
                                    background: Rectangle { radius: Theme.radius; color: Theme.input; border.color: taskInput.activeFocus ? Theme.primaryInk : Theme.border }
                                    Keys.onPressed: function(event) {
                                        if ((event.modifiers & Qt.ControlModifier) && (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)) { root.startTask(); event.accepted = true }
                                    }
                                }
                            }
                            GridLayout {
                                Layout.fillWidth: true; columns: root.historyOpen ? 1 : 2; columnSpacing: 16; rowSpacing: 12
                                FormField { id: startUrl; objectName: "aiStartUrl"; Layout.fillWidth: true; label: "Starting URL"; placeholder: "https://example.com/catalog"; text: aiBridge.startingUrl }
                                ColumnLayout {
                                    Layout.fillWidth: true; spacing: 7
                                    Text { text: "Browser profile"; color: Theme.dim; font.pixelSize: 11; font.bold: true }
                                    ComboBox {
                                        id: profile; objectName: "aiProfileSelector"; Layout.fillWidth: true; Layout.preferredHeight: 40
                                        model: profilesBridge.selectionModel; textRole: "name"
                                        onCountChanged: Qt.callLater(root.ensureProfileSelection)
                                        onCurrentIndexChanged: Qt.callLater(root.ensureProfileSelection)
                                        onCurrentTextChanged: root.sessionProblem = aiBridge.sessionIssue(currentText)
                                    }
                                }
                            }
                            RowLayout {
                                Layout.fillWidth: true; spacing: 8
                                LineIcon { name: "check"; color: reviewActions.checked ? Theme.success : Theme.warning; size: 16 }
                                Text { Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 11; text: (reviewActions.checked ? "Changes require approval" : "Changes run without approval") + (stayOnHost.checked ? " · Starting host only" : " · Other hosts allowed") + (localFiles.checked ? " · Local files allowed" : ""); color: reviewActions.checked && !localFiles.checked ? Theme.muted : Theme.warning }
                                PrimaryButton { objectName: "aiOptionsToggle"; text: root.optionsOpen ? "Hide options" : "Options"; secondary: true; onClicked: root.optionsOpen = !root.optionsOpen }
                            }
                            ColumnLayout {
                                visible: root.optionsOpen; Layout.fillWidth: true; spacing: 8
                                CheckBox { id: stayOnHost; objectName: "aiStayOnHost"; text: "Stay on the starting host"; checked: true }
                                CheckBox { id: reviewActions; objectName: "aiConfirmActions"; text: "Ask before changing the page"; checked: true }
                                CheckBox { id: localFiles; text: "Allow access to local files"; checked: false }
                                FormField { id: stepsField; Layout.fillWidth: true; label: "Maximum steps (5–100)"; text: String(root.maxSteps); validator: IntValidator { bottom: 5; top: 100 } }
                                Text { Layout.fillWidth: true; text: "Close the profile browser before starting. Cloud profiles are locked during the session."; color: Theme.muted; font.pixelSize: 11; wrapMode: Text.WordWrap }
                            }
                            Text { Layout.fillWidth: true; wrapMode: Text.WordWrap; font.pixelSize: 12; color: Theme.warning; visible: root.sessionProblem !== ""; text: root.sessionProblem }
                            RowLayout {
                                Layout.fillWidth: true
                                PrimaryButton {
                                    id: startButton; objectName: "aiStartButton"; text: "Start task"; icon: "play"
                                    enabled: !aiBridge.busy && !aiBridge.hasDraft && aiBridge.configured && profile.currentIndex >= 0 && root.sessionProblem === "" && taskInput.text.trim().length > 0 && taskInput.text.length <= 4000 && (!stayOnHost.checked || startUrl.text.trim() !== "") && Number(stepsField.text) >= 5 && Number(stepsField.text) <= 100
                                    onClicked: root.startTask()
                                }
                                Text { text: "Ctrl + Enter"; color: Theme.dim; font.pixelSize: 11 }
                                Item { Layout.fillWidth: true }
                                Text { text: taskInput.text.length + " / 4000"; color: taskInput.text.length > 4000 ? Theme.danger : Theme.dim; font.pixelSize: 11 }
                            }
                            Text { Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.dim; font.pixelSize: 11; text: "Page text, URLs, outputs and your answers are sent to the configured provider. Editable field contents are excluded. Never enter credentials in instructions or answers. API requests may be billed." }
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true; spacing: 10; visible: !root.showingSession
                        RowLayout {
                            Layout.fillWidth: true
                            Text { text: "Not sure where to start?"; color: Theme.muted; font.pixelSize: 12 }
                            Item { Layout.fillWidth: true }
                            PrimaryButton { objectName: "aiDemoButton"; text: "Try a demo"; icon: "play"; secondary: true; enabled: !aiBridge.busy && !appState.cloudEnabled; onClicked: aiBridge.prepareDemo() }
                        }
                        GridLayout {
                            Layout.fillWidth: true; columns: 3; columnSpacing: 10
                            Repeater {
                                model: [{key: "catalog", title: "Catalog to data", description: "Products → JSON", icon: "globe"}, {key: "report", title: "Page report", description: "Page → text", icon: "logs"}, {key: "form", title: "Form preview", description: "Fill without submitting", icon: "user"}]
                                delegate: Button {
                                    required property var modelData
                                    Layout.fillWidth: true; Layout.minimumWidth: 0; implicitHeight: 84
                                    enabled: !aiBridge.busy && !appState.cloudEnabled
                                    Accessible.name: modelData.title + ". Install starter in the scenario editor"
                                    background: Rectangle { radius: Theme.radius; color: parent.hovered ? Theme.subtle : Theme.card; border.color: parent.visualFocus ? Theme.primaryInk : Theme.border }
                                    contentItem: ColumnLayout {
                                        spacing: 6
                                        RowLayout {
                                            LineIcon { name: modelData.icon; size: 16 }
                                            Text { Layout.fillWidth: true; text: modelData.title; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight }
                                        }
                                        Text { Layout.fillWidth: true; text: modelData.description; color: Theme.dim; font.pixelSize: 11; elide: Text.ElideRight }
                                    }
                                    onClicked: aiBridge.installTemplate(modelData.key)
                                    ToolTip.visible: hovered; ToolTip.text: "Install a starter in the scenario editor"; ToolTip.delay: 600
                                }
                            }
                        }
                        Text { Layout.fillWidth: true; visible: appState.cloudEnabled; text: "Demo and starters are available in a local workspace."; color: Theme.dim; font.pixelSize: 11 }
                    }
                    GlassCard {
                        Layout.fillWidth: true; implicitHeight: sessionSummary.implicitHeight + 40; visible: root.showingSession
                        ColumnLayout {
                            id: sessionSummary; anchors.left: parent.left; anchors.right: parent.right; spacing: 12
                            RowLayout {
                                Layout.fillWidth: true; spacing: 10
                                BusyIndicator { implicitWidth: 24; implicitHeight: 24; running: aiBridge.active && !aiBridge.paused && !aiBridge.waiting; visible: aiBridge.active }
                                LineIcon { visible: !aiBridge.active; name: root.succeeded ? "check" : "stop"; color: root.succeeded ? Theme.success : Theme.warning; size: 22 }
                                Text { Layout.fillWidth: true; text: root.phaseLabel; color: Theme.text; font.pixelSize: 19; font.weight: Font.DemiBold }
                                PrimaryButton { objectName: "aiPauseButton"; visible: aiBridge.active && !aiBridge.verifying; text: aiBridge.paused ? "Resume" : "Pause"; secondary: true; enabled: !aiBridge.waiting; onClicked: aiBridge.togglePause() }
                                PrimaryButton { objectName: "aiStopButton"; visible: aiBridge.active; text: "Stop"; icon: "stop"; secondary: true; onClicked: aiBridge.stop() }
                            }
                            Text { Layout.fillWidth: true; text: aiBridge.task; textFormat: Text.PlainText; color: Theme.text; font.pixelSize: 13; wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight }
                            Text { text: "Profile: " + aiBridge.profileName; color: Theme.dim; font.pixelSize: 11 }
                            Text { Layout.fillWidth: true; text: aiBridge.status; color: root.finished && !root.succeeded ? Theme.warning : Theme.muted; wrapMode: Text.WordWrap; font.pixelSize: 12 }
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true; implicitHeight: approval.implicitHeight + 40; radius: Theme.radius; color: Theme.selection; border.color: Theme.primaryInk; visible: aiBridge.waiting
                        ColumnLayout {
                            id: approval; anchors.left: parent.left; anchors.right: parent.right; anchors.margins: 20; y: 20; spacing: 12
                            Text { text: "Your decision is needed"; color: Theme.text; font.pixelSize: 18; font.weight: Font.DemiBold }
                            Text { Layout.fillWidth: true; text: aiBridge.question; textFormat: Text.PlainText; color: Theme.text; wrapMode: Text.WordWrap; font.pixelSize: 13 }
                            FormField { id: response; objectName: "aiApprovalResponse"; Layout.fillWidth: true; label: "Answer or note (sent to the provider — no credentials)"; placeholder: "Optional for action approval" }
                            RowLayout {
                                PrimaryButton { objectName: "aiApproveButton"; text: "Approve & continue"; icon: "check"; onClicked: { aiBridge.respond(response.text); response.text = "" } }
                                PrimaryButton { objectName: "aiDeclineButton"; text: "Decline & stop"; secondary: true; onClicked: aiBridge.stop() }
                            }
                        }
                    }
                    AIResultPanel { Layout.fillWidth: true; visible: root.finished && aiBridge.resultText !== "" }
                    GlassCard {
                        Layout.fillWidth: true; implicitHeight: reuse.implicitHeight + 40; visible: root.finished && aiBridge.hasDraft
                        RowLayout {
                            id: reuse; anchors.left: parent.left; anchors.right: parent.right; spacing: 16
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 6
                                Text { text: "Make this task reusable"; color: Theme.text; font.pixelSize: 17; font.weight: Font.DemiBold }
                                Text { Layout.fillWidth: true; text: "Set inputs, check a read-only replay, then save in the editor."; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap }
                            }
                            PrimaryButton { objectName: "aiCreateWorkflow"; text: "Create scenario"; icon: "workflow"; enabled: !aiBridge.busy; onClicked: workflowDialog.open() }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true; visible: root.showingSession || aiBridge.artifactsDir !== ""
                        PrimaryButton { objectName: "aiLogToggle"; text: root.logOpen ? "Hide activity" : "Activity & details"; icon: "logs"; secondary: true; onClicked: root.logOpen = !root.logOpen }
                        Item { Layout.fillWidth: true }
                    }
                    ColumnLayout {
                        visible: root.logOpen; Layout.fillWidth: true; spacing: 10
                        Rectangle {
                            Layout.fillWidth: true; Layout.preferredHeight: 250; radius: Theme.radius; color: Theme.input; border.color: Theme.border; clip: true
                            ListView {
                                id: eventList; anchors.fill: parent; anchors.margins: 12; model: aiBridge.eventsModel; clip: true; spacing: 10
                                ScrollBar.vertical: ScrollBar {}
                                delegate: RowLayout {
                                    width: eventList.width; spacing: 10
                                    Text { text: model.step > 0 ? String(model.step).padStart(2, "0") : "·"; color: Theme.dim; font.family: Theme.monoFamily; font.pixelSize: 11; Layout.preferredWidth: 24; Layout.alignment: Qt.AlignTop }
                                    Text { Layout.fillWidth: true; text: model.text || model.action; textFormat: Text.PlainText; color: model.type === "error" ? Theme.warning : Theme.text; font.pixelSize: 12; wrapMode: Text.WordWrap }
                                }
                                onCountChanged: if (count > 0 && atYEnd) positionViewAtEnd()
                            }
                            Text { anchors.centerIn: parent; visible: eventList.count === 0; text: "Activity will appear here"; color: Theme.dim; font.pixelSize: 12 }
                        }
                        Text { Layout.fillWidth: true; text: aiBridge.usageText; color: Theme.dim; font.pixelSize: 11; wrapMode: Text.WordWrap }
                        PrimaryButton { text: "Open local files"; icon: "folder"; secondary: true; visible: aiBridge.artifactsDir !== ""; onClicked: aiBridge.openArtifacts() }
                    }
                }
            }
            Rectangle {
                Layout.preferredWidth: 258; Layout.fillHeight: true; visible: root.historyOpen
                color: Theme.input; border.color: Theme.border; radius: Theme.radius
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 16; spacing: 14
                    Text { text: "Recent tasks"; color: Theme.text; font.pixelSize: 16; font.weight: Font.DemiBold }
                    Text { Layout.fillWidth: true; text: "Local history for this workspace"; color: Theme.dim; font.pixelSize: 11; wrapMode: Text.WordWrap }
                    ListView {
                        id: history; objectName: "aiHistoryList"; Layout.fillWidth: true; Layout.fillHeight: true
                        model: aiBridge.historyModel; clip: true; spacing: 8; ScrollBar.vertical: ScrollBar {}
                        delegate: Button {
                            id: historyItem
                            width: history.width; implicitHeight: 102; enabled: !aiBridge.busy && !aiBridge.hasDraft
                            Accessible.name: "Open " + model.scenario
                            background: Rectangle { radius: Theme.radiusSm; color: historyItem.hovered ? Theme.selection : Theme.card; border.color: historyItem.visualFocus ? Theme.primaryInk : Theme.borderSubtle }
                            contentItem: ColumnLayout {
                                spacing: 6
                                Text { Layout.fillWidth: true; text: model.scenario; textFormat: Text.PlainText; color: Theme.text; font.pixelSize: 12; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight }
                                Text { Layout.fillWidth: true; text: model.profile; color: Theme.dim; font.pixelSize: 11; elide: Text.ElideRight }
                                Text { text: model.status; color: model.status === "success" || model.status === "done" ? Theme.success : Theme.warning; font.pixelSize: 10 }
                            }
                            onClicked: { aiBridge.loadRun(model.id); taskScroll.contentY = 0 }
                            ToolTip.visible: hovered; ToolTip.text: "Open this result"; ToolTip.delay: 600
                        }
                        Text { anchors.centerIn: parent; width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; visible: history.count === 0; text: "Your completed tasks\nwill appear here."; color: Theme.dim; font.pixelSize: 12 }
                    }
                    Text { Layout.fillWidth: true; visible: aiBridge.hasDraft; text: "Save or discard the current draft to open another task."; color: Theme.muted; font.pixelSize: 11; wrapMode: Text.WordWrap }
                }
            }
        }
    }
}
