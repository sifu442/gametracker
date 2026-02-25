import QtQuick 2.15
import QtQuick.Controls 2.15

Button {
    id: control
    property string iconText: ""
    property url iconSource: ""
    property int iconSize: 14
    property color bgColor: "#1c1c1c"
    property color bgHover: "#262626"
    property color bgPressed: "#141414"
    property color textColor: "#e8e8e8"
    readonly property bool hasIconSource: {
        var s = (control.iconSource || "").toString()
        return s !== "" && s !== "file:///" && s !== "qrc:/"
    }

    implicitHeight: 36
    implicitWidth: 96
    hoverEnabled: true

    background: Rectangle {
        radius: 6
        color: control.down ? control.bgPressed : (control.hovered ? control.bgHover : control.bgColor)
        border.color: "#2c2c2c"
    }

    contentItem: Item {
        anchors.fill: parent
        Row {
            spacing: 6
            anchors.centerIn: parent
            Image {
                source: control.iconSource
                width: control.hasIconSource ? control.iconSize : 0
                height: control.hasIconSource ? control.iconSize : 0
                fillMode: Image.PreserveAspectFit
                visible: control.hasIconSource
                smooth: true
                mipmap: true
            }
            Text {
                text: control.iconText
                color: control.textColor
                font.pointSize: 10
                verticalAlignment: Text.AlignVCenter
                visible: control.iconText !== "" && !control.hasIconSource
            }
            Text {
                text: control.text
                color: control.textColor
                font.pointSize: 10
                font.bold: true
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
        }
    }
}
