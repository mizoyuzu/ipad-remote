import Network

class BonjourBrowser {
    private var browser: NWBrowser?
    private let queue = DispatchQueue(label: "com.ipadremote.bonjour")

    /// Called when a service is discovered. Provides the NWEndpoint to connect to directly.
    var onDiscovered: ((NWEndpoint, String) -> Void)?

    func startBrowsing() {
        let descriptor = NWBrowser.Descriptor.bonjour(
            type: "_ipadremote._udp",
            domain: nil
        )
        let browser = NWBrowser(for: descriptor, using: .udp)

        browser.browseResultsChangedHandler = { [weak self] results, _ in
            for result in results {
                if case .service(let name, _, _, _) = result.endpoint {
                    self?.onDiscovered?(result.endpoint, name)
                }
            }
        }

        browser.stateUpdateHandler = { state in
            switch state {
            case .ready:
                break
            case .failed(let error):
                print("Bonjour browser failed: \(error)")
            default:
                break
            }
        }

        browser.start(queue: queue)
        self.browser = browser
    }

    func stopBrowsing() {
        browser?.cancel()
        browser = nil
    }
}
