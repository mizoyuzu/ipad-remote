import UIKit

class HapticManager {
    private let impact = UIImpactFeedbackGenerator(style: .light)
    private let notification = UINotificationFeedbackGenerator()
    private let selection = UISelectionFeedbackGenerator()

    init() {
        impact.prepare()
        selection.prepare()
    }

    func tap() {
        impact.impactOccurred()
        impact.prepare()
    }

    func modeSwitch() {
        notification.notificationOccurred(.success)
    }

    func arrowKey() {
        selection.selectionChanged()
        selection.prepare()
    }

    func longPress() {
        let heavy = UIImpactFeedbackGenerator(style: .heavy)
        heavy.impactOccurred()
    }
}
