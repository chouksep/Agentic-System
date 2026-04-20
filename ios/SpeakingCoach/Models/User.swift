import Foundation

struct User: Codable {
    let id: String
    let email: String
    let displayName: String
    let subscriptionTier: String
    let onboardingComplete: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case email
        case displayName = "display_name"
        case subscriptionTier = "subscription_tier"
        case onboardingComplete = "onboarding_complete"
    }
}

struct AuthResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let tokenType: String

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case tokenType = "token_type"
    }
}

struct CoachingProfile: Codable, Identifiable {
    let id: String
    let name: String
    let profileType: String
    let coachingFocus: [String: Bool]
    let instructions: String?
    let isActive: Bool
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case profileType = "profile_type"
        case coachingFocus = "coaching_focus"
        case instructions
        case isActive = "is_active"
        case createdAt = "created_at"
    }
}

struct CallRecord: Codable, Identifiable {
    let id: String
    let callType: String
    let externalParticipantName: String?
    let durationSeconds: Int
    let transcript: String?
    let audioS3Url: String?
    let startedAt: String
    let endedAt: String?
    let isArchived: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case callType = "call_type"
        case externalParticipantName = "external_participant_name"
        case durationSeconds = "duration_seconds"
        case transcript
        case audioS3Url = "audio_s3_url"
        case startedAt = "started_at"
        case endedAt = "ended_at"
        case isArchived = "is_archived"
    }
}
