import Foundation

enum InputMode: UInt8, CaseIterable, Identifiable {
    case trackpad = 0
    case scroll = 1
    case arrow = 2

    var id: UInt8 { rawValue }

    var label: String {
        switch self {
        case .trackpad: "Trackpad"
        case .scroll:   "Scroll"
        case .arrow:    "Arrow Keys"
        }
    }

    var icon: String {
        switch self {
        case .trackpad: "hand.point.up.left"
        case .scroll:   "arrow.up.arrow.down"
        case .arrow:    "arrow.up.arrow.down.arrow.left.arrow.right"
        }
    }
}
