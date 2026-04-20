import SwiftUI

struct RegisterView: View {
    @State private var displayName = ""
    @State private var email = ""
    @State private var password = ""
    @State private var errorMessage = ""
    @State private var isLoading = false
    @Environment(\.dismiss) var dismiss

    var authManager: AuthManager

    var body: some View {
        VStack(spacing: 24) {
            VStack(spacing: 8) {
                Text("🎤")
                    .font(.system(size: 48))
                Text("Create Account")
                    .font(.title)
                    .fontWeight(.bold)
            }

            VStack(spacing: 16) {
                TextField("Display Name", text: $displayName)
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)

                TextField("Email", text: $email)
                    .textContentType(.emailAddress)
                    .keyboardType(.emailAddress)
                    .autocapitalization(.none)
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)

                SecureField("Password", text: $password)
                    .textContentType(.newPassword)
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
            }

            if !errorMessage.isEmpty {
                Text(errorMessage)
                    .foregroundColor(.red)
                    .font(.caption)
            }

            Button(action: handleRegister) {
                if isLoading {
                    ProgressView()
                        .tint(.white)
                } else {
                    Text("Register")
                }
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(Color.blue)
            .foregroundColor(.white)
            .cornerRadius(8)
            .disabled(isLoading)

            Spacer()
        }
        .padding()
        .navigationBackButtonHidden(false)
    }

    private func handleRegister() {
        errorMessage = ""
        isLoading = true

        Task {
            do {
                try await authManager.register(email: email, password: password, displayName: displayName)
            } catch {
                errorMessage = "Registration failed: \(error.localizedDescription)"
            }
            isLoading = false
        }
    }
}

#Preview {
    NavigationStack {
        RegisterView(authManager: AuthManager())
    }
}
