import QtQuick
import theme 1.0
import "."

Rectangle {
    id: canvasRoot
    property alias model: nodes.model
    property real panX: 0
    property real panY: 0
    property real zoom: 1.0
    property int linkingFrom: -1
    property string linkingKind: "ok"
    property real linkStartX: 0
    property real linkStartY: 0
    property real mouseSceneX: 0
    property real mouseSceneY: 0
    property int selectedRow: -1
    property bool linkWasDragged: false
    property bool panning: false
    signal nodeSelected(int row)
    signal nodeMoved(int row, real x, real y)
    signal nodeContextRequested(int row, real x, real y)
    signal linkRequested(int sourceRow, int targetRow, string kind)
    signal linkContextRequested(int sourceRow, int targetRow, string kind, real x, real y)
    signal deleteRequested(int row)

    color: Theme.subtle
    radius: 18
    border.color: Theme.border
    clip: true
    focus: true

    function repaint() { linksCanvas.requestPaint() }
    function resetView() {
        panX = 0
        panY = 0
        zoom = 1.0
        linkingFrom = -1
        repaint()
    }
    function viewportToSceneX(vx) { return (vx - scene.x) / canvasRoot.zoom }
    function viewportToSceneY(vy) { return (vy - scene.y) / canvasRoot.zoom }
    function sceneToViewportX(sx) { return scene.x + sx * canvasRoot.zoom }
    function sceneToViewportY(sy) { return scene.y + sy * canvasRoot.zoom }
    function zoomAt(viewX, viewY, factor) {
        var oldZoom = canvasRoot.zoom
        var newZoom = Math.max(0.35, Math.min(2.5, oldZoom * factor))
        var sx = (viewX - canvasRoot.panX) / oldZoom
        var sy = (viewY - canvasRoot.panY) / oldZoom
        canvasRoot.zoom = newZoom
        canvasRoot.panX = viewX - sx * newZoom
        canvasRoot.panY = viewY - sy * newZoom
        repaint()
    }
    function nodeAtScene(sceneX, sceneY, margin) {
        margin = margin || 0
        for (var i = nodes.count - 1; i >= 0; i--) {
            var item = nodes.itemAt(i)
            if (item && sceneX >= item.x - margin && sceneX <= item.x + item.width + margin && sceneY >= item.y - margin && sceneY <= item.y + item.height + margin)
                return item
        }
        return null
    }
    function startLink(row, kind, sceneX, sceneY) {
        canvasRoot.linkingFrom = row
        canvasRoot.linkingKind = kind
        canvasRoot.linkStartX = sceneX
        canvasRoot.linkStartY = sceneY
        canvasRoot.mouseSceneX = sceneX
        canvasRoot.mouseSceneY = sceneY
        canvasRoot.linkWasDragged = false
        canvasRoot.nodeSelected(row)
        repaint()
    }
    function finishLink(sceneX, sceneY) {
        if (canvasRoot.linkingFrom < 0)
            return
        var target = nodeAtScene(sceneX, sceneY, 24)
        var source = canvasRoot.linkingFrom
        var kind = canvasRoot.linkingKind
        canvasRoot.linkingFrom = -1
        if (target)
            canvasRoot.linkRequested(source, target.row, kind)
        repaint()
    }
    function distanceToSegment(px, py, ax, ay, bx, by) {
        var dx = bx - ax
        var dy = by - ay
        var lengthSq = dx * dx + dy * dy
        if (lengthSq <= 0.001)
            return Math.sqrt((px - ax) * (px - ax) + (py - ay) * (py - ay))
        var t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lengthSq))
        var cx = ax + t * dx
        var cy = ay + t * dy
        return Math.sqrt((px - cx) * (px - cx) + (py - cy) * (py - cy))
    }
    function bezierPoint(t, p0, p1, p2, p3) {
        var mt = 1 - t
        return mt * mt * mt * p0 + 3 * mt * mt * t * p1 + 3 * mt * t * t * p2 + t * t * t * p3
    }
    function linkDistance(px, py, a, b, offset) {
        if (a === b)
            return selfLinkDistance(px, py, a, offset)
        var ax = sceneToViewportX(a.x + a.width)
        var ay = sceneToViewportY(a.y + a.height / 2 + offset)
        var bx = sceneToViewportX(b.x)
        var by = sceneToViewportY(b.y + b.height / 2)
        var c1x = ax + 70 * zoom
        var c2x = bx - 70 * zoom
        var prevX = ax
        var prevY = ay
        var best = 999999
        for (var i = 1; i <= 24; i++) {
            var t = i / 24
            var x = bezierPoint(t, ax, c1x, c2x, bx)
            var y = bezierPoint(t, ay, ay, by, by)
            best = Math.min(best, distanceToSegment(px, py, prevX, prevY, x, y))
            prevX = x
            prevY = y
        }
        return best
    }
    function selfLinkDistance(px, py, a, offset) {
        var sx = sceneToViewportX(a.x + a.width)
        var sy = sceneToViewportY(a.y + a.height / 2 + offset)
        var tx = sceneToViewportX(a.x)
        var ty = sy
        var right = 68 * zoom
        var bottom = 100 * zoom
        var left = 66 * zoom
        var yb = sceneToViewportY(a.y + a.height) + bottom
        var best = 999999
        var prevX = sx
        var prevY = sy
        for (var i = 1; i <= 40; i++) {
            var t = i / 40
            var x = bezierPoint(t, sx, sx + right, tx - left, tx - 2 * zoom)
            var y = bezierPoint(t, sy, yb, yb, ty)
            best = Math.min(best, distanceToSegment(px, py, prevX, prevY, x, y))
            prevX = x
            prevY = y
        }
        return best
    }
    function linkHitAt(viewX, viewY) {
        var items = []
        var byTag = {}
        for (var i = 0; i < nodes.count; i++) {
            var item = nodes.itemAt(i)
            if (item) {
                items.push(item)
                byTag[item.tag] = item
            }
        }
        var best = null
        var bestDistance = 12
        for (var j = 0; j < items.length; j++) {
            var a = items[j]
            if (a.nextOk && byTag[a.nextOk]) {
                var okTarget = byTag[a.nextOk]
                var okDistance = linkDistance(viewX, viewY, a, okTarget, -14)
                if (okDistance < bestDistance) {
                    bestDistance = okDistance
                    best = { source: a.row, target: okTarget.row, kind: "ok" }
                }
            }
            if (a.nextErr && byTag[a.nextErr]) {
                var errTarget = byTag[a.nextErr]
                var errDistance = linkDistance(viewX, viewY, a, errTarget, 18)
                if (errDistance < bestDistance) {
                    bestDistance = errDistance
                    best = { source: a.row, target: errTarget.row, kind: "err" }
                }
            }
        }
        return best
    }

    Keys.onPressed: function(event) {
        if ((event.key === Qt.Key_Delete || event.key === Qt.Key_Backspace) && selectedRow > 0) {
            canvasRoot.deleteRequested(selectedRow)
            event.accepted = true
        }
    }

        MouseArea {
            id: panArea
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
        property real lastX: 0
        property real lastY: 0
        onPressed: function(mouse) {
            canvasRoot.forceActiveFocus()
            lastX = mouse.x
            lastY = mouse.y
            canvasRoot.panning = mouse.button === Qt.LeftButton || mouse.button === Qt.MiddleButton
        }
        onPositionChanged: function(mouse) {
            canvasRoot.mouseSceneX = canvasRoot.viewportToSceneX(mouse.x)
            canvasRoot.mouseSceneY = canvasRoot.viewportToSceneY(mouse.y)
            if (canvasRoot.linkingFrom >= 0)
                canvasRoot.repaint()
            if (!canvasRoot.panning || !(mouse.buttons & (Qt.LeftButton | Qt.MiddleButton)))
                return
            canvasRoot.panX += mouse.x - lastX
            canvasRoot.panY += mouse.y - lastY
            lastX = mouse.x
            lastY = mouse.y
            canvasRoot.repaint()
        }
        onReleased: canvasRoot.panning = false
        onClicked: function(mouse) {
            canvasRoot.forceActiveFocus()
            if (mouse.button === Qt.RightButton) {
                var link = canvasRoot.linkHitAt(mouse.x, mouse.y)
                if (link)
                    canvasRoot.linkContextRequested(link.source, link.target, link.kind, mouse.x, mouse.y)
                return
            }
            if (canvasRoot.linkingFrom >= 0) {
                canvasRoot.linkingFrom = -1
                canvasRoot.repaint()
            }
        }
        onWheel: function(wheel) {
            canvasRoot.zoomAt(wheel.x, wheel.y, wheel.angleDelta.y > 0 ? 1.12 : 0.89)
            wheel.accepted = true
        }
        DropArea {
            anchors.fill: parent
            onPositionChanged: function(drag) {
                if (canvasRoot.linkingFrom >= 0) {
                    canvasRoot.mouseSceneX = canvasRoot.viewportToSceneX(drag.x)
                    canvasRoot.mouseSceneY = canvasRoot.viewportToSceneY(drag.y)
                    canvasRoot.repaint()
                }
            }
        }
    }

    Item {
        id: scene
        x: canvasRoot.panX
        y: canvasRoot.panY
        width: canvasRoot.width / canvasRoot.zoom
        height: canvasRoot.height / canvasRoot.zoom
        scale: canvasRoot.zoom
        transformOrigin: Item.TopLeft
        z: 2
        Repeater {
            id: nodes
            delegate: ScenarioNode {
                x: model.x
                y: model.y
                step: model.index
                property int row: model.row
                property string tag: model.tag
                property string nextOk: model.nextOk
                property string nextErr: model.nextErr
                title: model.title
                subtitle: model.subtitle
                accent: model.accent
                selected: model.selected
                onClicked: {
                    canvasRoot.forceActiveFocus()
                    canvasRoot.selectedRow = model.row
                    if (canvasRoot.linkingFrom >= 0) {
                        canvasRoot.linkRequested(canvasRoot.linkingFrom, model.row, canvasRoot.linkingKind)
                        canvasRoot.linkingFrom = -1
                        canvasRoot.repaint()
                    } else {
                        canvasRoot.nodeSelected(model.row)
                    }
                }
                onPortPressed: function(kind, localX, localY) {
                    canvasRoot.forceActiveFocus()
                    canvasRoot.selectedRow = model.row
                    canvasRoot.startLink(model.row, kind, x + localX, y + localY)
                }
                onPortDragged: function(kind, localX, localY) {
                    canvasRoot.mouseSceneX = x + localX
                    canvasRoot.mouseSceneY = y + localY
                    if (Math.abs(canvasRoot.mouseSceneX - canvasRoot.linkStartX) > 10 || Math.abs(canvasRoot.mouseSceneY - canvasRoot.linkStartY) > 10)
                        canvasRoot.linkWasDragged = true
                    canvasRoot.repaint()
                }
                onPortReleased: function(kind, localX, localY) {
                    canvasRoot.mouseSceneX = x + localX
                    canvasRoot.mouseSceneY = y + localY
                    if (Math.abs(canvasRoot.mouseSceneX - canvasRoot.linkStartX) > 10 || Math.abs(canvasRoot.mouseSceneY - canvasRoot.linkStartY) > 10)
                        canvasRoot.linkWasDragged = true
                    if (canvasRoot.linkWasDragged)
                        canvasRoot.finishLink(canvasRoot.mouseSceneX, canvasRoot.mouseSceneY)
                    else
                        canvasRoot.repaint()
                }
                onContextRequested: function(localX, localY) {
                    canvasRoot.forceActiveFocus()
                    canvasRoot.selectedRow = model.row
                    canvasRoot.nodeContextRequested(model.row, scene.x + (x + localX) * canvasRoot.zoom, scene.y + (y + localY) * canvasRoot.zoom)
                }
                onMoved: canvasRoot.repaint()
                onMoveFinished: {
                    canvasRoot.repaint()
                    canvasRoot.nodeMoved(model.row, x, y)
                }
                Component.onCompleted: canvasRoot.repaint()
            }
            onItemAdded: canvasRoot.repaint()
            onItemRemoved: canvasRoot.repaint()
        }
    }

    Canvas {
        id: linksCanvas
        anchors.fill: parent
        z: 1
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()

            ctx.fillStyle = Theme.border
            var grid = Math.max(12, 24 * canvasRoot.zoom)
            var ox = canvasRoot.panX % grid
            var oy = canvasRoot.panY % grid
            for (var gx = ox; gx < width; gx += grid) {
                for (var gy = oy; gy < height; gy += grid) {
                    ctx.fillRect(gx, gy, 1.5, 1.5)
                }
            }

            ctx.setLineDash([7, 7])
            ctx.lineWidth = 2
            var items = []
            var byTag = {}
            for (var i = 0; i < nodes.count; i++) {
                var item = nodes.itemAt(i)
                if (item) { items.push(item); byTag[item.tag] = item }
            }
            items.sort(function(a, b) { return a.step - b.step })

            function drawLink(a, b, color, offset) {
                if (a === b) {
                    drawSelfLink(a, color, offset)
                    return
                }
                var ax = canvasRoot.sceneToViewportX(a.x + a.width)
                var ay = canvasRoot.sceneToViewportY(a.y + a.height / 2 + offset)
                var bx = canvasRoot.sceneToViewportX(b.x)
                var by = canvasRoot.sceneToViewportY(b.y + b.height / 2)
                ctx.strokeStyle = color
                ctx.beginPath()
                ctx.moveTo(ax, ay)
                ctx.bezierCurveTo(ax + 70 * canvasRoot.zoom, ay, bx - 70 * canvasRoot.zoom, by, bx, by)
                ctx.stroke()
            }
            function drawSelfLink(a, color, offset) {
                var sx = canvasRoot.sceneToViewportX(a.x + a.width)
                var sy = canvasRoot.sceneToViewportY(a.y + a.height / 2 + offset)
                var tx = canvasRoot.sceneToViewportX(a.x)
                var ty = sy
                var right = 68 * canvasRoot.zoom
                var bottom = 100 * canvasRoot.zoom
                var left = 66 * canvasRoot.zoom
                var yb = canvasRoot.sceneToViewportY(a.y + a.height) + bottom
                ctx.strokeStyle = color
                ctx.beginPath()
                ctx.moveTo(sx, sy)
                ctx.bezierCurveTo(sx + right, yb, tx - left, yb, tx - 2 * canvasRoot.zoom, ty)
                ctx.stroke()
            }

            for (var j = 0; j < items.length; j++) {
                var a = items[j]
                if (a.nextOk && byTag[a.nextOk]) drawLink(a, byTag[a.nextOk], Theme.success, -14)
                if (a.nextErr && byTag[a.nextErr]) drawLink(a, byTag[a.nextErr], Theme.danger, 18)
            }

            if (canvasRoot.linkingFrom >= 0) {
                ctx.setLineDash([4, 5])
                ctx.strokeStyle = canvasRoot.linkingKind === "err" ? Theme.danger : Theme.success
                var sx = canvasRoot.sceneToViewportX(canvasRoot.linkStartX)
                var sy = canvasRoot.sceneToViewportY(canvasRoot.linkStartY)
                var tx = canvasRoot.sceneToViewportX(canvasRoot.mouseSceneX)
                var ty = canvasRoot.sceneToViewportY(canvasRoot.mouseSceneY)
                ctx.beginPath()
                ctx.moveTo(sx, sy)
                ctx.bezierCurveTo(sx + 80 * canvasRoot.zoom, sy, tx - 80 * canvasRoot.zoom, ty, tx, ty)
                ctx.stroke()
            }
        }
    }

    Rectangle {
        visible: canvasRoot.linkingFrom >= 0
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 14
        width: hintText.width + 28
        height: 34
        radius: 12
        color: Theme.card
        border.color: canvasRoot.linkingKind === "err" ? Theme.danger : Theme.success
        Text {
            id: hintText
            anchors.centerIn: parent
            text: canvasRoot.linkingKind === "err" ? "Click target node for error link" : "Click target node for success link"
            color: Theme.text
            font.pixelSize: 12
            font.bold: true
        }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 14
        width: 92
        height: 34
        radius: 11
        color: Theme.card
        border.color: Theme.border
        Text { anchors.centerIn: parent; text: Math.round(canvasRoot.zoom * 100) + "%"; color: Theme.muted; font.pixelSize: 12; font.bold: true }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onDoubleClicked: canvasRoot.resetView() }
    }

    onWidthChanged: repaint()
    onHeightChanged: repaint()
}
