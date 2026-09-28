import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0

WorkspaceDialog {
    id: root
    objectName: "pythonScriptDialog"
    title: "Python script · API v1"
    width: Math.min(1040, Overlay.overlay.width - 60)
    height: Math.min(740, Overlay.overlay.height - 40)
    anchors.centerIn: Overlay.overlay
    property string validation: ""
    property bool valid: true
    closePolicy: Popup.NoAutoClose
    Connections {
        target: scenariosBridge
        function onScenarioSaved() { if (root.visible) root.close() }
    }

    function edit(step) {
        code.text = step.code || ""
        inputs.text = JSON.stringify(step.inputs || {}, null, 2)
        resultName.text = step.result_variable || ""
        timeout.text = String(step.timeout_ms || 60000)
        validation = ""
        open()
        code.forceActiveFocus()
    }

    function check() {
        var result = scenariosBridge.checkPython(code.text)
        validation = result.message
        valid = result.ok
        if (result.line > 0) {
            var lines = code.text.split("\n")
            var offset = 0
            for (var i = 0; i < result.line - 1; i++) offset += lines[i].length + 1
            code.select(offset, offset + (lines[result.line - 1] || "").length)
            code.forceActiveFocus()
        }
        return result.ok
    }

    contentItem: ColumnLayout {
        width: root.availableWidth
        spacing: 12
        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: "async def main(ctx) · Current page: ctx.page · Browser: ctx.context · Inputs: ctx.inputs · Variables: ctx.variables · Log: ctx.log · Files: ctx.artifacts_dir · Return a JSON-compatible result."
            color: Theme.muted
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 0
            clip: true
            color: Theme.input
            border.color: Theme.border
            radius: Theme.radiusSm
            ScrollView {
                id: codeScroll
                anchors.fill: parent
                anchors.margins: 8
                TextArea {
                    id: code
                    objectName: "pythonCodeEditor"
                    font.family: "Consolas"
                    font.pixelSize: 14
                    color: Theme.text
                    wrapMode: TextEdit.NoWrap
                    selectByMouse: true
                    persistentSelection: true
                    leftPadding: 52
                    background: Item {}
                    Component.onCompleted: scenariosBridge.highlightPython(textDocument)
                    Text {
                        x: 0; y: code.topPadding
                        width: 40
                        font: code.font
                        color: Theme.dim
                        horizontalAlignment: Text.AlignRight
                        text: { var rows = []; for (var i = 1; i <= code.lineCount; i++) rows.push(i); return rows.join("\n") }
                    }
                    Keys.onPressed: function(event) {
                        if (event.key === Qt.Key_Backtab || (event.key === Qt.Key_Tab && (code.selectionStart !== code.selectionEnd || (event.modifiers & Qt.ShiftModifier)))) {
                            var selection = scenariosBridge.indentPython(code.textDocument, code.selectionStart, code.selectionEnd, event.key === Qt.Key_Backtab || !!(event.modifiers & Qt.ShiftModifier))
                            code.select(selection.start, selection.end)
                            event.accepted = true
                        } else if (event.key === Qt.Key_Tab) {
                            code.insert(code.cursorPosition, "    ")
                            event.accepted = true
                        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                            var line = code.text.slice(0, code.cursorPosition).split("\n").pop()
                            var indent = (line.match(/^ */) || [""])[0]
                            code.insert(code.cursorPosition, "\n" + indent + (line.trim().endsWith(":") ? "    " : ""))
                            event.accepted = true
                        }
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            FormField { id: resultName; Layout.fillWidth: true; Layout.minimumWidth: 0; label: "Result variable (optional)" }
            FormField { id: timeout; Layout.preferredWidth: 170; label: "Timeout ms" }
        }
        Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: "Inputs (JSON object): {{variables}} are resolved in values, never in code"; color: Theme.muted }
        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: 90
            Layout.minimumWidth: 0
            clip: true
            TextArea { id: inputs; font.family: "Consolas"; selectByMouse: true; color: Theme.text }
        }
        Label { Layout.fillWidth: true; text: root.validation; color: root.valid ? Theme.muted : "#b33d47"; wrapMode: Text.WordWrap; visible: text.length > 0 }
        RowLayout {
            Layout.fillWidth: true
            PrimaryButton { text: "Check syntax"; secondary: true; onClicked: root.check() }
            Item { Layout.fillWidth: true }
            PrimaryButton { text: "Cancel"; secondary: true; onClicked: root.close() }
            PrimaryButton {
                text: "Save script"
                enabled: scenariosBridge.canManage && !scenariosBridge.saving
                onClicked: {
                    var milliseconds = Number(timeout.text)
                    if (!Number.isInteger(milliseconds) || milliseconds < 100 || milliseconds > 3600000) {
                        root.valid = false
                        root.validation = "Timeout must be an integer between 100 and 3600000 ms."
                        return
                    }
                    if (root.check()) scenariosBridge.savePythonStep(code.text, inputs.text, resultName.text, milliseconds)
                }
            }
        }
        Label {
            Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Theme.dim
            text: "Test in Scenarios → Runs with the step debugger. This is native Python, not a sandbox. Saving or checking syntax does not run the script."
        }
    }
}
