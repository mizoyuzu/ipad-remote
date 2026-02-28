import SwiftUI

struct ConnectionBar: View {
    let state: ConnectionState
    let onManualConnect: (String, UInt16) -> Void

    @State private var manualIP: String = ""
    @State private var showManualEntry = false

    var body: some View {
        HStack {
            Circle()
                .fill(state.isConnected ? Color.green : Color.red)
                .frame(width: 10, height: 10)

            Text(state.label)
                .font(.caption)
                .lineLimit(1)

            Spacer()

            Button("Manual IP") {
                showManualEntry.toggle()
            }
            .font(.caption)
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Color(.systemGroupedBackground))
        .alert("Enter RPi IP Address", isPresented: $showManualEntry) {
            TextField("192.168.x.x", text: $manualIP)
                .keyboardType(.decimalPad)
            Button("Connect") {
                if !manualIP.isEmpty {
                    onManualConnect(manualIP, 5005)
                }
            }
            Button("Cancel", role: .cancel) {}
        }
    }
}
