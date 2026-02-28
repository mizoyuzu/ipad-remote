import Foundation

struct Packet {
    let mode: InputMode
    let flags: UInt8
    let dx: Int8
    let dy: Int8
    let wheel: Int8
    let keycode: UInt8

    func toData() -> Data {
        var data = Data(count: 6)
        data[0] = mode.rawValue
        data[1] = flags
        data[2] = UInt8(bitPattern: dx)
        data[3] = UInt8(bitPattern: dy)
        data[4] = UInt8(bitPattern: wheel)
        data[5] = keycode
        return data
    }

    // MARK: - Convenience constructors

    static func mouseMove(dx: Int8, dy: Int8, buttons: UInt8 = 0, wheel: Int8 = 0) -> Packet {
        Packet(mode: .trackpad, flags: buttons, dx: dx, dy: dy, wheel: wheel, keycode: 0)
    }

    static func scroll(amount: Int8) -> Packet {
        Packet(mode: .scroll, flags: 0, dx: 0, dy: 0, wheel: amount, keycode: 0)
    }

    static func arrowKey(_ keycode: UInt8, modifier: UInt8 = 0) -> Packet {
        Packet(mode: .arrow, flags: modifier, dx: 0, dy: 0, wheel: 0, keycode: keycode)
    }

    static func keyRelease(mode: InputMode) -> Packet {
        Packet(mode: mode, flags: 0, dx: 0, dy: 0, wheel: 0, keycode: 0)
    }

    static func shortcut(keycode: UInt8, modifier: UInt8) -> Packet {
        Packet(mode: .trackpad, flags: modifier, dx: 0, dy: 0, wheel: 0, keycode: keycode)
    }
}

// MARK: - USB HID Keycode constants

enum HIDKeycode {
    static let enter: UInt8      = 0x28
    static let rightArrow: UInt8 = 0x4F
    static let leftArrow: UInt8  = 0x50
    static let downArrow: UInt8  = 0x51
    static let upArrow: UInt8    = 0x52
    static let keyH: UInt8       = 0x0B
    static let tab: UInt8        = 0x2B
}

enum HIDModifier {
    static let leftGUI: UInt8 = 0x08  // Cmd key
}
