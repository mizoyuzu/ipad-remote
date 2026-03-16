import Foundation
import UIKit

class InertiaEngine {
    private var velocity: Double = 0
    private var displayLink: CADisplayLink?
    private var onTick: ((Double) -> Void)?

    /// Decay factor applied every tick (0.85 = moderately fast decay)
    let decay: Double = 0.85

    /// Minimum velocity threshold before stopping
    let threshold: Double = 0.5

    func start(initialVelocity: Double, onTick: @escaping (Double) -> Void) {
        stop()
        self.velocity = initialVelocity
        self.onTick = onTick

        let link = CADisplayLink(target: self, selector: #selector(tick))
        link.preferredFrameRateRange = CAFrameRateRange(minimum: 60, maximum: 120)
        link.add(to: .current, forMode: .common)
        self.displayLink = link
    }

    @objc private func tick() {
        velocity *= decay

        if abs(velocity) < threshold {
            stop()
            return
        }

        onTick?(velocity)
    }

    func stop() {
        displayLink?.invalidate()
        displayLink = nil
        onTick = nil
        velocity = 0
    }

    var isActive: Bool { displayLink != nil }
}
