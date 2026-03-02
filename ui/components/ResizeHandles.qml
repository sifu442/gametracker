import QtQuick

Item {
    id: resizeHandles
    property var dialogRef
    property real minWidth: 320
    property real minHeight: 200
    property real handleSize: 8

    anchors.fill: parent
    z: 1000

    function applyResize(newX, newY, newW, newH) {
        dialogRef.x = newX
        dialogRef.y = newY
        dialogRef.width = newW
        dialogRef.height = newH
    }

    function clampLeft(dx, startX, startW) {
        var newW = Math.max(minWidth, startW - dx)
        var newX = startX + (startW - newW)
        return [newX, newW]
    }

    function clampTop(dy, startY, startH) {
        var newH = Math.max(minHeight, startH - dy)
        var newY = startY + (startH - newH)
        return [newY, newH]
    }

    function initStart(area) {
        area.startX = dialogRef.x
        area.startY = dialogRef.y
        area.startW = dialogRef.width
        area.startH = dialogRef.height
    }

    MouseArea {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: resizeHandles.handleSize
        cursorShape: Qt.SizeVerCursor
        property real startX
        property real startY
        property real startW
        property real startH
        onPressed: resizeHandles.initStart(this)
        onPositionChanged: function(mouse) {
            if (!pressed)
                return
            var dy = mouse.y
            var res = resizeHandles.clampTop(dy, startY, startH)
            resizeHandles.applyResize(startX, res[0], startW, res[1])
        }
    }

    MouseArea {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: resizeHandles.handleSize
        cursorShape: Qt.SizeVerCursor
        property real startX
        property real startY
        property real startW
        property real startH
        onPressed: resizeHandles.initStart(this)
        onPositionChanged: function(mouse) {
            if (!pressed)
                return
            var newH = Math.max(resizeHandles.minHeight, startH + mouse.y)
            resizeHandles.applyResize(startX, startY, startW, newH)
        }
    }

    MouseArea {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: resizeHandles.handleSize
        cursorShape: Qt.SizeHorCursor
        property real startX
        property real startY
        property real startW
        property real startH
        onPressed: resizeHandles.initStart(this)
        onPositionChanged: function(mouse) {
            if (!pressed)
                return
            var dx = mouse.x
            var res = resizeHandles.clampLeft(dx, startX, startW)
            resizeHandles.applyResize(res[0], startY, res[1], startH)
        }
    }

    MouseArea {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: resizeHandles.handleSize
        cursorShape: Qt.SizeHorCursor
        property real startX
        property real startY
        property real startW
        property real startH
        onPressed: resizeHandles.initStart(this)
        onPositionChanged: function(mouse) {
            if (!pressed)
                return
            var newW = Math.max(resizeHandles.minWidth, startW + mouse.x)
            resizeHandles.applyResize(startX, startY, newW, startH)
        }
    }

    MouseArea {
        anchors.left: parent.left
        anchors.top: parent.top
        width: resizeHandles.handleSize
        height: resizeHandles.handleSize
        cursorShape: Qt.SizeFDiagCursor
        property real startX
        property real startY
        property real startW
        property real startH
        onPressed: resizeHandles.initStart(this)
        onPositionChanged: function(mouse) {
            if (!pressed)
                return
            var dx = mouse.x
            var dy = mouse.y
            var resW = resizeHandles.clampLeft(dx, startX, startW)
            var resH = resizeHandles.clampTop(dy, startY, startH)
            resizeHandles.applyResize(resW[0], resH[0], resW[1], resH[1])
        }
    }

    MouseArea {
        anchors.right: parent.right
        anchors.top: parent.top
        width: resizeHandles.handleSize
        height: resizeHandles.handleSize
        cursorShape: Qt.SizeBDiagCursor
        property real startX
        property real startY
        property real startW
        property real startH
        onPressed: resizeHandles.initStart(this)
        onPositionChanged: function(mouse) {
            if (!pressed)
                return
            var dy = mouse.y
            var resH = resizeHandles.clampTop(dy, startY, startH)
            var newW = Math.max(resizeHandles.minWidth, startW + mouse.x)
            resizeHandles.applyResize(startX, resH[0], newW, resH[1])
        }
    }

    MouseArea {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        width: resizeHandles.handleSize
        height: resizeHandles.handleSize
        cursorShape: Qt.SizeBDiagCursor
        property real startX
        property real startY
        property real startW
        property real startH
        onPressed: resizeHandles.initStart(this)
        onPositionChanged: function(mouse) {
            if (!pressed)
                return
            var dx = mouse.x
            var resW = resizeHandles.clampLeft(dx, startX, startW)
            var newH = Math.max(resizeHandles.minHeight, startH + mouse.y)
            resizeHandles.applyResize(resW[0], startY, resW[1], newH)
        }
    }

    MouseArea {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        width: resizeHandles.handleSize
        height: resizeHandles.handleSize
        cursorShape: Qt.SizeFDiagCursor
        property real startX
        property real startY
        property real startW
        property real startH
        onPressed: resizeHandles.initStart(this)
        onPositionChanged: function(mouse) {
            if (!pressed)
                return
            var newW = Math.max(resizeHandles.minWidth, startW + mouse.x)
            var newH = Math.max(resizeHandles.minHeight, startH + mouse.y)
            resizeHandles.applyResize(startX, startY, newW, newH)
        }
    }
}
