import SwiftUI

struct TrackpadView: View {
    let udpClient: UDPClient
    let haptics: HapticManager

    @State private var acceleration = AccelerationCurve()
    @State private var lastDragLocation: CGPoint? = nil

    var body: some View {
        ZStack {
            // Base: UIKit gesture view for multi-touch support
            TrackpadGestureView(
                onDrag: handleDrag,
                onDragEnd: handleDragEnd,
                onTap: handleTap,
                onLongPress: handleLongPress,
                onTwoFingerScroll: handleTwoFingerScroll
            )

            // Visual overlay
            VStack(spacing: 8) {
                Image(systemName: "hand.point.up.left")
                    .font(.system(size: 48))
                Text("Trackpad")
                    .font(.title2)
                Text("Tap: Click  |  Long Press: Right Click")
                    .font(.caption)
                Text("2-finger Scroll")
                    .font(.caption)
            }
            .foregroundStyle(.tertiary)
            .allowsHitTesting(false)
        }
    }

    private func handleDrag(_ location: CGPoint) {
        if let last = lastDragLocation {
            let rawDx = location.x - last.x
            let rawDy = location.y - last.y
            let (dx, dy) = acceleration.apply(dx: rawDx, dy: rawDy)
            udpClient.send(.mouseMove(dx: dx, dy: dy))
        }
        lastDragLocation = location
    }

    private func handleDragEnd() {
        lastDragLocation = nil
    }

    private func handleTap() {
        haptics.tap()
        udpClient.send(.mouseMove(dx: 0, dy: 0, buttons: 0x01))
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            udpClient.send(.mouseMove(dx: 0, dy: 0, buttons: 0x00))
        }
    }

    private func handleLongPress() {
        haptics.longPress()
        udpClient.send(.mouseMove(dx: 0, dy: 0, buttons: 0x02))
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            udpClient.send(.mouseMove(dx: 0, dy: 0, buttons: 0x00))
        }
    }

    private func handleTwoFingerScroll(_ deltaY: CGFloat) {
        let wheel = Int8(clamping: Int(-deltaY))
        udpClient.send(.mouseMove(dx: 0, dy: 0, wheel: wheel))
    }
}

// MARK: - UIKit bridge for multi-touch gesture recognition

struct TrackpadGestureView: UIViewRepresentable {
    let onDrag: (CGPoint) -> Void
    let onDragEnd: () -> Void
    let onTap: () -> Void
    let onLongPress: () -> Void
    let onTwoFingerScroll: (CGFloat) -> Void

    func makeUIView(context: Context) -> UIView {
        let view = UIView()
        view.backgroundColor = .clear

        // Single-finger drag (mouse move)
        let pan = UIPanGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.handlePan(_:)))
        pan.minimumNumberOfTouches = 1
        pan.maximumNumberOfTouches = 1

        // Two-finger scroll
        let twoFingerPan = UIPanGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.handleTwoFingerPan(_:)))
        twoFingerPan.minimumNumberOfTouches = 2
        twoFingerPan.maximumNumberOfTouches = 2

        // Tap (left click)
        let tap = UITapGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.handleTap(_:)))
        tap.numberOfTouchesRequired = 1

        // Long press (right click)
        let longPress = UILongPressGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.handleLongPress(_:)))
        longPress.minimumPressDuration = 0.5

        // Let tap and long press coexist; tap requires long press to fail
        tap.require(toFail: longPress)

        view.addGestureRecognizer(pan)
        view.addGestureRecognizer(twoFingerPan)
        view.addGestureRecognizer(tap)
        view.addGestureRecognizer(longPress)

        return view
    }

    func updateUIView(_ uiView: UIView, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(
            onDrag: onDrag,
            onDragEnd: onDragEnd,
            onTap: onTap,
            onLongPress: onLongPress,
            onTwoFingerScroll: onTwoFingerScroll
        )
    }

    class Coordinator: NSObject {
        let onDrag: (CGPoint) -> Void
        let onDragEnd: () -> Void
        let onTap: () -> Void
        let onLongPress: () -> Void
        let onTwoFingerScroll: (CGFloat) -> Void

        private var lastTwoFingerY: CGFloat = 0

        init(onDrag: @escaping (CGPoint) -> Void,
             onDragEnd: @escaping () -> Void,
             onTap: @escaping () -> Void,
             onLongPress: @escaping () -> Void,
             onTwoFingerScroll: @escaping (CGFloat) -> Void) {
            self.onDrag = onDrag
            self.onDragEnd = onDragEnd
            self.onTap = onTap
            self.onLongPress = onLongPress
            self.onTwoFingerScroll = onTwoFingerScroll
        }

        @objc func handlePan(_ gesture: UIPanGestureRecognizer) {
            switch gesture.state {
            case .changed:
                let location = gesture.location(in: gesture.view)
                onDrag(location)
            case .ended, .cancelled:
                onDragEnd()
            default:
                break
            }
        }

        @objc func handleTwoFingerPan(_ gesture: UIPanGestureRecognizer) {
            switch gesture.state {
            case .began:
                lastTwoFingerY = gesture.location(in: gesture.view).y
            case .changed:
                let currentY = gesture.location(in: gesture.view).y
                let deltaY = currentY - lastTwoFingerY
                onTwoFingerScroll(deltaY)
                lastTwoFingerY = currentY
            default:
                break
            }
        }

        @objc func handleTap(_ gesture: UITapGestureRecognizer) {
            if gesture.state == .ended {
                onTap()
            }
        }

        @objc func handleLongPress(_ gesture: UILongPressGestureRecognizer) {
            if gesture.state == .began {
                onLongPress()
            }
        }
    }
}
