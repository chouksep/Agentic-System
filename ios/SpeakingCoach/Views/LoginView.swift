import SwiftUI

struct LoginView: View {
    @State private var email = ""
    @State private var password = ""
    @State private var errorMessage = ""
    @State private var isLoading = false
    @State private var showRegister = false

    var authManager: AuthManager

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                VStack(spacing: 8) {
                    Text("🎤")
                        .font(.system(size: 48))
                    Text("Speaking Coach")
                        .font(.title)
                        .fontWeight(.bold)
                }

                VStack(spacing: 16) {
                    TextField("Email", text: $email)
                        .textContentType(.emailAddress)
                        .keyboardType(.emailAddress)
                        .autocapitalization(.none)
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(8)

                    SecureField("Password", text: $password)
                        .textContentType(.password)
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(8)
                }

                if !errorMessage.isEmpty {
                    Text(errorMessage)
                        .foregroundColor(.red)
                        .font(.caption)
                }

                Button(action: handleLogin) {
                    if isLoading {
                        ProgressView()
                            .tint(.white)
                    } else {
                        Text("Login")
                    }
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(8)
                .disabled(isLoading)

                Spacer()

                HStack {
                    Text("Don't have an account?")
                    NavigationLink("Register", destination: RegisterView(authManager: authManager))
                }
            }
            .padding()
        }
    }

    private func handleLogin() {
        errorMessage = ""
        isLoading = true

        Task {
            do {
                try await authManager.login(email: email, password: password)
            } catch {
                errorMessage = "Login failed: \(error.localizedDescription)"
            }
            isLoading = false
        }
    }
}

#Preview {
    LoginView(authManager: AuthManager())
}
