import SwiftUI

struct ShortcutBar: View {
    let udpClient: UDPClient
    let haptics: HapticManager

    var body: some View {
        HStack(spacing: 20) {
            Button {
                haptics.tap()
                sendShortcut(keycode: HIDKeycode.keyH, modifier: HIDModifier.leftGUI)
            } label: {
                Label("Home", systemImage: "house")
            }

            Button {
                haptics.tap()
                sendShortcut(keycode: HIDKeycode.tab, modifier: HIDModifier.leftGUI)
            } label: {
                Label("App Switcher", systemImage: "square.on.square")
            }
        }
        .buttonStyle(.bordered)
        .padding()
    }

    private func sendShortcut(keycode: UInt8, modifier: UInt8) {
        udpClient.send(.shortcut(keycode: keycode, modifier: modifier))
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            udpClient.send(.keyRelease(mode: .trackpad))
        }
    }
}
