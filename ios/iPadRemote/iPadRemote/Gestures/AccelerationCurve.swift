import Foundation
import CoreGraphics

struct AccelerationCurve {
    /// Sensitivity multiplier (user-adjustable, default 1.0)
    var sensitivity: Double = 1.0

    /// Power curve exponent (1.0 = linear, 1.5 = moderate acceleration)
    let exponent: Double = 1.5

    /// Dead zone threshold to filter out jitter
    let deadZone: Double = 0.1

    /// Apply nonlinear acceleration to a raw delta value.
    /// Returns clamped Int8 value ready for packet encoding.
    func apply(rawDelta: CGFloat) -> Int8 {
        let speed = abs(Double(rawDelta))
        guard speed > deadZone else { return 0 }

        let accelerated = pow(speed, exponent) * sensitivity
        let signed = rawDelta > 0 ? accelerated : -accelerated

        // Clamp to Int8 range
        let clamped = max(-128.0, min(127.0, signed))
        return Int8(clamped)
    }

    /// Apply to a 2D delta (dx, dy) independently.
    func apply(dx: CGFloat, dy: CGFloat) -> (Int8, Int8) {
        (apply(rawDelta: dx), apply(rawDelta: dy))
    }
}
