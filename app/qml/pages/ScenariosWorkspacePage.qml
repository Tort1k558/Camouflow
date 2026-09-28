import QtQuick
import QtQuick.Layouts
import theme 1.0
import "../components"

Item {
    id: root
    objectName: "scenariosWorkspace"
    readonly property bool showingRuns: appState.currentPage === "ScenarioRuns"
    readonly property bool showingRecorder: appState.currentPage === "ScenarioRecord"
    readonly property bool showingAI: appState.currentPage === "ScenarioAI"
    Row {
        id: navigation
        x: 28; y: 16; spacing: 8
        PrimaryButton { text: "Editor"; icon: "workflow"; secondary: root.showingRuns || root.showingRecorder || root.showingAI; onClicked: appState.setPage("Scenarios") }
        PrimaryButton { text: recorderBridge.active ? "Recording..." : "Record"; icon: "plus"; secondary: !root.showingRecorder; onClicked: appState.setPage("ScenarioRecord") }
        PrimaryButton { text: aiBridge.active ? "AI running…" : "AI task"; icon: "play"; secondary: !root.showingAI; onClicked: appState.setPage("ScenarioAI") }
        PrimaryButton { text: "Runs"; icon: "play"; secondary: !root.showingRuns; onClicked: appState.setPage("ScenarioRuns") }
    }
    Item {
        anchors.fill: parent
        anchors.topMargin: navigation.y + navigation.height + 8
        ScenariosPage { anchors.fill: parent; visible: !root.showingRuns && !root.showingRecorder && !root.showingAI }
        ScenarioRecorderPanel { anchors.fill: parent; visible: root.showingRecorder }
        AIAssistantPanel { anchors.fill: parent; visible: root.showingAI }
        ScenarioRunsPanel { anchors.fill: parent; visible: root.showingRuns }
    }
}
