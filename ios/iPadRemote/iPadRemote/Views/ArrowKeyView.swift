import SwiftUI

struct ArrowKeyView: View {
    let udpClient: UDPClient
    let haptics: HapticManager

    @State private var inertiaEngine = InertiaEngine()

    var body: some View {
        Color.clear
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 20)
                    .onEnded { value in
                        let dx = value.translation.width
                        let dy = value.translation.height

                        // Determine dominant direction
                        let keycode: UInt8
                        if abs(dx) > abs(dy) {
                            keycode = dx > 0 ? HIDKeycode.rightArrow : HIDKeycode.leftArrow
                        } else {
                            keycode = dy > 0 ? HIDKeycode.downArrow : HIDKeycode.upArrow
                        }

                        haptics.arrowKey()
                        sendKeyPress(keycode)

                        // Inertial repeat based on swipe velocity
                        let velocity = max(
                            abs(value.predictedEndTranslation.width - value.translation.width),
                            abs(value.predictedEndTranslation.height - value.translation.height)
                        )
                        if velocity > 100 {
                            let repeatRate = velocity / 100
                            inertiaEngine.start(initialVelocity: repeatRate) { vel in
                                if abs(vel) >= 1 {
                                    haptics.arrowKey()
                                    sendKeyPress(keycode)
                                }
                            }
                        }
                    }
            )
            .simultaneousGesture(
                TapGesture()
                    .onEnded {
                        haptics.tap()
                        sendKeyPress(HIDKeycode.enter)
                    }
            )
            .overlay {
                VStack(spacing: 16) {
                    Image(systemName: "arrow.up.arrow.down.arrow.left.arrow.right")
                        .font(.system(size: 48))
                    Text("Arrow Keys")
                        .font(.title2)
                    Text("Swipe: Arrow Keys\nTap: Enter")
                        .font(.caption)
                        .multilineTextAlignment(.center)
                }
                .foregroundStyle(.tertiary)
                .allowsHitTesting(false)
            }
    }

    private func sendKeyPress(_ keycode: UInt8) {
        udpClient.send(.arrowKey(keycode))
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            udpClient.send(.keyRelease(mode: .arrow))
        }
    }
}
