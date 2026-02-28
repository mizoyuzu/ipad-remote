import Foundation

enum ConnectionState: Equatable {
    case disconnected
    case searching
    case connecting
    case connected(host: String)

    var isConnected: Bool {
        if case .connected = self { return true }
        return false
    }

    var label: String {
        switch self {
        case .disconnected:         "Disconnected"
        case .searching:            "Searching..."
        case .connecting:           "Connecting..."
        case .connected(let host):  "Connected: \(host)"
        }
    }
}

@Observable
class AppState {
    var mode: InputMode = .trackpad
    var connectionState: ConnectionState = .disconnected
    var serverHost: String = ""
    var serverPort: UInt16 = 5005
}
