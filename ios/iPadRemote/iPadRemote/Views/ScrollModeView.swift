import SwiftUI

struct ScrollModeView: View {
    let udpClient: UDPClient
    let haptics: HapticManager

    @State private var inertiaEngine = InertiaEngine()
    @State private var lastDragY: CGFloat? = nil

    var body: some View {
        Color.clear
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 1)
                    .onChanged { value in
                        inertiaEngine.stop()

                        if let lastY = lastDragY {
                            let rawDy = value.location.y - lastY
                            // Invert: drag up = scroll up (negative wheel)
                            let wheel = Int8(clamping: Int(-rawDy))
                            if wheel != 0 {
                                udpClient.send(.scroll(amount: wheel))
                            }
                        }
                        lastDragY = value.location.y
                    }
                    .onEnded { value in
                        lastDragY = nil

                        // Start inertial scroll based on predicted velocity
                        let velocity = value.predictedEndTranslation.height
                            - value.translation.height

                        if abs(velocity) > 5 {
                            inertiaEngine.start(initialVelocity: -velocity * 0.3) { vel in
                                let wheel = Int8(clamping: Int(vel))
                                if wheel != 0 {
                                    udpClient.send(.scroll(amount: wheel))
                                }
                            }
                        }
                    }
            )
            .overlay {
                VStack(spacing: 12) {
                    Image(systemName: "arrow.up")
                        .font(.title)
                    Text("Scroll")
                        .font(.title2)
                    Image(systemName: "arrow.down")
                        .font(.title)
                }
                .foregroundStyle(.tertiary)
                .allowsHitTesting(false)
            }
    }
}
