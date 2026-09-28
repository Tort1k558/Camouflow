import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

Flickable {
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
    id: root
    contentWidth: width
    contentHeight: Math.max(height + 1, content.implicitHeight + 80)
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    Column {
        id: content
        width: parent.width - 56
        x: 28
        y: 24
        spacing: 22

        PageHeader { width: parent.width; title: "Settings"; subtitle: "Local application preferences" }
        ConfirmDialog {
            id: privacyNotice
            width: Math.min(480, root.width - 56)
            function acknowledge() {
                ask("Enable the AI assistant?", function() {}, "I understand")
            }
        }

        SettingsSection {
            width: parent.width
            height: 294
            title: "App Settings"
            subtitle: "Runtime configuration"
            icon: "settings"
            accent: Theme.primary
            Column {
                anchors.fill: parent
                spacing: 12
                Text { text: "Data root"; color: Theme.text; font.weight: Font.DemiBold; font.pixelSize: 12 }
                Rectangle {
                    width: parent.width
                    height: 42
                    radius: 11
                    color: Theme.subtle
                    border.color: Theme.border
                    Text { anchors.fill: parent; anchors.margins: 12; text: settingsBridge ? settingsBridge.dataRoot : ""; color: Theme.muted; elide: Text.ElideMiddle; font.pixelSize: 12 }
                }
                FormField {
                    id: serverUrl
                    width: parent.width
                    label: "Server URL (changing servers requires signing in again)"
                    placeholder: "https://api.example.com"
                    text: settingsBridge ? settingsBridge.serverUrl : ""

                }
                PrimaryButton { text: "Save server URL"; secondary: true; onClicked: settingsBridge.saveServerUrl(serverUrl.text) }
            }
        }

        SettingsSection {
            width: parent.width
            height: 470
            title: "AI Assistant"
            subtitle: "Browser agent provider (OpenAI-compatible: GLM, OpenAI, OpenRouter, Ollama…)"
            icon: "settings"
            accent: Theme.primary
            Column {
                anchors.fill: parent
                spacing: 12

                RowLayout {
                    width: parent.width; spacing: 10
                    Text { text: "Enable AI assistant"; color: Theme.text; font.weight: Font.DemiBold; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                    CheckBox {
                        id: aiEnabled
                        checked: settingsBridge ? settingsBridge.aiEnabled : false
                        onCheckedChanged: { if (checked && !(settingsBridge && settingsBridge.aiEnabled)) privacyNotice.acknowledge() }
                    }
                }
                Text {
                    width: parent.width; wrapMode: Text.WordWrap; color: Theme.muted; font.pixelSize: 11
                    text: "Privacy: while running a task, the structure of the visited pages (element texts, no input values) is sent to the provider you configure. Run a local Ollama endpoint to keep everything on this machine."
                }
                FormField { id: aiBaseUrl; width: parent.width; label: "Base URL (OpenAI-compatible, e.g. https://api.z.ai/api/paas/v4)"; placeholder: "https://localhost:11434/v1"; text: settingsBridge ? settingsBridge.aiBaseUrl : "" }
                FormField { id: aiApiKey; width: parent.width; label: "API key (stored locally, like server tokens)"; placeholder: "sk-…"; echoMode: TextInput.Password; text: settingsBridge ? settingsBridge.aiApiKey : "" }
                RowLayout {
                    width: parent.width; spacing: 10
                    FormField { id: aiModel; Layout.fillWidth: true; label: "Model"; placeholder: "glm-4.7"; text: settingsBridge ? settingsBridge.aiModel : "" }
                    FormField { id: aiMaxSteps; Layout.preferredWidth: 120; label: "Max steps"; text: settingsBridge ? settingsBridge.aiMaxSteps : "25" }
                }
                RowLayout {
                    width: parent.width; spacing: 10
                    PrimaryButton { text: "Save AI settings"; secondary: true; onClicked: settingsBridge.saveAiSettings(aiEnabled.checked, aiBaseUrl.text, aiApiKey.text, aiModel.text, aiMaxSteps.text) }
                    PrimaryButton { text: "Test connection"; secondary: true; onClicked: settingsBridge.testAiProvider() }
                }
            }
        }
    }
}
