import Foundation

class APIClient {
    static let shared = APIClient()

    private let baseURL = URL(string: "http://localhost:8000/api")!
    var token: String?

    private init() {}

    enum APIError: Error {
        case invalidResponse
        case decodingError
        case networkError(Error)
        case unauthorized
        case serverError(String)
    }

    func request<T: Decodable>(
        _ endpoint: String,
        method: String = "GET",
        body: Encodable? = nil
    ) async throws -> T {
        let url = baseURL.appendingPathComponent(endpoint)
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        if let token = token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let body = body {
            request.httpBody = try JSONEncoder().encode(body)
        }

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            if httpResponse.statusCode == 401 {
                throw APIError.unauthorized
            }
            throw APIError.serverError("HTTP \(httpResponse.statusCode)")
        }

        let decoder = JSONDecoder()
        return try decoder.decode(T.self, from: data)
    }

    func login(email: String, password: String) async throws -> AuthResponse {
        struct LoginRequest: Encodable {
            let email: String
            let password: String
        }

        let response: AuthResponse = try await request(
            "auth/login",
            method: "POST",
            body: LoginRequest(email: email, password: password)
        )
        self.token = response.accessToken
        return response
    }

    func register(email: String, password: String, displayName: String) async throws -> AuthResponse {
        struct RegisterRequest: Encodable {
            let email: String
            let password: String
            let display_name: String
        }

        let response: AuthResponse = try await request(
            "auth/register",
            method: "POST",
            body: RegisterRequest(email: email, password: password, display_name: displayName)
        )
        self.token = response.accessToken
        return response
    }

    func getProfile() async throws -> User {
        try await request("auth/me")
    }

    func startCall(profileId: String, callType: String) async throws -> CallStartResponse {
        struct StartCallRequest: Encodable {
            let profile_id: String
            let call_type: String
            let external_participant_name: String? = nil
        }

        try await request(
            "calls/start",
            method: "POST",
            body: StartCallRequest(profile_id: profileId, call_type: callType)
        )
    }

    func endCall(callId: String) async throws -> EndCallResponse {
        try await request(
            "calls/\(callId)/end",
            method: "POST"
        )
    }

    func getProfiles() async throws -> [CoachingProfile] {
        struct ProfilesResponse: Decodable {
            let data: [CoachingProfile]
        }
        let response: ProfilesResponse = try await request("profiles")
        return response.data
    }
}

struct CallStartResponse: Decodable {
    let callId: String
    let startedAt: String

    enum CodingKeys: String, CodingKey {
        case callId = "call_id"
        case startedAt = "started_at"
    }
}

struct EndCallResponse: Decodable {
    let callId: String
    let durationSeconds: Int
    let endedAt: String

    enum CodingKeys: String, CodingKey {
        case callId = "call_id"
        case durationSeconds = "duration_seconds"
        case endedAt = "ended_at"
    }
}
