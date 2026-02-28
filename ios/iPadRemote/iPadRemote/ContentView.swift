import SwiftUI
import Network

struct ContentView: View {
    @Environment(AppState.self) private var appState
    @State private var udpClient = UDPClient()
    @State private var bonjourBrowser = BonjourBrowser()
    @State private var haptics = HapticManager()

    var body: some View {
        @Bindable var appState = appState

        VStack(spacing: 0) {
            // Connection status bar
            ConnectionBar(
                state: appState.connectionState,
                onManualConnect: { host, port in
                    appState.serverHost = host
                    appState.serverPort = port
                    connectTo(host: host, port: port)
                }
            )

            // Mode segmented control
            Picker("Mode", selection: $appState.mode) {
                ForEach(InputMode.allCases) { mode in
                    Text(mode.label).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal)
            .padding(.vertical, 8)
            .onChange(of: appState.mode) { _, _ in
                haptics.modeSwitch()
            }

            // Active mode view
            Group {
                switch appState.mode {
                case .trackpad:
                    TrackpadView(udpClient: udpClient, haptics: haptics)
                case .scroll:
                    ScrollModeView(udpClient: udpClient, haptics: haptics)
                case .arrow:
                    ArrowKeyView(udpClient: udpClient, haptics: haptics)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            // Shortcut bar
            ShortcutBar(udpClient: udpClient, haptics: haptics)
        }
        .onAppear {
            setupBonjourDiscovery()
            setupConnectionStateHandler()
            appState.connectionState = .searching
            bonjourBrowser.startBrowsing()
        }
    }

    private func setupBonjourDiscovery() {
        bonjourBrowser.onDiscovered = { endpoint, name in
            DispatchQueue.main.async {
                guard !appState.connectionState.isConnected else { return }
                appState.connectionState = .connecting
                udpClient.connect(to: endpoint)
            }
        }
    }

    private func setupConnectionStateHandler() {
        udpClient.onStateChange = { state in
            DispatchQueue.main.async {
                switch state {
                case .ready:
                    appState.connectionState = .connected(host: appState.serverHost.isEmpty ? "mDNS" : appState.serverHost)
                case .failed, .cancelled:
                    appState.connectionState = .disconnected
                    // Auto-reconnect: restart browsing
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                        appState.connectionState = .searching
                        bonjourBrowser.startBrowsing()
                    }
                default:
                    break
                }
            }
        }
    }

    private func connectTo(host: String, port: UInt16) {
        bonjourBrowser.stopBrowsing()
        appState.connectionState = .connecting
        udpClient.connect(to: host, port: port)
    }
}
