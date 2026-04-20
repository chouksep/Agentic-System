import SwiftUI

struct AnalyticsView: View {
    var body: some View {
        NavigationStack {
            VStack {
                VStack(spacing: 16) {
                    HStack {
                        VStack(alignment: .leading) {
                            Text("Improvement")
                                .font(.caption)
                                .foregroundColor(.gray)
                            Text("Coming Soon")
                                .font(.title2)
                                .fontWeight(.bold)
                        }
                        Spacer()
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                }
                .padding()

                Spacer()
            }
            .navigationTitle("Analytics")
        }
    }
}

#Preview {
    AnalyticsView()
}
