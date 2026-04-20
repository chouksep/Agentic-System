import Foundation

@Observable
class AuthManager {
    @ObservationIgnored private let apiClient = APIClient.shared
    @ObservationIgnored private let userDefaults = UserDefaults.standard

    var isLoggedIn: Bool {
        userDefaults.string(forKey: "token") != nil
    }

    var currentUser: User?

    func login(email: String, password: String) async throws {
        let response = try await apiClient.login(email: email, password: password)
        userDefaults.set(response.accessToken, forKey: "token")
        userDefaults.set(response.refreshToken, forKey: "refreshToken")
        currentUser = try await apiClient.getProfile()
    }

    func register(email: String, password: String, displayName: String) async throws {
        let response = try await apiClient.register(email: email, password: password, displayName: displayName)
        userDefaults.set(response.accessToken, forKey: "token")
        userDefaults.set(response.refreshToken, forKey: "refreshToken")
        currentUser = try await apiClient.getProfile()
    }

    func logout() {
        userDefaults.removeObject(forKey: "token")
        userDefaults.removeObject(forKey: "refreshToken")
        currentUser = nil
        apiClient.token = nil
    }

    func loadStoredToken() {
        if let token = userDefaults.string(forKey: "token") {
            apiClient.token = token
        }
    }
}
