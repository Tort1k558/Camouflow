import QtQuick
import QtQuick.Controls
import theme 1.0

WorkspaceDialog {
    id: root
    objectName: "confirmDialog"
    property string message: ""
    property string actionText: "Delete"
    property var action: null
    function ask(message, callback, actionText) {
        root.message = message
        root.action = callback
        root.actionText = actionText || "Delete"
        open()
    }
    anchors.centerIn: Overlay.overlay
    width: Math.min(460, Overlay.overlay.width - 48)
    padding: 24
    closePolicy: Popup.CloseOnEscape
    contentItem: Column {
        spacing: 14
        Text { text: "Confirm action"; color: Theme.text; font.pixelSize: 22; font.weight: Font.Medium }
        Text { width: parent.width; text: root.message; color: Theme.muted; wrapMode: Text.WordWrap; font.pixelSize: 13 }
    }
    footer: DialogActions {
        acceptText: root.actionText
        destructive: true
        onRejected: root.reject()
        onAccepted: root.accept()
    }
    onAccepted: {
        var callback = action
        action = null
        if (callback) callback()
    }
    onClosed: action = null
}
