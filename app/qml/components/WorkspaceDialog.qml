import QtQuick
import QtQuick.Controls
import theme 1.0

Dialog {
    focus: true
    modal: true
    font.family: Theme.fontFamily
    Overlay.modal: Rectangle { color: Theme.overlay }
    background: Rectangle {
        color: Theme.card
        radius: Theme.radiusLg
        border.color: Theme.border
    }
}
