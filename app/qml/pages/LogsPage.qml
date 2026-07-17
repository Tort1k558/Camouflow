import QtQuick
import theme 1.0
import "../components"

Flickable {
    contentWidth: width; contentHeight: content.height + 48; clip: true
    Column { id: content; width: parent.width - 56; x: 28; y: 24; spacing: 22
        PageHeader { width: parent.width; title: "Logs"; subtitle: "Application and automation events" }
        Row { spacing: 12; PrimaryButton { width: 34; text: ""; icon: "refresh"; iconOnly: true; secondary: true; onClicked: logsBridge.refresh() } PrimaryButton { width: 34; text: ""; icon: "trash"; iconOnly: true; danger: true; onClicked: logsBridge.clear() } }
        GlassCard { width: parent.width; height: 660; padding: 18
            ListView { anchors.fill: parent; model: logsBridge.model; spacing: 8; clip: true
                delegate: Rectangle { width: ListView.view.width; height: Math.max(42, line.height + 20); radius: 0; color: "transparent"; border.color: Theme.borderSubtle
                    Text { id: levelText; anchors.left: parent.left; anchors.leftMargin: 12; anchors.top: parent.top; anchors.topMargin: 11; width: 70; text: model.level; color: model.level === "ERROR" ? Theme.danger : model.level === "WARNING" ? Theme.warning : Theme.success; font.pixelSize: 11; font.bold: true }
                    Text { id: line; anchors.left: levelText.right; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 11; text: model.text; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.Wrap }
                }
            }
        }
    }
}
