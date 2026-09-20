import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import theme 1.0
import "../components"

Item {
    id: root
    anchors.fill: parent
    property string lastCanvasScenarioName: ""
    enabled: !scenariosBridge.saving
    Connections { target: scenariosBridge; function onScenarioSaved() { root.markScenarioSaved() } }
    property bool scenarioSaved: false

    function markScenarioSaved() {
        scenarioSaved = true
        savedTimer.restart()
    }

    function openVariableEditor(key) {
        var payload = key && settingsBridge ? settingsBridge.getVariable(key) : ({})
        sharedVarKey.text = payload.key || key || ""
        sharedVarType.text = payload.type || "string"
        sharedVarValue.text = payload.value || ""
    }

    ConfirmDialog { id: confirmDialog }

    function confirmDeleteStep() {
        var step = scenariosBridge.selectedStep()
        confirmDialog.ask('Delete step "' + (step.tag || step.action || "untagged") + '" from the scenario?', function() { scenariosBridge.deleteStep() })
    }

    Timer {
        id: savedTimer
        interval: 3000
        repeat: false
        onTriggered: root.scenarioSaved = false
    }

    function reloadStepEditor() {
        var step = scenariosBridge.selectedStep()
        stepTag.text = step.tag || ""
        stepAction.text = step.action || ""
        stepSelector.text = step.selector || ""
        stepSelectorType.text = step.selector_type || "css"
        stepValue.text = step.value || step.url || step.text || step.message || ""
        stepVariable.text = step.name || step.to_var || step.from_var || step.variable || ""
        stepPattern.text = step.pattern || step.targets_string || ""
        stepTimeout.text = step.timeout_ms ? String(step.timeout_ms) : "0"
        stepSeconds.text = step.seconds ? String(step.seconds) : "0"
        stepNextOk.text = step.next_success_step || ""
        stepNextErr.text = step.next_error_step || ""
        var extra = {}
        var skip = {"tag":1,"action":1,"selector":1,"selector_type":1,"value":1,"url":1,"text":1,"message":1,"name":1,"to_var":1,"from_var":1,"variable":1,"pattern":1,"targets_string":1,"timeout_ms":1,"seconds":1,"next_success_step":1,"next_error_step":1,"_pos":1}
        for (var k in step) if (!skip[k]) extra[k] = step[k]
        stepExtra.text = JSON.stringify(extra, null, 2)
    }

    Connections {
        target: scenariosBridge
        function onSelectedStepChanged() { root.reloadStepEditor() }
        function onSelectedChanged() {
            root.reloadStepEditor()
            if (root.lastCanvasScenarioName !== scenariosBridge.selectedName) {
                root.lastCanvasScenarioName = scenariosBridge.selectedName
                actionCanvas.resetView()
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 0
        spacing: 0

        Rectangle {
            Layout.preferredWidth: root.width < 1100 ? 218 : 250
            Layout.fillHeight: true
            color: Theme.elevated
            border.color: Theme.borderSubtle
            Column {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 14
                Text { text: "Current scenario"; color: Theme.text; font.pixelSize: 14; font.weight: Font.DemiBold }
                Rectangle {
                    width: parent.width
                    height: 76
                    radius: 14
                    color: Theme.selection
                    border.color: Theme.primary
                    Column {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.margins: 14
                        spacing: 4
                        Text { text: scenariosBridge.selectedName || "Select scenario"; color: Theme.text; font.pixelSize: 14; font.weight: Font.DemiBold; elide: Text.ElideRight; width: parent.width }
                        Text { text: scenariosBridge.selectedDescription || "Click to choose/create"; color: Theme.muted; font.pixelSize: 12; elide: Text.ElideRight; width: parent.width }
                    }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: scenarioDialog.open() }
                }

                Text {
                    visible: appState && appState.cloudEnabled
                    text: "Latest runs"
                    color: Theme.text
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                }
                ListView {
                    width: parent.width
                    visible: appState && appState.cloudEnabled
                    height: visible ? 132 : 0
                    model: scenariosBridge.runsModel
                    spacing: 7
                    clip: true
                    delegate: Rectangle {
                        width: ListView.view.width
                        height: 58
                        radius: 13
                        color: Theme.subtle
                        border.color: Theme.border
                        Rectangle { width: 4; height: parent.height - 18; radius: 2; anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter; color: model.accent }
                        Column {
                            anchors.left: parent.left
                            anchors.leftMargin: 20
                            anchors.right: parent.right
                            anchors.rightMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 3
                            Row {
                                width: parent.width
                                spacing: 8
                                Text { text: model.status; color: model.accent; font.pixelSize: 11; font.weight: Font.DemiBold }
                                Text { text: model.duration; color: Theme.dim; font.pixelSize: 11 }
                                Text { text: model.started; color: Theme.dim; font.pixelSize: 11; elide: Text.ElideRight; width: parent.width - 120 }
                            }
                            Text { text: model.scenario + " / " + model.profile; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight; width: parent.width }
                            Text { visible: model.error !== ""; text: model.error; color: Theme.danger; font.pixelSize: 11; elide: Text.ElideRight; width: parent.width }
                        }
                    }
                }

                Text { text: "Action Groups"; color: Theme.text; font.pixelSize: 14; font.weight: Font.DemiBold }
                ListView {
                    width: parent.width
                    height: 198
                    model: scenariosBridge.categoriesModel
                    spacing: 7
                    clip: true
                    delegate: Rectangle {
                        width: ListView.view.width
                        height: 34
                        radius: 10
                        color: model.selected ? Theme.selection : Theme.input
                        border.color: model.selected ? Theme.primary : Theme.border
                        Text { anchors.left: parent.left; anchors.leftMargin: 12; anchors.verticalCenter: parent.verticalCenter; text: model.name; color: model.selected ? Theme.primaryLight : Theme.muted; font.pixelSize: 12; font.weight: Font.DemiBold }
                        Text { anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; text: model.count; color: Theme.dim; font.pixelSize: 11 }
                        MouseArea { anchors.fill: parent; onClicked: scenariosBridge.setCategory(model.name) }
                    }
                }

                Text { text: "Action Templates"; color: Theme.text; font.pixelSize: 14; font.weight: Font.DemiBold }
                ListView {
                    width: parent.width
                    height: parent.height - y - 4
                    model: scenariosBridge.templatesModel
                    spacing: 8
                    clip: true
                    delegate: Rectangle {
                        width: ListView.view.width
                        height: 54
                        radius: 13
                        color: Theme.subtle
                        border.color: Theme.border
                        Row { anchors.fill: parent; anchors.margins: 12; spacing: 12
                            Rectangle { width: 30; height: 30; radius: 12; color: Theme.primary; Text { anchors.centerIn: parent; text: "+"; color: Theme.primaryText; font.weight: Font.DemiBold } }
                            Column { width: parent.width - 42; spacing: 2; Text { width: parent.width; elide: Text.ElideRight; text: model.title; color: Theme.text; font.weight: Font.DemiBold; font.pixelSize: 13 } Text { width: parent.width; elide: Text.ElideRight; text: model.subtitle; color: Theme.dim; font.pixelSize: 12 } }
                        }
                        MouseArea { anchors.fill: parent; enabled: scenariosBridge.canManage; onClicked: scenariosBridge.addAction(model.action) }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.background
            Column {
                anchors.fill: parent
                Rectangle {
                    width: parent.width
                    height: 96
                    color: Theme.background
                    border.color: Theme.borderSubtle
                    Text { anchors.left: parent.left; anchors.leftMargin: 22; anchors.top: parent.top; anchors.topMargin: 12; text: "Action map"; color: Theme.primaryLight; font.pixelSize: 18; font.weight: Font.DemiBold }
                    RowLayout { anchors.left: parent.left; anchors.right: parent.right; anchors.margins: 12; y: 43; spacing: 8
                        PrimaryButton { text: "Variables"; icon: "settings"; secondary: true; enabled: scenariosBridge.canManage; onClicked: { root.openVariableEditor(""); variablesDialog.open() } }
                        PrimaryButton {
                            text: root.scenarioSaved ? "Saved" : "Save"
                            icon: "save"
                            secondary: true
                            enabled: scenariosBridge.canManage
                            onClicked: {
                                scenariosBridge.saveSelected(scenarioNameEdit.text, scenarioDescEdit.text)

                            }
                        }
                        PrimaryButton { text: "Configure run"; icon: "play"; enabled: scenariosBridge.canRun && scenariosBridge.selectedName !== ""; onClicked: operationsBridge.prepareRun(operationsBridge.selectedProfiles) }

                    }
                }
                ScenarioCanvas {
                    id: actionCanvas
                    width: parent.width
                    height: parent.height - 96
                    model: scenariosBridge.stepsModel
                    onNodeSelected: function(row) { scenariosBridge.selectStep(row) }
                    onNodeMoved: function(row, x, y) { scenariosBridge.setStepPosition(row, x, y) }
                    onNodeContextRequested: function(row, x, y) {
                        scenariosBridge.selectStep(row)
                        stepMenu.popup(x, y + 96)
                    }
                    onLinkRequested: function(sourceRow, targetRow, kind) {
                        scenariosBridge.linkSteps(sourceRow, targetRow, kind)
                    }
                    onLinkContextRequested: function(sourceRow, targetRow, kind, x, y) {
                        linkMenu.sourceRow = sourceRow
                        linkMenu.targetRow = targetRow
                        linkMenu.kind = kind
                        linkMenu.popup(x, y + 96)
                    }
                    onDeleteRequested: function(row) {
                        scenariosBridge.selectStep(row)
                        root.confirmDeleteStep()
                    }
                }
            }
        }

        Rectangle {
            Layout.preferredWidth: root.width < 1100 ? 280 : 320
            Layout.fillHeight: true
            color: Theme.elevated
            border.color: Theme.borderSubtle
            Flickable {
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                anchors.fill: parent
                contentWidth: width
                contentHeight: details.height + 44
                clip: true
                Column {
                    id: details
                    width: parent.width - 36
                    x: 18
                    y: 20
                    spacing: 14
                    Text { text: "Node Properties"; color: Theme.text; font.pixelSize: 15; font.weight: Font.DemiBold }
                    Row { width: parent.width; spacing: 8
                        PrimaryButton { width: (parent.width - 8) / 2; text: "Copy"; secondary: true; enabled: scenariosBridge.canManage; onClicked: scenariosBridge.duplicateStep() }
                        PrimaryButton { width: (parent.width - 8) / 2; text: "Delete"; danger: true; enabled: scenariosBridge.canManage; onClicked: root.confirmDeleteStep() }
                    }
                    FormField { id: stepTag; width: parent.width; label: "Tag" }
                    Row { width: parent.width; spacing: 8
                        FormField { id: stepAction; width: (parent.width - 8) / 2; label: "Action" }
                        FormField { id: stepSelectorType; width: (parent.width - 8) / 2; label: "Selector type" }
                    }
                    FormField { id: stepSelector; width: parent.width; label: "Selector" }
                    FormField { id: stepValue; width: parent.width; label: "Value / URL / text" }
                    FormField { id: stepVariable; width: parent.width; label: "Variable" }
                    FormField { id: stepPattern; width: parent.width; label: "Pattern / targets" }
                    Row { width: parent.width; spacing: 8
                        FormField { id: stepTimeout; width: (parent.width - 8) / 2; label: "Timeout ms" }
                        FormField { id: stepSeconds; width: (parent.width - 8) / 2; label: "Sleep sec" }
                    }
                    Row { width: parent.width; spacing: 8
                        FormField { id: stepNextOk; width: (parent.width - 8) / 2; label: "Next success tag" }
                        FormField { id: stepNextErr; width: (parent.width - 8) / 2; label: "Next error tag" }
                    }
                    Text { text: "Extra JSON"; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold }
                    Rectangle { width: parent.width; height: 118; radius: Theme.radiusSm; color: Theme.subtle; border.color: Theme.border
                        TextArea { id: stepExtra; anchors.fill: parent; anchors.margins: 10; color: Theme.text; placeholderTextColor: Theme.dim; font.family: "Consolas"; font.pixelSize: 12; background: Item {} }
                    }
                    PrimaryButton {
                        width: parent.width
                        text: "Save Step"
                        icon: "save"
                        enabled: scenariosBridge.canManage
                        onClicked: scenariosBridge.saveStep(
                            stepTag.text,
                            stepAction.text,
                            stepSelector.text,
                            stepSelectorType.text,
                            stepValue.text,
                            stepVariable.text,
                            stepPattern.text,
                            parseInt(stepTimeout.text || "0"),
                            parseFloat(stepSeconds.text || "0"),
                            stepNextOk.text,
                            stepNextErr.text,
                            stepExtra.text
                        )
                    }
                    Text { text: "Raw step"; color: Theme.dim; font.pixelSize: 12 }
                    Rectangle { width: parent.width; height: 110; radius: Theme.radiusSm; color: Theme.background; border.color: Theme.border
                        Text { anchors.fill: parent; anchors.margins: 10; text: scenariosBridge.selectedStepJson; color: Theme.muted; font.family: "Consolas"; font.pixelSize: 11; wrapMode: Text.Wrap; elide: Text.ElideRight }
                    }
                }
            }
        }
    }

    WorkspaceDialog {
        id: variablesDialog
        objectName: "variablesDialog"
        modal: true
        width: Math.min(860, root.width - 80)
        height: Math.min(560, root.height - 80)
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: Theme.radiusLg; border.color: Theme.border }
        contentItem: Column {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 16

            RowLayout {
                width: parent.width
                height: 38
                Text { text: "Shared Variables"; color: Theme.text; font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
                PrimaryButton { Layout.preferredWidth: 104; text: "New"; icon: "plus"; enabled: scenariosBridge.canManage; onClicked: root.openVariableEditor("") }
                PrimaryButton { Layout.preferredWidth: 104; text: "Close"; secondary: true; onClicked: variablesDialog.close() }
            }

            RowLayout {
                width: parent.width
                height: parent.height - 54
                spacing: 16

                Rectangle {
                    Layout.preferredWidth: 330
                    Layout.fillHeight: true
                    radius: 14
                    color: Theme.background
                    border.color: Theme.border

                    ListView {
                        anchors.fill: parent
                        anchors.margins: 10
                        model: settingsBridge ? settingsBridge.variablesModel : null
                        spacing: 8
                        clip: true
                        delegate: Rectangle {
                            width: ListView.view.width
                            height: 54
                            radius: 12
                            color: Theme.subtle
                            border.color: Theme.border
                            Text {
                                anchors.left: parent.left
                                anchors.leftMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 92
                                text: "[" + model.type + "] " + model.key + ": " + model.value
                                color: Theme.muted
                                font.pixelSize: 12
                                elide: Text.ElideRight
                            }
                            PrimaryButton { anchors.right: delBtn.left; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter; width: 32; height: 30; text: ""; icon: "settings"; secondary: true; onClicked: root.openVariableEditor(model.key) }
                            PrimaryButton {
                                id: delBtn
                                anchors.right: parent.right
                                anchors.rightMargin: 8
                                anchors.verticalCenter: parent.verticalCenter
                                width: 32
                                height: 30
                                text: ""
                                icon: "trash"
                                danger: true
                                enabled: scenariosBridge.canManage
                                onClicked: {
                                    if (settingsBridge) settingsBridge.deleteVariable(model.key)
                                    if (sharedVarKey.text === model.key) root.openVariableEditor("")
                                }
                            }
                        }
                    }
                }

                Column {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 14

                    FormField { id: sharedVarKey; width: parent.width; label: "Key" }
                    Row {
                        width: parent.width
                        spacing: 10
                        PrimaryButton { width: (parent.width - 20) / 3; text: "string"; secondary: sharedVarType.text !== "string"; onClicked: sharedVarType.text = "string" }
                        PrimaryButton { width: (parent.width - 20) / 3; text: "number"; secondary: sharedVarType.text !== "number"; onClicked: sharedVarType.text = "number" }
                        PrimaryButton { width: (parent.width - 20) / 3; text: "list"; secondary: sharedVarType.text !== "list"; onClicked: sharedVarType.text = "list" }
                    }
                    FormField { id: sharedVarType; visible: false; text: "string" }
                    Text { text: "Value"; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold }
                    Rectangle {
                        width: parent.width
                        height: 190
                        radius: 11
                        color: Theme.subtle
                        border.color: Theme.border
                        TextArea {
                            id: sharedVarValue
                            anchors.fill: parent
                            anchors.margins: 10
                            color: Theme.text
                            placeholderText: "Value or one list item per line"
                            placeholderTextColor: Theme.dim
                            background: Item {}
                            wrapMode: TextArea.Wrap
                            font.pixelSize: 13
                        }
                    }
                    Row {
                        spacing: 10
                        PrimaryButton { width: 130; text: "Save"; icon: "save"; enabled: scenariosBridge.canManage; onClicked: if (settingsBridge) settingsBridge.saveVariable(sharedVarKey.text, sharedVarType.text, sharedVarValue.text) }
                        PrimaryButton { width: 110; text: "Clear"; secondary: true; onClicked: root.openVariableEditor("") }
                    }
                }
            }
        }
    }

    WorkspaceDialog {
        id: scenarioDialog
        objectName: "scenarioDialog"
        modal: true
        width: Math.min(760, root.width - 80)
        height: Math.min(650, root.height - 80)
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: Theme.radiusLg; border.color: Theme.border }
        contentItem: Column {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 16
            Text { text: "Scenario Library"; color: Theme.text; font.pixelSize: 24; font.weight: Font.DemiBold }
            Row {
                width: parent.width
                spacing: 12
                PrimaryButton { width: 110; text: "New"; icon: "plus"; enabled: scenariosBridge.canManage; onClicked: scenariosBridge.createScenario() }
                PrimaryButton { width: 110; text: "Duplicate"; secondary: true; enabled: scenariosBridge.canManage; onClicked: scenariosBridge.duplicateSelected() }
                PrimaryButton { width: 110; text: "Market"; icon: "globe"; secondary: true; onClicked: appState.setPage("Marketplace") }
                PrimaryButton {
                    width: 110
                    text: "Publish"
                    icon: "globe"
                    secondary: true
                    enabled: scenariosBridge.canManage
                    onClicked: {
                        publishTitle.text = scenariosBridge.selectedName
                        publishDescription.text = scenariosBridge.selectedDescription
                        publishCategory.text = "Utility"
                        publishTags.text = ""
                        publishDialog.open()
                    }
                }
                PrimaryButton { width: 100; text: "Delete"; danger: true; enabled: scenariosBridge.canAdmin; onClicked: scenariosBridge.deleteSelected() }
                PrimaryButton {
                    width: 90
                    text: root.scenarioSaved ? "Saved" : "Save"
                    icon: "save"
                    secondary: true
                    enabled: scenariosBridge.canManage
                    onClicked: {
                        scenariosBridge.saveSelected(scenarioNameEdit.text, scenarioDescEdit.text)

                    }
                }
            }
            RowLayout {
                width: parent.width
                height: parent.height - 126
                spacing: 16
                ListView {
                    Layout.preferredWidth: 330
                    Layout.fillHeight: true
                    model: scenariosBridge.model
                    spacing: 8
                    clip: true
                    delegate: Rectangle {
                        width: ListView.view.width
                        height: 46
                        radius: 12
                        color: scenariosBridge.selectedName === model.name ? Theme.selection : Theme.subtle
                        border.color: scenariosBridge.selectedName === model.name ? Theme.primary : Theme.border
                        Text { anchors.left: parent.left; anchors.leftMargin: 14; anchors.top: parent.top; anchors.topMargin: 8; text: model.name; color: Theme.text; font.pixelSize: 13; font.weight: Font.DemiBold; elide: Text.ElideRight; width: parent.width - 70 }
                        Text { anchors.left: parent.left; anchors.leftMargin: 14; anchors.bottom: parent.bottom; anchors.bottomMargin: 8; text: model.steps + " steps"; color: Theme.dim; font.pixelSize: 11 }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: scenariosBridge.selectScenario(model.name) }
                    }
                }
                Column {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 14
                    Text { text: "Details"; color: Theme.text; font.pixelSize: 16; font.weight: Font.DemiBold }
                    FormField { id: scenarioNameEdit; width: parent.width; label: "Name"; text: scenariosBridge.selectedName }
                    FormField { id: scenarioDescEdit; width: parent.width; label: "Description"; text: scenariosBridge.selectedDescription }
                    PrimaryButton { width: 140; text: "Apply & Close"; enabled: scenariosBridge.canManage; onClicked: { scenariosBridge.saveSelected(scenarioNameEdit.text, scenarioDescEdit.text); scenarioDialog.close() } }
                }
            }
        }
    }

    WorkspaceDialog {
        id: publishDialog
        objectName: "publishDialog"
        modal: true
        width: Math.min(520, root.width - 80)
        height: Math.min(520, root.height - 80)
        anchors.centerIn: Overlay.overlay
        padding: 0
        background: Rectangle { color: Theme.elevated; radius: Theme.radiusLg; border.color: Theme.border }
        contentItem: Column {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14
            Text { text: "Publish Scenario"; color: Theme.text; font.pixelSize: 24; font.weight: Font.DemiBold }
            Text { text: "Publish current scenario to the global marketplace."; color: Theme.muted; font.pixelSize: 13; wrapMode: Text.Wrap; width: parent.width }
            FormField { id: publishTitle; width: parent.width; label: "Title" }
            FormField { id: publishDescription; width: parent.width; label: "Description" }
            FormField { id: publishCategory; width: parent.width; label: "Category: Social, Ads, E-commerce, Scraping, Warm-up, QA, Utility" }
            Text { text: "Tags"; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold }
            Rectangle {
                width: parent.width
                height: 88
                radius: 11
                color: Theme.subtle
                border.color: Theme.border
                TextArea {
                    id: publishTags
                    anchors.fill: parent
                    anchors.margins: 10
                    color: Theme.text
                    placeholderText: "comma separated tags"
                    placeholderTextColor: Theme.dim
                    background: Item {}
                    wrapMode: TextArea.Wrap
                }
            }
            Row {
                spacing: 10
                PrimaryButton {
                    width: 130
                    text: "Publish"
                    icon: "globe"
                    enabled: scenariosBridge.canManage
                    onClicked: {
                        scenariosBridge.publishSelectedToMarket(publishTitle.text, publishDescription.text, publishCategory.text, publishTags.text)
                        publishDialog.close()
                    }
                }
                PrimaryButton { width: 110; text: "Cancel"; secondary: true; onClicked: publishDialog.close() }
            }
        }
    }

    Menu {
        id: stepMenu
        MenuItem { text: "Edit step"; onTriggered: root.reloadStepEditor() }
        MenuItem { text: "Duplicate step"; enabled: scenariosBridge.canManage; onTriggered: scenariosBridge.duplicateStep() }
        MenuSeparator {}
        MenuItem { text: "Move before"; enabled: scenariosBridge.canManage; onTriggered: scenariosBridge.moveStep(-1) }
        MenuItem { text: "Move after"; enabled: scenariosBridge.canManage; onTriggered: scenariosBridge.moveStep(1) }
        MenuSeparator {}
        MenuItem { text: "Delete step"; enabled: scenariosBridge.canManage; onTriggered: root.confirmDeleteStep() }
    }
    Menu {
        id: linkMenu
        property int sourceRow: -1
        property int targetRow: -1
        property string kind: "ok"
        MenuItem {
            text: linkMenu.kind === "err" ? "Delete error link" : "Delete success link"
            enabled: scenariosBridge.canManage
            onTriggered: scenariosBridge.deleteLink(linkMenu.sourceRow, linkMenu.targetRow, linkMenu.kind)
        }
    }
    Component.onCompleted: root.reloadStepEditor()
}
