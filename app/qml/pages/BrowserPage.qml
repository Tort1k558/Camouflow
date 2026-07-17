import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

Flickable {
    id: root
    contentWidth: width
    contentHeight: Math.max(height + 1, content.implicitHeight + 90)
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    property string tab: "Runtime"
    readonly property bool isCamoufox: browserSettingsBridge.engine === "camoufox"

    component TabButton: Rectangle {
        id: tb
        property string label: "Tab"
        property bool active: false
        signal clicked()
        height: 36; width: 118; radius: 11
        color: active ? "#171226" : "transparent"
        border.color: active ? Theme.primary : Theme.borderSubtle
        Text { anchors.centerIn: parent; text: tb.label; color: active ? "white" : Theme.muted; font.pixelSize: 13; font.weight: Font.DemiBold }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: tb.clicked() }
    }

    component ToggleRow: Rectangle {
        id: tr
        property string label: "Toggle"
        property string hint: ""
        property bool checked: false
        signal toggled(bool value)
        width: parent ? parent.width : 300; height: 46
        color: "transparent"
        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.borderSubtle }
        Column { anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; spacing: 2
            Text { text: tr.label; color: Theme.text; font.pixelSize: 13; font.bold: true }
            Text { visible: tr.hint !== ""; text: tr.hint; color: Theme.dim; font.pixelSize: 11 }
        }
        Rectangle { id: sw; width: 40; height: 22; radius: 11; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; color: tr.checked ? Theme.primary : "transparent"; border.color: tr.checked ? Theme.primaryLight : Theme.border
            Rectangle { width: 18; height: 18; radius: 9; y: 3; x: tr.checked ? 21 : 3; color: "white"; Behavior on x { NumberAnimation { duration: 120 } } }
        }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: tr.toggled(!tr.checked) }
    }

    component ModeButton: Rectangle {
        id: mb
        property string label: "Mode"
        property bool active: false
        signal clicked()
        height: 36; radius: 11
        color: active ? Theme.primary : "transparent"
        border.color: active ? Theme.primary : Theme.border
        Text { anchors.centerIn: parent; text: mb.label; color: active ? "white" : Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: mb.clicked() }
    }

    component PresetButton: Rectangle {
        id: pb
        property string label: "Preset"
        property string preset: "balanced"
        signal clicked(string preset)
        height: 34
        width: Math.max(118, labelText.implicitWidth + 30)
        radius: 17
        color: mouse.containsMouse ? "#151520" : "transparent"
        border.color: Theme.border
        Text { id: labelText; anchors.centerIn: parent; text: pb.label; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold }
        MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pb.clicked(pb.preset) }
    }

    component EngineOption: Rectangle {
        id: eo
        property string engineId: "camoufox"
        property string title: "Camoufox"
        property string description: ""
        property string chipA: ""
        property string chipB: ""
        readonly property bool active: browserSettingsBridge.engine === engineId
        signal clicked()
        height: 126
        radius: 16
        color: active ? "#141223" : "#0d0d16"
        border.color: active ? Theme.primary : Theme.borderSubtle
        border.width: 1

        Rectangle {
            width: 3
            height: parent.height - 28
            radius: 2
            anchors.left: parent.left
            anchors.leftMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            color: active ? Theme.primary : "transparent"
        }
        LineIcon {
            anchors.left: parent.left
            anchors.leftMargin: 30
            anchors.top: parent.top
            anchors.topMargin: 18
            name: engineId === "camoufox" ? "globe" : "dashboard"
            color: active ? Theme.primaryLight : Theme.dim
            size: 22
        }
        Column {
            anchors.left: parent.left
            anchors.leftMargin: 70
            anchors.right: parent.right
            anchors.rightMargin: 18
            anchors.top: parent.top
            anchors.topMargin: 17
            spacing: 7
            Text { text: eo.title; color: active ? Theme.text : Theme.muted; font.pixelSize: 18; font.bold: true }
            Text { width: parent.width; text: eo.description; color: Theme.muted; font.pixelSize: 12; wrapMode: Text.WordWrap; maximumLineCount: 2 }
            Row {
                spacing: 8
                Rectangle { width: 128; height: 26; radius: 8; color: "transparent"; border.color: active ? Theme.primary : Theme.border; Text { anchors.centerIn: parent; text: eo.chipA; color: active ? Theme.primaryLight : Theme.dim; font.pixelSize: 11; font.bold: true } }
                Rectangle { width: 118; height: 26; radius: 8; color: "transparent"; border.color: active ? Theme.primary : Theme.border; Text { anchors.centerIn: parent; text: eo.chipB; color: active ? Theme.primaryLight : Theme.dim; font.pixelSize: 11; font.bold: true } }
            }
        }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: eo.clicked() }
    }

    component MultiField: Column {
        id: mf
        property string label: "Label"
        property alias text: input.text
        property string placeholder: ""
        property int fieldHeight: 92
        signal editingFinished()
        spacing: 8
        Text { text: mf.label; color: Theme.dim; font.pixelSize: 11; font.bold: true }
        Item { width: parent.width; height: mf.fieldHeight
            ScrollView { anchors.fill: parent; anchors.bottomMargin: 8; clip: true
                TextArea {
                    id: input
                    color: Theme.text
                    placeholderText: mf.placeholder
                    placeholderTextColor: Theme.dim
                    background: Item {}
                    wrapMode: TextArea.Wrap
                    font.pixelSize: 13
                    onActiveFocusChanged: if (!activeFocus) mf.editingFinished()
                }
            }
            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: input.activeFocus ? Theme.primary : Theme.border }
        }
    }

    Column {
        id: content
        width: parent.width - 56
        x: 28; y: 24; spacing: 22

        RowLayout { width: parent.width
            PageHeader { Layout.fillWidth: true; title: "Browser Engine"; subtitle: "New design, old full browser defaults" }
            PrimaryButton { width: 110; text: "Save"; icon: "save"; onClicked: browserSettingsBridge.save() }
            PrimaryButton { width: 110; text: "Reset"; secondary: true; onClicked: browserSettingsBridge.reset() }
            PrimaryButton { width: 130; text: "Compatibility"; secondary: true; onClicked: browserSettingsBridge.checkCompatibility() }
        }

        RowLayout { width: parent.width; spacing: 14
            EngineOption {
                Layout.fillWidth: true
                engineId: "camoufox"
                title: "Camoufox"
                description: "Firefox-based anti-detect engine with strong fingerprint masking and virtual/headless modes."
                chipA: "Deep fingerprint"
                chipB: "Virtual display"
                onClicked: browserSettingsBridge.setEngine("camoufox")
            }
            EngineOption {
                Layout.fillWidth: true
                engineId: "cloakbrowser"
                title: "CloakBrowser"
                description: "Chromium-based engine with native window control, proxy geo detection and launch args."
                chipA: "Chromium"
                chipB: "Launch args"
                onClicked: browserSettingsBridge.setEngine("cloakbrowser")
            }
        }

        GlassCard { width: parent.width; height: 62; padding: 14
            Row { anchors.verticalCenter: parent.verticalCenter; spacing: 8
                PresetButton { label: "Balanced"; preset: "balanced"; onClicked: function(presetName) { browserSettingsBridge.applyPreset(presetName) } }
                PresetButton { label: "Max stealth"; preset: "maximum_stealth"; onClicked: function(presetName) { browserSettingsBridge.applyPreset(presetName) } }
                PresetButton { label: "FingerprintJS"; preset: "fingerprintjs"; onClicked: function(presetName) { browserSettingsBridge.applyPreset(presetName) } }
                PresetButton { label: "Cloudflare"; preset: "cloudflare"; onClicked: function(presetName) { browserSettingsBridge.applyPreset(presetName) } }
                PresetButton { label: "Low resource"; preset: "low_resource"; onClicked: function(presetName) { browserSettingsBridge.applyPreset(presetName) } }
                PresetButton { label: "Warm profile"; preset: "persistent_warm"; onClicked: function(presetName) { browserSettingsBridge.applyPreset(presetName) } }
            }
        }

        GlassCard { width: parent.width; height: 64; padding: 14
            Row { anchors.verticalCenter: parent.verticalCenter; spacing: 10
                TabButton { label: "Runtime"; active: root.tab === label; onClicked: root.tab = label }
                TabButton { label: "Fingerprint"; active: root.tab === label; onClicked: root.tab = label }
                TabButton { label: "Network"; active: root.tab === label; onClicked: root.tab = label }
                TabButton { label: "Context"; active: root.tab === label; onClicked: root.tab = label }
                TabButton { label: "Storage"; active: root.tab === label; onClicked: root.tab = label }
                TabButton { label: "Advanced"; active: root.tab === label; onClicked: root.tab = label }
            }
        }

        GridLayout {
            width: parent.width; columns: 2; columnSpacing: 22; rowSpacing: 22
            visible: root.tab === "Runtime"
            SettingsSection { Layout.fillWidth: true; Layout.preferredHeight: root.isCamoufox ? 390 : 560; title: "Execution"; subtitle: root.isCamoufox ? "Camoufox window/headless/humanize" : "CloakBrowser headless/humanize"; icon: "play"; accent: Theme.primary
                Column { anchors.fill: parent; spacing: 14
                    Text { text: "Execution mode"; color: Theme.text; font.pixelSize: 12; font.bold: true }
                    Row { width: parent.width; spacing: 10
                        ModeButton { width: (parent.width - 20) / 3; label: "Standard"; active: browserSettingsBridge.headlessMode === "standard"; onClicked: browserSettingsBridge.setHeadlessMode("standard") }
                        ModeButton { width: (parent.width - 20) / 3; label: "Headless"; active: browserSettingsBridge.headlessMode === "headless"; onClicked: browserSettingsBridge.setHeadlessMode("headless") }
                        ModeButton { width: (parent.width - 20) / 3; label: "Virtual"; active: browserSettingsBridge.headlessMode === "virtual"; enabled: root.isCamoufox; opacity: enabled ? 1 : 0.35; onClicked: if (enabled) browserSettingsBridge.setHeadlessMode("virtual") }
                    }
                    ToggleRow { label: "Human-like cursor"; hint: "Enable natural mouse movement"; checked: browserSettingsBridge.humanize; onToggled: function(value) { browserSettingsBridge.setHumanizeEnabled(value) } }
                    FormField { width: parent.width; label: "Cursor duration"; placeholder: "Auto"; text: browserSettingsBridge.humanizeDuration; onEditingFinished: browserSettingsBridge.setValue("humanize", text) }
                    Text { text: "Human preset"; color: Theme.text; font.pixelSize: 12; font.bold: true }
                    Row { width: parent.width; spacing: 10
                        ModeButton { width: (parent.width - 10) / 2; label: "Default human"; active: browserSettingsBridge.humanPreset === "default"; onClicked: browserSettingsBridge.setValue("human_preset", "default") }
                        ModeButton { width: (parent.width - 10) / 2; label: "Careful human"; active: browserSettingsBridge.humanPreset === "careful"; onClicked: browserSettingsBridge.setValue("human_preset", "careful") }
                    }
                    Row { visible: !root.isCamoufox; width: parent.width; spacing: 16
                        FormField { width: (parent.width - 16) / 2; label: "Mouse speed"; placeholder: "Auto"; text: browserSettingsBridge.humanMouseSpeed; onEditingFinished: browserSettingsBridge.setValue("human_mouse_speed", text) }
                        FormField { width: (parent.width - 16) / 2; label: "Scroll intensity"; placeholder: "Auto"; text: browserSettingsBridge.humanScrollIntensity; onEditingFinished: browserSettingsBridge.setValue("human_scroll_intensity", parseInt(text || "0")) }
                    }
                    Row { visible: !root.isCamoufox; width: parent.width; spacing: 16
                        FormField { width: (parent.width - 16) / 2; label: "Typing min ms"; placeholder: "Auto"; text: browserSettingsBridge.humanTypingDelayMin; onEditingFinished: browserSettingsBridge.setValue("human_typing_delay_min", parseInt(text || "0")) }
                        FormField { width: (parent.width - 16) / 2; label: "Typing max ms"; placeholder: "Auto"; text: browserSettingsBridge.humanTypingDelayMax; onEditingFinished: browserSettingsBridge.setValue("human_typing_delay_max", parseInt(text || "0")) }
                    }
                    ToggleRow { visible: !root.isCamoufox; label: "Actionability wait"; hint: "Wait visible/enabled/stable before humanized actions"; checked: browserSettingsBridge.humanActionabilityWait; onToggled: function(value) { browserSettingsBridge.setBool("human_actionability_wait", value) } }
                }
            }
            SettingsSection { visible: root.isCamoufox; Layout.fillWidth: true; Layout.preferredHeight: 320; title: "Operating Systems"; subtitle: "Camoufox OS fingerprint pool"; icon: "globe"; accent: Theme.success
                Column { anchors.fill: parent; spacing: 12
                    ToggleRow { label: "Auto"; hint: "Use automatic OS selection"; checked: browserSettingsBridge.osAuto; onToggled: function(value) { if (value) browserSettingsBridge.setOsEnabled("auto", true) } }
                    ToggleRow { label: "Windows"; checked: browserSettingsBridge.osWindows; onToggled: function(value) { browserSettingsBridge.setOsEnabled("windows", value) } }
                    ToggleRow { label: "macOS"; checked: browserSettingsBridge.osMacos; onToggled: function(value) { browserSettingsBridge.setOsEnabled("macos", value) } }
                    ToggleRow { label: "Linux"; checked: browserSettingsBridge.osLinux; onToggled: function(value) { browserSettingsBridge.setOsEnabled("linux", value) } }
                }
            }
            SettingsSection { visible: !root.isCamoufox; Layout.fillWidth: true; Layout.preferredHeight: 560; title: "Cloak Fingerprint"; subtitle: "Chromium fingerprint arguments"; icon: "globe"; accent: Theme.success
                Column { anchors.fill: parent; spacing: 14
                    Text { text: "Platform"; color: Theme.text; font.pixelSize: 12; font.bold: true }
                    Row { width: parent.width; spacing: 10
                        ModeButton { width: (parent.width - 20) / 3; label: "Windows"; active: browserSettingsBridge.platform === "windows"; onClicked: browserSettingsBridge.setValue("platform", "windows") }
                        ModeButton { width: (parent.width - 20) / 3; label: "macOS"; active: browserSettingsBridge.platform === "macos"; onClicked: browserSettingsBridge.setValue("platform", "macos") }
                        ModeButton { width: (parent.width - 20) / 3; label: "Linux"; active: browserSettingsBridge.platform === "linux"; onClicked: browserSettingsBridge.setValue("platform", "linux") }
                    }
                    FormField { width: parent.width; label: "Fingerprint seed"; placeholder: "Auto per profile"; text: browserSettingsBridge.fingerprintSeed; onEditingFinished: browserSettingsBridge.setValue("fingerprint_seed", parseInt(text || "0")) }
                    Row { width: parent.width; spacing: 16
                        FormField { width: (parent.width - 16) / 2; label: "Platform version"; placeholder: "Auto"; text: browserSettingsBridge.platformVersion; onEditingFinished: browserSettingsBridge.setValue("platform_version", text) }
                        FormField { width: (parent.width - 16) / 2; label: "Brand version"; placeholder: "Auto"; text: browserSettingsBridge.brandVersion; onEditingFinished: browserSettingsBridge.setValue("brand_version", text) }
                    }
                    Row { width: parent.width; spacing: 16
                        FormField { width: (parent.width - 16) / 2; label: "Brand"; placeholder: "Auto / Chrome"; text: browserSettingsBridge.brand; onEditingFinished: browserSettingsBridge.setValue("brand", text) }
                        FormField { width: (parent.width - 16) / 2; label: "Device memory GB"; placeholder: "Auto"; text: browserSettingsBridge.deviceMemory; onEditingFinished: browserSettingsBridge.setValue("device_memory", parseInt(text || "0")) }
                    }
                    Row { width: parent.width; spacing: 16
                        FormField { width: (parent.width - 16) / 2; label: "Storage quota MB"; placeholder: "Auto / 500"; text: browserSettingsBridge.storageQuota; onEditingFinished: browserSettingsBridge.setValue("storage_quota", parseInt(text || "0")) }
                        FormField { width: (parent.width - 16) / 2; label: "WebRTC IP"; placeholder: "auto / IP"; text: browserSettingsBridge.webrtcIp; onEditingFinished: browserSettingsBridge.setValue("webrtc_ip", text) }
                    }
                    ToggleRow { label: "Fingerprint noise"; hint: "Disable only for FPJS troubleshooting"; checked: browserSettingsBridge.fingerprintNoise; onToggled: function(value) { browserSettingsBridge.setBool("fingerprint_noise", value) } }
                }
            }
            SettingsSection { Layout.fillWidth: true; Layout.preferredHeight: 310; title: "Locale & Timezone"; subtitle: root.isCamoufox ? "Camoufox locale/config overrides" : "CloakBrowser locale/timezone launch options"; icon: "globe"; accent: Theme.warning
                Column { anchors.fill: parent; spacing: 16
                    FormField { width: parent.width; label: "Locale override"; placeholder: "Auto / en-US"; text: browserSettingsBridge.locale; onEditingFinished: browserSettingsBridge.setValue("locale", text) }
                    FormField { width: parent.width; label: "Timezone override"; placeholder: "Auto / America/New_York"; text: browserSettingsBridge.timezone; onEditingFinished: browserSettingsBridge.setValue("timezone", text) }
                    Row { width: parent.width; spacing: 10
                        ModeButton { width: (parent.width - 20) / 3; label: "Auto"; active: browserSettingsBridge.locale === "" && browserSettingsBridge.timezone === ""; onClicked: { browserSettingsBridge.setValue("locale", ""); browserSettingsBridge.setValue("timezone", "") } }
                        ModeButton { width: (parent.width - 20) / 3; label: "en-US / NY"; active: browserSettingsBridge.locale === "en-US"; onClicked: { browserSettingsBridge.setValue("locale", "en-US"); browserSettingsBridge.setValue("timezone", "America/New_York") } }
                        ModeButton { width: (parent.width - 20) / 3; label: "ru-RU / Moscow"; active: browserSettingsBridge.locale === "ru-RU"; onClicked: { browserSettingsBridge.setValue("locale", "ru-RU"); browserSettingsBridge.setValue("timezone", "Europe/Moscow") } }
                    }
                }
            }
            SettingsSection { Layout.fillWidth: true; Layout.preferredHeight: root.isCamoufox ? 270 : 390; title: root.isCamoufox ? "Camoufox Storage" : "Cloak Runtime"; subtitle: root.isCamoufox ? "Profile persistence" : "Persistent context / stealth / backend"; icon: "save"; accent: Theme.primary
                Column { anchors.fill: parent; spacing: 12
                    ToggleRow { label: "Persistent context"; hint: "Keep browser session data"; checked: browserSettingsBridge.persistentContext; onToggled: function(value) { browserSettingsBridge.setBool("persistent_context", value) } }
                    ToggleRow { visible: root.isCamoufox; label: "Enable cache"; hint: "Camoufox disk/network cache"; checked: browserSettingsBridge.enableCache; onToggled: function(value) { browserSettingsBridge.setBool("enable_cache", value) } }
                    ToggleRow { visible: !root.isCamoufox; label: "GeoIP locale/timezone"; hint: "CloakBrowser proxy-based detection"; checked: browserSettingsBridge.geoip; onToggled: function(value) { browserSettingsBridge.setBool("geoip", value) } }
                    ToggleRow { visible: !root.isCamoufox; label: "Stealth args"; hint: "Use cloakbrowser default stealth args"; checked: browserSettingsBridge.stealthArgs; onToggled: function(value) { browserSettingsBridge.setBool("stealth_args", value) } }
                    FormField { visible: !root.isCamoufox; width: parent.width; label: "Backend"; placeholder: "Auto"; text: browserSettingsBridge.backend; onEditingFinished: browserSettingsBridge.setValue("backend", text) }
                }
            }
        }

        GridLayout {
            width: parent.width; columns: 2; columnSpacing: 22; rowSpacing: 22
            visible: root.tab === "Fingerprint"
            SettingsSection { Layout.fillWidth: true; Layout.preferredHeight: 310; title: "Window Size"; subtitle: "Browser viewport defaults"; icon: "dashboard"; accent: Theme.primary
                Column { anchors.fill: parent; spacing: 16
                    Row { width: parent.width; spacing: 16
                        FormField { width: (parent.width - 16) / 2; label: "Window width"; text: browserSettingsBridge.windowWidth; onEditingFinished: browserSettingsBridge.setValue("window_width", parseInt(text)) }
                        FormField { width: (parent.width - 16) / 2; label: "Window height"; text: browserSettingsBridge.windowHeight; onEditingFinished: browserSettingsBridge.setValue("window_height", parseInt(text)) }
                    }
                    Row { width: parent.width; spacing: 16
                        FormField { width: (parent.width - 16) / 2; label: "Screen width"; text: browserSettingsBridge.screenWidth; onEditingFinished: browserSettingsBridge.setValue("screen_width", parseInt(text)) }
                        FormField { width: (parent.width - 16) / 2; label: "Screen height"; text: browserSettingsBridge.screenHeight; onEditingFinished: browserSettingsBridge.setValue("screen_height", parseInt(text)) }
                    }
                    PrimaryButton { width: 110; text: "Auto size"; secondary: true; onClicked: { browserSettingsBridge.setValue("window_width", 0); browserSettingsBridge.setValue("window_height", 0); browserSettingsBridge.setValue("screen_width", 0); browserSettingsBridge.setValue("screen_height", 0) } }
                }
            }
            SettingsSection { visible: root.isCamoufox; Layout.fillWidth: true; Layout.preferredHeight: 310; title: "Camoufox Runtime Protection"; subtitle: "Network/rendering restrictions"; icon: "zap"; accent: Theme.warning
                Column { anchors.fill: parent; spacing: 12
                    ToggleRow { label: "Block WebRTC"; checked: browserSettingsBridge.blockWebrtc; onToggled: function(value) { browserSettingsBridge.setBool("block_webrtc", value) } }
                    ToggleRow { label: "Block images"; checked: browserSettingsBridge.blockImages; onToggled: function(value) { browserSettingsBridge.setBool("block_images", value) } }
                    ToggleRow { label: "Disable COOP"; checked: browserSettingsBridge.disableCoop; onToggled: function(value) { browserSettingsBridge.setBool("disable_coop", value) } }
                }
            }
            SettingsSection { visible: root.isCamoufox; Layout.fillWidth: true; Layout.preferredHeight: 280; title: "Camoufox Window Overrides"; subtitle: "window_overrides JSON passed to config"; icon: "settings"; accent: Theme.success
                Column { anchors.fill: parent; spacing: 12
                    MultiField { width: parent.width; fieldHeight: 170; label: "window_overrides JSON"; placeholder: "{\n  \"screen\": {\"availWidth\": 1920}\n}"; text: browserSettingsBridge.windowOverridesText; onEditingFinished: browserSettingsBridge.setValue("window_overrides", text) }
                }
            }
        }

        GridLayout {
            width: parent.width; columns: 2; columnSpacing: 22; rowSpacing: 22
            visible: root.tab === "Network"
            SettingsSection { Layout.fillWidth: true; Layout.preferredHeight: 320; title: "Locale & Timezone"; subtitle: "Manual or proxy-derived locale signals"; icon: "globe"; accent: Theme.primary
                Column { anchors.fill: parent; spacing: 16
                    FormField { width: parent.width; label: "Locale override"; placeholder: "Auto / en-US"; text: browserSettingsBridge.locale; onEditingFinished: browserSettingsBridge.setValue("locale", text) }
                    FormField { width: parent.width; label: "Timezone override"; placeholder: "Auto / America/New_York"; text: browserSettingsBridge.timezone; onEditingFinished: browserSettingsBridge.setValue("timezone", text) }
                    ToggleRow { visible: !root.isCamoufox; label: "GeoIP locale/timezone"; hint: "Match timezone and locale to proxy IP"; checked: browserSettingsBridge.geoip; onToggled: function(value) { browserSettingsBridge.setBool("geoip", value) } }
                }
            }
            SettingsSection { Layout.fillWidth: true; Layout.preferredHeight: 320; title: "Proxy & Protocol"; subtitle: "WebRTC, proxy bypass and HTTP/2"; icon: "network"; accent: Theme.success
                Column { anchors.fill: parent; spacing: 14
                    FormField { visible: !root.isCamoufox; width: parent.width; label: "WebRTC IP"; placeholder: "auto / explicit IP / empty"; text: browserSettingsBridge.webrtcIp; onEditingFinished: browserSettingsBridge.setValue("webrtc_ip", text) }
                    FormField { visible: !root.isCamoufox; width: parent.width; label: "Proxy bypass"; placeholder: ".google.com,localhost"; text: browserSettingsBridge.proxyBypass; onEditingFinished: browserSettingsBridge.setValue("proxy_bypass", text) }
                    ToggleRow { label: "Disable HTTP/2"; hint: "Only for sites that challenge fresh sessions"; checked: browserSettingsBridge.disableHttp2; onToggled: function(value) { browserSettingsBridge.setBool("disable_http2", value) } }
                    ToggleRow { visible: root.isCamoufox; label: "Block WebRTC"; checked: browserSettingsBridge.blockWebrtc; onToggled: function(value) { browserSettingsBridge.setBool("block_webrtc", value) } }
                }
            }
            SettingsSection { visible: root.isCamoufox; Layout.fillWidth: true; Layout.preferredHeight: 250; title: "Camoufox Protection"; subtitle: "Rendering/network restrictions"; icon: "zap"; accent: Theme.warning
                Column { anchors.fill: parent; spacing: 12
                    ToggleRow { label: "Block images"; checked: browserSettingsBridge.blockImages; onToggled: function(value) { browserSettingsBridge.setBool("block_images", value) } }
                    ToggleRow { label: "Disable COOP"; checked: browserSettingsBridge.disableCoop; onToggled: function(value) { browserSettingsBridge.setBool("disable_coop", value) } }
                }
            }
        }

        GridLayout {
            width: parent.width; columns: 2; columnSpacing: 22; rowSpacing: 22
            visible: root.tab === "Context"
            SettingsSection { Layout.fillWidth: true; Layout.preferredHeight: root.isCamoufox ? 540 : 500; title: root.isCamoufox ? "Camoufox Navigator" : "CloakBrowser Navigator"; subtitle: root.isCamoufox ? "navigator_overrides + Accept-Language" : "Chromium context options"; icon: "user"; accent: Theme.primary
                ColumnLayout { anchors.fill: parent; spacing: 16
                    RowLayout { Layout.fillWidth: true; spacing: 12
                        FormField { Layout.fillWidth: true; Layout.preferredHeight: 62; label: "User Agent"; placeholder: "Auto"; text: browserSettingsBridge.userAgent; onEditingFinished: browserSettingsBridge.setValue("user_agent", text) }
                        PrimaryButton { text: "Auto UA"; secondary: true; Layout.preferredWidth: 110; Layout.alignment: Qt.AlignBottom; onClicked: browserSettingsBridge.setValue("user_agent", "") }
                    }
                    RowLayout { Layout.fillWidth: true; spacing: 10
                        ToggleRow { Layout.fillWidth: true; label: "Ignore HTTPS"; checked: browserSettingsBridge.ignoreHttpsErrors; onToggled: function(value) { browserSettingsBridge.setBool("ignore_https_errors", value) } }
                        ToggleRow { Layout.fillWidth: true; label: "JavaScript"; checked: browserSettingsBridge.javaScriptEnabled; onToggled: function(value) { browserSettingsBridge.setBool("java_script_enabled", value) } }
                    }
                    RowLayout { Layout.fillWidth: true; spacing: 10
                        ToggleRow { Layout.fillWidth: true; label: "Bypass CSP"; checked: browserSettingsBridge.bypassCsp; onToggled: function(value) { browserSettingsBridge.setBool("bypass_csp", value) } }
                        ToggleRow { Layout.fillWidth: true; label: "Downloads"; checked: browserSettingsBridge.acceptDownloads; onToggled: function(value) { browserSettingsBridge.setBool("accept_downloads", value) } }
                    }
                    RowLayout { Layout.fillWidth: true; spacing: 16
                        FormField { Layout.fillWidth: true; Layout.preferredHeight: 62; label: "CPU cores"; text: browserSettingsBridge.cpuCores; onEditingFinished: browserSettingsBridge.setValue("hardware_concurrency", parseInt(text)) }
                        PrimaryButton { text: "Auto CPU"; secondary: true; Layout.preferredWidth: 110; Layout.alignment: Qt.AlignBottom; onClicked: browserSettingsBridge.setValue("hardware_concurrency", 0) }
                    }
                    MultiField { visible: root.isCamoufox; width: parent.width; fieldHeight: 170; label: "navigator_overrides JSON"; placeholder: "{\n  \"platform\": \"Win32\",\n  \"languages\": [\"en-US\", \"en\"]\n}"; text: browserSettingsBridge.navigatorOverridesText; onEditingFinished: browserSettingsBridge.setValue("navigator_overrides", text) }
                }
            }
            SettingsSection { Layout.fillWidth: true; Layout.preferredHeight: 500; title: "Headers & Permissions"; subtitle: "Context extra headers and permissions"; icon: "check"; accent: Theme.warning
                ColumnLayout { anchors.fill: parent; spacing: 16
                    MultiField { width: parent.width; fieldHeight: 190; label: "Extra HTTP headers JSON"; placeholder: "{\n  \"DNT\": \"1\"\n}"; text: browserSettingsBridge.extraHttpHeadersText; onEditingFinished: browserSettingsBridge.setValue("extra_http_headers", text) }
                    MultiField { width: parent.width; fieldHeight: 160; label: "Permissions"; placeholder: "geolocation\nnotifications\ncamera\nmicrophone"; text: browserSettingsBridge.permissionsText; onEditingFinished: browserSettingsBridge.setValue("permissions", text) }
                    FormField { Layout.fillWidth: true; label: "Storage state path"; placeholder: "state.json"; text: browserSettingsBridge.storageStatePath; onEditingFinished: browserSettingsBridge.setValue("storage_state_path", text) }
                }
            }
            SettingsSection { Layout.fillWidth: true; Layout.preferredHeight: root.isCamoufox ? 350 : 500; title: root.isCamoufox ? "Camoufox WebGL" : "CloakBrowser GPU"; subtitle: root.isCamoufox ? "Validated webgl_config pair" : "Fingerprint GPU launch args"; icon: "settings"; accent: Theme.success
                ColumnLayout { anchors.fill: parent; spacing: 16
                    FormField { Layout.fillWidth: true; label: "WebGL / GPU vendor"; placeholder: "Auto"; text: browserSettingsBridge.webglVendor; onEditingFinished: browserSettingsBridge.setValue("webgl_vendor", text) }
                    FormField { Layout.fillWidth: true; label: "WebGL / GPU renderer"; placeholder: "Auto"; text: browserSettingsBridge.webglRenderer; onEditingFinished: browserSettingsBridge.setValue("webgl_renderer", text) }
                    RowLayout { Layout.fillWidth: true; spacing: 10
                        ModeButton { Layout.fillWidth: true; label: "Auto GPU"; active: browserSettingsBridge.webglVendor === "" && browserSettingsBridge.webglRenderer === ""; onClicked: { browserSettingsBridge.setValue("webgl_vendor", ""); browserSettingsBridge.setValue("webgl_renderer", "") } }
                        ModeButton { Layout.fillWidth: true; label: "NVIDIA"; active: browserSettingsBridge.webglVendor.indexOf("NVIDIA") >= 0; onClicked: { browserSettingsBridge.setValue("webgl_vendor", "NVIDIA Corporation"); browserSettingsBridge.setValue("webgl_renderer", "NVIDIA GeForce RTX") } }
                        ModeButton { Layout.fillWidth: true; label: "Intel"; active: browserSettingsBridge.webglVendor.indexOf("Intel") >= 0; onClicked: { browserSettingsBridge.setValue("webgl_vendor", "Intel Inc."); browserSettingsBridge.setValue("webgl_renderer", "Intel Iris OpenGL Engine") } }
                    }
                    RowLayout { visible: !root.isCamoufox; Layout.fillWidth: true; spacing: 10
                        ModeButton { Layout.fillWidth: true; label: "Auto"; active: browserSettingsBridge.colorScheme === ""; onClicked: browserSettingsBridge.setValue("color_scheme", "") }
                        ModeButton { Layout.fillWidth: true; label: "Light"; active: browserSettingsBridge.colorScheme === "light"; onClicked: browserSettingsBridge.setValue("color_scheme", "light") }
                        ModeButton { Layout.fillWidth: true; label: "Dark"; active: browserSettingsBridge.colorScheme === "dark"; onClicked: browserSettingsBridge.setValue("color_scheme", "dark") }
                    }
                    ToggleRow { visible: root.isCamoufox; width: parent.width; label: "Block WebGL"; checked: browserSettingsBridge.blockWebgl; onToggled: function(value) { browserSettingsBridge.setBool("block_webgl", value) } }
                }
            }
        }

        GridLayout {
            width: parent.width; columns: 2; columnSpacing: 22; rowSpacing: 22
            visible: root.tab === "Storage"
            SettingsSection { visible: root.isCamoufox; Layout.fillWidth: true; Layout.preferredHeight: 520; title: "Camoufox Addons"; subtitle: "fonts/addons/exclude_addons"; icon: "plus"; accent: Theme.primary
                Column { anchors.fill: parent; spacing: 16
                    MultiField { width: parent.width; label: "Fonts"; placeholder: "One font per line"; text: browserSettingsBridge.fontsText; onEditingFinished: browserSettingsBridge.setValue("fonts", text) }
                    MultiField { width: parent.width; label: "Addons"; placeholder: "Path or addon id per line"; text: browserSettingsBridge.addonsText; onEditingFinished: browserSettingsBridge.setValue("addons", text) }
                    MultiField { width: parent.width; label: "Exclude addons"; placeholder: "Addon ids to exclude"; text: browserSettingsBridge.excludeAddonsText; onEditingFinished: browserSettingsBridge.setValue("exclude_addons", text) }
                }
            }
            SettingsSection { visible: !root.isCamoufox; Layout.fillWidth: true; Layout.preferredHeight: 390; title: "CloakBrowser Launch"; subtitle: "extension_paths and launch_args"; icon: "settings"; accent: Theme.success
                Column { anchors.fill: parent; spacing: 16
                    MultiField { width: parent.width; label: "Extension paths"; placeholder: "One extension path per line"; text: browserSettingsBridge.extensionPathsText; onEditingFinished: browserSettingsBridge.setValue("extension_paths", text) }
                    MultiField { width: parent.width; label: "Launch arguments"; placeholder: "--flag=value"; text: browserSettingsBridge.launchArgsText; onEditingFinished: browserSettingsBridge.setValue("launch_args", text) }
                }
            }
        }

        GridLayout {
            width: parent.width; columns: 2; columnSpacing: 22; rowSpacing: 22
            visible: root.tab === "Advanced"
            SettingsSection { visible: root.isCamoufox; Layout.fillWidth: true; Layout.preferredHeight: 360; title: "Navigator Overrides"; subtitle: "Raw Camoufox navigator_overrides JSON"; icon: "user"; accent: Theme.primary
                Column { anchors.fill: parent; spacing: 12
                    MultiField { width: parent.width; fieldHeight: 250; label: "navigator_overrides JSON"; placeholder: "{\n  \"platform\": \"Win32\",\n  \"languages\": [\"en-US\", \"en\"]\n}"; text: browserSettingsBridge.navigatorOverridesText; onEditingFinished: browserSettingsBridge.setValue("navigator_overrides", text) }
                }
            }
            SettingsSection { visible: root.isCamoufox; Layout.fillWidth: true; Layout.preferredHeight: 360; title: "Window Overrides"; subtitle: "Raw Camoufox window_overrides JSON"; icon: "dashboard"; accent: Theme.success
                Column { anchors.fill: parent; spacing: 12
                    MultiField { width: parent.width; fieldHeight: 250; label: "window_overrides JSON"; placeholder: "{\n  \"screen\": {\"availWidth\": 1920}\n}"; text: browserSettingsBridge.windowOverridesText; onEditingFinished: browserSettingsBridge.setValue("window_overrides", text) }
                }
            }
            SettingsSection { visible: !root.isCamoufox; Layout.fillWidth: true; Layout.preferredHeight: 420; title: "Raw Launch Arguments"; subtitle: "One Chromium/Cloak flag per line"; icon: "settings"; accent: Theme.primary
                Column { anchors.fill: parent; spacing: 12
                    MultiField { width: parent.width; fieldHeight: 310; label: "Launch arguments"; placeholder: "--fingerprint-noise=false\n--disable-http2"; text: browserSettingsBridge.launchArgsText; onEditingFinished: browserSettingsBridge.setValue("launch_args", text) }
                }
            }
        }
    }
}
