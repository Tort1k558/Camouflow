import QtQuick
import theme 1.0

Row {
    id: root
    property color ink: Theme.text
    property bool compact: false
    spacing: 9
    Canvas {
        id: mark
        width: 28; height: 28
        anchors.verticalCenter: parent.verticalCenter
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.strokeStyle = root.ink
            ctx.lineWidth = 4
            ctx.lineJoin = "round"
            ctx.beginPath()
            ctx.moveTo(24, 6)
            ctx.lineTo(12, 6)
            ctx.bezierCurveTo(0, 6, 0, 23, 12, 23)
            ctx.lineTo(18, 23)
            ctx.lineTo(18, 13)
            ctx.lineTo(8, 13)
            ctx.stroke()
            ctx.beginPath()
            ctx.moveTo(24, 13)
            ctx.lineTo(24, 24)
            ctx.stroke()
        }
        Connections { target: root; function onInkChanged() { mark.requestPaint() } }
    }
    Text {
        visible: !root.compact
        text: "camouflow"
        color: root.ink
        font.family: Theme.fontFamily
        font.pixelSize: 22
        font.weight: Font.Bold
        font.letterSpacing: -0.8
        anchors.verticalCenter: parent.verticalCenter
    }
}
