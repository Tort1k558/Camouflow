import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import theme 1.0
import "../components"

Item {
    id: root
    clip: true
    objectName: "browserPage"
    property string tab: "Runtime"
    onTabChanged: settingsScroll.contentY = 0
    readonly property bool isCamoufox: browserSettingsBridge.engine === "camoufox"

    component ToggleRow: Rectangle {
        id: tr
        property string label: "Toggle"
        property string hint: ""
        property bool checked: false
        signal toggled(bool value)
        width: parent ? parent.width : 300; height: Math.max(52, toggleText.implicitHeight + 16)
        color: "transparent"
        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.borderSubtle }
        Column { id: toggleText; anchors.left: parent.left; anchors.right: sw.left; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; spacing: 3
            Text { width: parent.width; wrapMode: Text.WordWrap; text: tr.label; color: Theme.text; font.pixelSize: 13; font.weight: Font.DemiBold }
            Text { visible: tr.hint !== ""; width: parent.width; wrapMode: Text.WordWrap; text: tr.hint; color: Theme.dim; font.pixelSize: 11 }
        }
        Rectangle { id: sw; width: 40; height: 22; radius: Theme.radiusSm; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; color: tr.checked ? Theme.primary : "transparent"; border.color: tr.checked ? Theme.primaryLight : Theme.border
            Rectangle { width: 18; height: 18; radius: 9; y: 2; x: tr.checked ? 20 : 2; color: tr.checked ? Theme.primaryText : Theme.muted; Behavior on x { NumberAnimation { duration: 120 } } }
        }
        activeFocusOnTab: true
        Accessible.role: Accessible.CheckBox
        Accessible.name: label
        Accessible.checked: checked
        Accessible.onToggleAction: tr.toggled(!tr.checked)
        Keys.onSpacePressed: tr.toggled(!tr.checked)
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { tr.forceActiveFocus(); tr.toggled(!tr.checked) } }
    }

    component ModeButton: PrimaryButton {
        id: mb
        property string label: "Mode"
        property bool active: false
        text: label
        secondary: !active
        height: 36; radius: Theme.radiusSm

    }

    readonly property var sections: [
        ["Runtime", "Launch & behavior", "play", "Window mode and humanization"],
        ["Fingerprint", "Fingerprint", "globe", "Screen and browser identity"],
        ["Network", "Network", "network", "Location, proxy and protocols"],
        ["Context", "Browser context", "user", "Navigator, headers and graphics"],
        ["Storage", "Extensions", "plus", "Fonts, addons and launch options"],
        ["Advanced", "Advanced", "settings", "Raw engine configuration"],
        ["Maintenance", "Engine health", "refresh", "Compatibility and updates"]
    ]
    readonly property var currentSection: sections.filter(function(section) { return section[0] === root.tab })[0] || sections[0]

    RowLayout {
        id: header
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.margins: 28
        spacing: 12
        PageHeader { Layout.fillWidth: true; title: "Browser engine"; subtitle: "Defaults on this computer. Individual profile overrides take priority." }
        PrimaryButton {
            text: "Reset defaults"; secondary: true
            onClicked: resetDialog.ask("Reset browser defaults? Your profiles and session data will not be deleted.", function() { browserSettingsBridge.reset() }, "Reset defaults")
        }
        PrimaryButton { text: "Save changes"; icon: "save"; onClicked: browserSettingsBridge.save() }
    }

    Rectangle {
        id: engineBar
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: header.bottom
        anchors.leftMargin: 28; anchors.rightMargin: 28; anchors.topMargin: 18
        height: 64; radius: Theme.radiusLg; color: Theme.card; border.color: Theme.borderSubtle
        RowLayout {
            anchors.fill: parent; anchors.margins: 12; spacing: 10
            Text { text: "ENGINE"; color: Theme.dim; font.family: Theme.monoFamily; font.pixelSize: 10; Layout.leftMargin: 6; Layout.rightMargin: 8 }
            ModeButton { label: "Camoufox"; active: root.isCamoufox; onClicked: browserSettingsBridge.setEngine("camoufox") }
            ModeButton { label: "CloakBrowser"; active: !root.isCamoufox; onClicked: browserSettingsBridge.setEngine("cloakbrowser") }
            Item { Layout.fillWidth: true }
            Text { text: root.isCamoufox ? "Firefox / Camoufox" : "Chromium / CloakBrowser"; color: Theme.muted; font.pixelSize: 12; Layout.rightMargin: 8 }
        }
    }

    Column {
        id: navigation
        anchors.left: parent.left; anchors.top: engineBar.bottom
        anchors.leftMargin: 28; anchors.topMargin: 24
        width: 192; spacing: 6
        Repeater {
            model: root.sections
            delegate: Button {
                id: sectionButton
                required property var modelData
                readonly property bool selected: root.tab === modelData[0]
                width: navigation.width; height: 44
                text: modelData[1]
                onClicked: root.tab = modelData[0]
                background: Rectangle {
                    radius: Theme.radiusSm
                    color: sectionButton.selected ? Theme.selection : sectionButton.hovered ? Theme.subtle : "transparent"
                    border.color: sectionButton.activeFocus ? Theme.primaryInk : "transparent"
                }
                contentItem: RowLayout {
                    spacing: 10
                    LineIcon { name: sectionButton.modelData[2]; size: 17; color: sectionButton.selected ? Theme.primaryInk : Theme.dim; Layout.leftMargin: 10 }
                    Text { text: sectionButton.text; color: sectionButton.selected ? Theme.text : Theme.muted; font.pixelSize: 12; font.weight: sectionButton.selected ? Font.DemiBold : Font.Normal; Layout.fillWidth: true }
                }
            }
        }
    }

    Column {
        id: sectionHeader
        anchors.left: navigation.right; anchors.right: parent.right; anchors.top: engineBar.bottom
        anchors.leftMargin: 28; anchors.rightMargin: 28; anchors.topMargin: 24
        spacing: 6
        Text { text: root.currentSection[1]; color: Theme.text; font.pixelSize: 22; font.weight: Font.DemiBold }
        Text { text: root.currentSection[3]; color: Theme.muted; font.pixelSize: 12 }
    }

    Flickable {
        id: settingsScroll
        objectName: "browserSettingsScroll"
        anchors.left: navigation.right; anchors.right: parent.right
        anchors.top: sectionHeader.bottom; anchors.bottom: parent.bottom
        anchors.leftMargin: 28; anchors.rightMargin: 28
        anchors.topMargin: 20; anchors.bottomMargin: 28
        contentWidth: width
        contentHeight: content.implicitHeight
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        Column {
            id: content
            width: settingsScroll.width - 14
            spacing: 18
            SettingsSection {
                width: parent.width; height: 236
                visible: root.tab === "Maintenance"
                title: "Engine diagnostics"; subtitle: "Check the installed engine before updating it."; icon: "refresh"
                Column {
                    anchors.fill: parent; spacing: 20
                    Rectangle {
                        width: parent.width; height: Math.max(58, statusText.implicitHeight + 28)
                        radius: Theme.radiusSm; color: Theme.subtle
                        Text {
                            id: statusText
                            anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: 14
                            text: browserSettingsBridge.compatibilityReport === "Not checked" ? "Run a compatibility check to verify this engine installation." : browserSettingsBridge.compatibilityReport
                            color: browserSettingsBridge.compatibilityReport.indexOf("Blocked") >= 0 ? Theme.danger : Theme.muted
                            font.pixelSize: 13; wrapMode: Text.WordWrap
                        }
                    }
                    Flow {
                        width: parent.width; spacing: 10
                        PrimaryButton { text: "Check compatibility"; icon: "check"; secondary: true; onClicked: browserSettingsBridge.checkCompatibility() }
                        PrimaryButton { text: "Check updates"; icon: "refresh"; secondary: true; onClicked: browserSettingsBridge.checkEngineUpdate() }
                        PrimaryButton { text: "Update engine"; icon: "save"; enabled: browserSettingsBridge.canUpdateEngine; onClicked: browserSettingsBridge.updateEngine() }
                    }
                }
            }
            GridLayout {
                width: parent.width; columns: 1; columnSpacing: 18; rowSpacing: 18
                visible: root.tab === "Runtime"
                SettingsSection { Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; Layout.preferredHeight: sectionBody1.implicitHeight + 100; title: "Execution"; subtitle: root.isCamoufox ? "Camoufox window/headless/humanize" : "CloakBrowser headless/humanize"; icon: "play"; accent: Theme.primary
                    Column { id: sectionBody1; anchors.fill: parent; spacing: 14
                        Text { text: "Execution mode"; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold }
                        Row { width: parent.width; spacing: 10
                            ModeButton { width: (parent.width - 20) / 3; label: "Standard"; active: browserSettingsBridge.headlessMode === "standard"; onClicked: browserSettingsBridge.setHeadlessMode("standard") }
                            ModeButton { width: (parent.width - 20) / 3; label: "Headless"; active: browserSettingsBridge.headlessMode === "headless"; onClicked: browserSettingsBridge.setHeadlessMode("headless") }
                            ModeButton { width: (parent.width - 20) / 3; label: "Virtual"; active: browserSettingsBridge.headlessMode === "virtual"; enabled: root.isCamoufox; opacity: enabled ? 1 : 0.35; onClicked: if (enabled) browserSettingsBridge.setHeadlessMode("virtual") }
                        }
                        ToggleRow { label: "Human-like cursor"; hint: "Enable natural mouse movement"; checked: browserSettingsBridge.humanize; onToggled: function(value) { browserSettingsBridge.setHumanizeEnabled(value) } }
                        FormField { width: parent.width; label: "Cursor duration"; placeholder: "Auto"; text: browserSettingsBridge.humanizeDuration; onEditingFinished: browserSettingsBridge.setValue("humanize", text) }
                        Text { text: "Human preset"; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold }
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
                SettingsSection { Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; Layout.preferredHeight: sectionBody5.implicitHeight + 100; title: root.isCamoufox ? "Camoufox Storage" : "Cloak Runtime"; subtitle: root.isCamoufox ? "Profile persistence" : "Persistent context / stealth / backend"; icon: "save"; accent: Theme.primary
                    Column { id: sectionBody5; anchors.fill: parent; spacing: 12
                        ToggleRow { label: "Persistent context"; hint: "Keep browser session data"; checked: browserSettingsBridge.persistentContext; onToggled: function(value) { browserSettingsBridge.setBool("persistent_context", value) } }
                        ToggleRow { visible: root.isCamoufox; label: "Enable cache"; hint: "Camoufox disk/network cache"; checked: browserSettingsBridge.enableCache; onToggled: function(value) { browserSettingsBridge.setBool("enable_cache", value) } }
                        ToggleRow { visible: !root.isCamoufox; label: "Stealth args"; hint: "Use cloakbrowser default stealth args"; checked: browserSettingsBridge.stealthArgs; onToggled: function(value) { browserSettingsBridge.setBool("stealth_args", value) } }
                        FormField { visible: !root.isCamoufox; width: parent.width; label: "Backend"; placeholder: "Auto"; text: browserSettingsBridge.backend; onEditingFinished: browserSettingsBridge.setValue("backend", text) }
                    }
                }
            }

            GridLayout {
                width: parent.width; columns: 1; columnSpacing: 18; rowSpacing: 18
                visible: root.tab === "Fingerprint"
                SettingsSection { visible: root.isCamoufox; Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; Layout.preferredHeight: sectionBody2.implicitHeight + 100; title: "Operating Systems"; subtitle: "Camoufox OS fingerprint pool"; icon: "globe"; accent: Theme.success
                    Column { id: sectionBody2; anchors.fill: parent; spacing: 12
                        ToggleRow { label: "Auto"; hint: "Use automatic OS selection"; checked: browserSettingsBridge.osAuto; onToggled: function(value) { if (value) browserSettingsBridge.setOsEnabled("auto", true) } }
                        ToggleRow { label: "Windows"; checked: browserSettingsBridge.osWindows; onToggled: function(value) { browserSettingsBridge.setOsEnabled("windows", value) } }
                        ToggleRow { label: "macOS"; checked: browserSettingsBridge.osMacos; onToggled: function(value) { browserSettingsBridge.setOsEnabled("macos", value) } }
                        ToggleRow { label: "Linux"; checked: browserSettingsBridge.osLinux; onToggled: function(value) { browserSettingsBridge.setOsEnabled("linux", value) } }
                    }
                }
                SettingsSection { visible: !root.isCamoufox; Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; Layout.preferredHeight: sectionBody3.implicitHeight + 100; title: "Cloak Fingerprint"; subtitle: "Chromium fingerprint arguments"; icon: "globe"; accent: Theme.success
                    Column { id: sectionBody3; anchors.fill: parent; spacing: 14
                        Text { text: "Platform"; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold }
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
                SettingsSection { Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; Layout.preferredHeight: sectionBody6.implicitHeight + 100; title: "Window Size"; subtitle: "Browser viewport defaults"; icon: "dashboard"; accent: Theme.primary
                    Column { id: sectionBody6; anchors.fill: parent; spacing: 16
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
            }

            GridLayout {
                width: parent.width; columns: 1; columnSpacing: 18; rowSpacing: 18
                visible: root.tab === "Network"
                SettingsSection { Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; Layout.preferredHeight: sectionBody9.implicitHeight + 100; title: "Locale & Timezone"; subtitle: "Manual or proxy-derived locale signals"; icon: "globe"; accent: Theme.primary
                    Column { id: sectionBody9; anchors.fill: parent; spacing: 16
                        Row { width: parent.width; spacing: 10
                            ModeButton { width: (parent.width - 20) / 3; label: "Auto"; active: browserSettingsBridge.locale === "" && browserSettingsBridge.timezone === ""; onClicked: { browserSettingsBridge.setValue("locale", ""); browserSettingsBridge.setValue("timezone", "") } }
                            ModeButton { width: (parent.width - 20) / 3; label: "en-US / NY"; active: browserSettingsBridge.locale === "en-US"; onClicked: { browserSettingsBridge.setValue("locale", "en-US"); browserSettingsBridge.setValue("timezone", "America/New_York") } }
                            ModeButton { width: (parent.width - 20) / 3; label: "ru-RU / Moscow"; active: browserSettingsBridge.locale === "ru-RU"; onClicked: { browserSettingsBridge.setValue("locale", "ru-RU"); browserSettingsBridge.setValue("timezone", "Europe/Moscow") } }
                        }
                        FormField { width: parent.width; label: "Locale override"; placeholder: "Auto / en-US"; text: browserSettingsBridge.locale; onEditingFinished: browserSettingsBridge.setValue("locale", text) }
                        FormField { width: parent.width; label: "Timezone override"; placeholder: "Auto / America/New_York"; text: browserSettingsBridge.timezone; onEditingFinished: browserSettingsBridge.setValue("timezone", text) }
                        ToggleRow { visible: !root.isCamoufox; label: "GeoIP locale/timezone"; hint: "Match timezone and locale to proxy IP"; checked: browserSettingsBridge.geoip; onToggled: function(value) { browserSettingsBridge.setBool("geoip", value) } }
                    }
                }
                SettingsSection { Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; Layout.preferredHeight: sectionBody10.implicitHeight + 100; title: "Proxy & Protocol"; subtitle: "WebRTC, proxy bypass and HTTP/2"; icon: "network"; accent: Theme.success
                    Column { id: sectionBody10; anchors.fill: parent; spacing: 14
                        FormField { visible: !root.isCamoufox; width: parent.width; label: "WebRTC IP"; placeholder: "auto / explicit IP / empty"; text: browserSettingsBridge.webrtcIp; onEditingFinished: browserSettingsBridge.setValue("webrtc_ip", text) }
                        FormField { visible: !root.isCamoufox; width: parent.width; label: "Proxy bypass"; placeholder: ".google.com,localhost"; text: browserSettingsBridge.proxyBypass; onEditingFinished: browserSettingsBridge.setValue("proxy_bypass", text) }
                        ToggleRow { label: "Disable HTTP/2"; hint: "Only for sites that challenge fresh sessions"; checked: browserSettingsBridge.disableHttp2; onToggled: function(value) { browserSettingsBridge.setBool("disable_http2", value) } }
                        ToggleRow { visible: root.isCamoufox; label: "Block WebRTC"; checked: browserSettingsBridge.blockWebrtc; onToggled: function(value) { browserSettingsBridge.setBool("block_webrtc", value) } }
                    }
                }
                SettingsSection { visible: root.isCamoufox; Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; Layout.preferredHeight: sectionBody11.implicitHeight + 100; title: "Camoufox Protection"; subtitle: "Rendering/network restrictions"; icon: "zap"; accent: Theme.warning
                    Column { id: sectionBody11; anchors.fill: parent; spacing: 12
                        ToggleRow { label: "Block images"; checked: browserSettingsBridge.blockImages; onToggled: function(value) { browserSettingsBridge.setBool("block_images", value) } }
                        ToggleRow { label: "Disable COOP"; checked: browserSettingsBridge.disableCoop; onToggled: function(value) { browserSettingsBridge.setBool("disable_coop", value) } }
                    }
                }
            }

            GridLayout {
                width: parent.width; columns: 1; columnSpacing: 18; rowSpacing: 18
                visible: root.tab === "Context"
                SettingsSection { Layout.fillWidth: true; Layout.preferredHeight: 350; title: root.isCamoufox ? "Camoufox Navigator" : "CloakBrowser Navigator"; subtitle: root.isCamoufox ? "navigator_overrides + Accept-Language" : "Chromium context options"; icon: "user"; accent: Theme.primary
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
                width: parent.width; columns: 1; columnSpacing: 18; rowSpacing: 18
                visible: root.tab === "Storage"
                SettingsSection { visible: root.isCamoufox; Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; Layout.preferredHeight: sectionBody12.implicitHeight + 100; title: "Camoufox Addons"; subtitle: "fonts/addons/exclude_addons"; icon: "plus"; accent: Theme.primary
                    Column { id: sectionBody12; anchors.fill: parent; spacing: 16
                        MultiField { width: parent.width; label: "Fonts"; placeholder: "One font per line"; text: browserSettingsBridge.fontsText; onEditingFinished: browserSettingsBridge.setValue("fonts", text) }
                        MultiField { width: parent.width; label: "Addons"; placeholder: "Path or addon id per line"; text: browserSettingsBridge.addonsText; onEditingFinished: browserSettingsBridge.setValue("addons", text) }
                        MultiField { width: parent.width; label: "Exclude addons"; placeholder: "Addon ids to exclude"; text: browserSettingsBridge.excludeAddonsText; onEditingFinished: browserSettingsBridge.setValue("exclude_addons", text) }
                    }
                }
                SettingsSection { visible: !root.isCamoufox; Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; Layout.preferredHeight: sectionBody13.implicitHeight + 100; title: "CloakBrowser Launch"; subtitle: "extension_paths and launch_args"; icon: "settings"; accent: Theme.success
                    Column { id: sectionBody13; anchors.fill: parent; spacing: 16
                        MultiField { width: parent.width; label: "Extension paths"; placeholder: "One extension path per line"; text: browserSettingsBridge.extensionPathsText; onEditingFinished: browserSettingsBridge.setValue("extension_paths", text) }
                    }
                }
            }

            GridLayout {
                width: parent.width; columns: 1; columnSpacing: 18; rowSpacing: 18
                visible: root.tab === "Advanced"
                SettingsSection { visible: root.isCamoufox; Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; Layout.preferredHeight: sectionBody14.implicitHeight + 100; title: "Navigator Overrides"; subtitle: "Raw Camoufox navigator_overrides JSON"; icon: "user"; accent: Theme.primary
                    Column { id: sectionBody14; anchors.fill: parent; spacing: 12
                        MultiField { width: parent.width; fieldHeight: 250; label: "navigator_overrides JSON"; placeholder: "{\n  \"platform\": \"Win32\",\n  \"languages\": [\"en-US\", \"en\"]\n}"; text: browserSettingsBridge.navigatorOverridesText; onEditingFinished: browserSettingsBridge.setValue("navigator_overrides", text) }
                    }
                }
                SettingsSection { visible: root.isCamoufox; Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; Layout.preferredHeight: sectionBody15.implicitHeight + 100; title: "Window Overrides"; subtitle: "Raw Camoufox window_overrides JSON"; icon: "dashboard"; accent: Theme.success
                    Column { id: sectionBody15; anchors.fill: parent; spacing: 12
                        MultiField { width: parent.width; fieldHeight: 250; label: "window_overrides JSON"; placeholder: "{\n  \"screen\": {\"availWidth\": 1920}\n}"; text: browserSettingsBridge.windowOverridesText; onEditingFinished: browserSettingsBridge.setValue("window_overrides", text) }
                    }
                }
                SettingsSection { visible: !root.isCamoufox; Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; Layout.preferredHeight: sectionBody16.implicitHeight + 100; title: "Raw Launch Arguments"; subtitle: "One Chromium/Cloak flag per line"; icon: "settings"; accent: Theme.primary
                    Column { id: sectionBody16; anchors.fill: parent; spacing: 12
                        MultiField { width: parent.width; fieldHeight: 310; label: "Launch arguments"; placeholder: "--fingerprint-noise=false\n--disable-http2"; text: browserSettingsBridge.launchArgsText; onEditingFinished: browserSettingsBridge.setValue("launch_args", text) }
                    }
                }
            }
        }
    }

    ConfirmDialog { id: resetDialog }
}
