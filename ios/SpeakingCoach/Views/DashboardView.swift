import SwiftUI

struct DashboardView: View {
    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                Text("Welcome to Speaking Coach")
                    .font(.title)
                    .fontWeight(.bold)
                    .padding()

                VStack(spacing: 12) {
                    HStack {
                        VStack(alignment: .leading) {
                            Text("Total Calls")
                                .font(.caption)
                                .foregroundColor(.gray)
                            Text("0")
                                .font(.title2)
                                .fontWeight(.bold)
                        }
                        Spacer()
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)

                    HStack {
                        VStack(alignment: .leading) {
                            Text("Total Minutes")
                                .font(.caption)
                                .foregroundColor(.gray)
                            Text("0")
                                .font(.title2)
                                .fontWeight(.bold)
                        }
                        Spacer()
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                }

                Button(action: {}) {
                    Label("Start Call", systemImage: "phone.fill")
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }

                Spacer()
            }
            .navigationTitle("Dashboard")
        }
    }
}

#Preview {
    DashboardView()
}
