import Network
import os

class UDPClient {
    private var connection: NWConnection?
    private let queue = DispatchQueue(label: "com.ipadremote.udp", qos: .userInteractive)

    var onStateChange: ((NWConnection.State) -> Void)?

    func connect(to host: String, port: UInt16) {
        // Cancel existing connection
        connection?.cancel()

        let endpoint = NWEndpoint.hostPort(
            host: NWEndpoint.Host(host),
            port: NWEndpoint.Port(rawValue: port)!
        )

        let params = NWParameters.udp
        params.serviceClass = .responsiveData

        let conn = NWConnection(to: endpoint, using: params)
        conn.stateUpdateHandler = { [weak self] state in
            self?.onStateChange?(state)
        }
        conn.start(queue: queue)
        self.connection = conn
    }

    /// Connect directly to a discovered Bonjour endpoint.
    func connect(to endpoint: NWEndpoint) {
        connection?.cancel()

        let params = NWParameters.udp
        params.serviceClass = .responsiveData

        let conn = NWConnection(to: endpoint, using: params)
        conn.stateUpdateHandler = { [weak self] state in
            self?.onStateChange?(state)
        }
        conn.start(queue: queue)
        self.connection = conn
    }

    func send(_ packet: Packet) {
        let data = packet.toData()
        connection?.send(content: data, completion: .contentProcessed { error in
            if let error {
                os_log(.error, "UDP send error: \(error.localizedDescription)")
            }
        })
    }

    func disconnect() {
        connection?.cancel()
        connection = nil
    }

    var isReady: Bool {
        guard let conn = connection else { return false }
        return conn.state == .ready
    }
}
