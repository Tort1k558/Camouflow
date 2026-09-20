import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

Item {
    id: root
    objectName: "marketplacePage"
    Component.onCompleted: scenariosBridge.ensureMarketLoaded()
    Column {
            anchors.fill: parent
            anchors.margins: 28
            spacing: 16

            RowLayout {
                width: parent.width
                height: 66
                PageHeader { title: "Scenario marketplace"; subtitle: "Inspect before installing. Destination: " + (appState.cloudEnabled ? (appState.cloudTeamName || "current team") : "this computer"); Layout.fillWidth: true }
                PrimaryButton { Layout.preferredWidth: 108; text: scenariosBridge.marketLoading ? "Loading..." : "Refresh"; enabled: !scenariosBridge.marketLoading; icon: "refresh"; secondary: true; onClicked: scenariosBridge.refreshMarket() }
                PrimaryButton { Layout.preferredWidth: 132; text: "My scenarios"; secondary: true; onClicked: appState.setPage("Scenarios") }
            }

            RowLayout {
                width: parent.width
                height: 44
                spacing: 12
                SearchBox { id: marketSearch; Layout.fillWidth: true; text: scenariosBridge.marketQuery; placeholder: "Search scenarios, tags, category..."; Keys.onReturnPressed: scenariosBridge.searchMarket(text) }
                PrimaryButton { Layout.preferredWidth: 96; text: "Search"; icon: "search"; onClicked: scenariosBridge.searchMarket(marketSearch.text) }
                PrimaryButton { Layout.preferredWidth: 96; text: "Popular"; secondary: scenariosBridge.marketSort !== "popular"; onClicked: scenariosBridge.setMarketSort("popular") }
                PrimaryButton { Layout.preferredWidth: 76; text: "New"; secondary: scenariosBridge.marketSort !== "new"; onClicked: scenariosBridge.setMarketSort("new") }
            }

            ListView {
                width: parent.width
                height: 38
                orientation: ListView.Horizontal
                spacing: 8
                clip: true
                model: scenariosBridge.marketCategoriesModel
                delegate: PrimaryButton {
                    width: Math.max(74, model.name.length * 9 + 28)
                    text: model.name
                    secondary: !model.selected
                    onClicked: scenariosBridge.setMarketCategory(model.name)
                }
            }

            RowLayout {
                width: parent.width
                height: parent.height - y
                spacing: 16

                ListView {
                    id: marketList
                    Layout.preferredWidth: parent.width * 0.48
                    Layout.fillHeight: true
                    model: scenariosBridge.marketModel
                    BusyIndicator { anchors.centerIn: parent; running: scenariosBridge.marketLoading; visible: running }
                    ScrollBar.vertical: ScrollBar {}
                    EmptyState { anchors.centerIn: parent; width: parent.width - 40; visible: marketList.count === 0 && !scenariosBridge.marketLoading; icon: "workflow"; title: "No scenarios to show"; description: "Try another search or refresh the catalog." }
                    spacing: 10
                    clip: true
                    delegate: Rectangle {
                        width: ListView.view.width
                        height: Math.max(120, marketInfo.implicitHeight + 32)
                        radius: 15
                        color: model.selected ? Theme.selection : Theme.card
                        border.color: model.selected ? Theme.primary : Theme.border

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: scenariosBridge.selectMarketScenario(model.id)
                        }

                        Column {
                            id: marketInfo
                            anchors.left: parent.left
                            anchors.leftMargin: 14
                            anchors.right: installBtn.left
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 6
                            Text { text: model.title; color: Theme.text; font.pixelSize: 14; font.weight: Font.DemiBold; elide: Text.ElideRight; width: parent.width }
                            Text { text: model.description || "No description"; color: Theme.muted; font.pixelSize: 12; elide: Text.ElideRight; width: parent.width }
                            Flow {
                                width: parent.width
                                spacing: 8
                                Text { text: model.category; color: Theme.primaryLight; font.pixelSize: 11; font.weight: Font.DemiBold }
                                Text { text: model.steps + " steps"; color: Theme.dim; font.pixelSize: 11 }
                                Text { text: model.downloads + " downloads"; color: Theme.dim; font.pixelSize: 11 }
                            }
                            Text { text: model.tags; visible: model.tags !== ""; color: Theme.dim; font.pixelSize: 11; elide: Text.ElideRight; width: parent.width }
                        }

                        PrimaryButton {
                            id: installBtn
                            anchors.right: parent.right
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            width: 86
                            enabled: !scenariosBridge.marketLoading
                            text: "Preview"
                            tooltip: "Inspect the steps before installing"
                            icon: "plus"
                            onClicked: scenariosBridge.selectMarketScenario(model.id)
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 16
                    color: Theme.card
                    border.color: Theme.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12
                        Text { text: scenariosBridge.selectedMarketTitle || "Select scenario"; color: Theme.text; font.pixelSize: 20; font.weight: Font.DemiBold; elide: Text.ElideRight; width: parent.width }
                        Text { visible: scenariosBridge.selectedMarketTitle !== ""; text: scenariosBridge.selectedMarketMeta; color: Theme.primaryLight; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight; width: parent.width }
                        Text { text: scenariosBridge.selectedMarketDescription || "Preview description and steps before installing."; color: Theme.muted; font.pixelSize: 13; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight; width: parent.width }
                        Text { text: "Steps preview"; color: Theme.text; font.pixelSize: 13; font.weight: Font.DemiBold }
                        Rectangle {
                            width: parent.width
                            height: parent.height - y - 50
                            radius: 12
                            color: Theme.subtle
                            border.color: Theme.border
                            ScrollView {
                                anchors.fill: parent
                                anchors.margins: 10
                                TextArea {
                                    text: scenariosBridge.selectedMarketStepsJson
                                    readOnly: true
                                    color: Theme.muted
                                    font.family: Theme.monoFamily
                                    font.pixelSize: 11
                                    wrapMode: TextArea.Wrap
                                    background: Item {}
                                }
                            }
                        }
                        PrimaryButton {
                            width: 150
                            text: "Install selected"
                            enabled: !scenariosBridge.marketLoading && scenariosBridge.selectedMarketTitle !== ""
                            icon: "plus"
                            onClicked: scenariosBridge.installMarketScenario("")
                        }
                    }
                }
            }
        }
}
