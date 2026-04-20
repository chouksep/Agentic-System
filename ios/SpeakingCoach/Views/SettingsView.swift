import SwiftUI

struct SettingsView: View {
    var authManager: AuthManager

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Account")
                        .font(.headline)
                    Text(authManager.currentUser?.email ?? "user@example.com")
                        .foregroundColor(.gray)
                }
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(8)

                VStack(spacing: 12) {
                    NavigationLink(destination: EmptyView()) {
                        HStack {
                            Text("App Version")
                            Spacer()
                            Text("0.1.0")
                                .foregroundColor(.gray)
                        }
                        .padding()
                    }

                    Divider()

                    NavigationLink(destination: EmptyView()) {
                        HStack {
                            Text("Privacy Policy")
                            Spacer()
                            Image(systemName: "chevron.right")
                        }
                        .padding()
                    }
                }

                Spacer()

                Button(action: handleLogout) {
                    Text("Logout")
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.red)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
            }
            .padding()
            .navigationTitle("Settings")
        }
    }

    private func handleLogout() {
        authManager.logout()
    }
}

#Preview {
    SettingsView(authManager: AuthManager())
}
