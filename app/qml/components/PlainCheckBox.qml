import QtQuick
import QtQuick.Controls

CheckBox {
    id: root
    contentItem: Text {
        text: root.text
        textFormat: Text.PlainText
        font: root.font
        color: root.palette.windowText
        leftPadding: root.indicator && !root.mirrored ? root.indicator.width + root.spacing : 0
        rightPadding: root.indicator && root.mirrored ? root.indicator.width + root.spacing : 0
        verticalAlignment: Text.AlignVCenter
    }
}
