import Foundation
import CallKit
import AVFoundation

@Observable
class CallManager: NSObject, CXCallObserverDelegate {
    @ObservationIgnored private let callObserver = CXCallObserver()
    @ObservationIgnored private let apiClient = APIClient.shared

    var activeCallId: String?
    var isCallActive: Bool = false
    var callDuration: Int = 0

    @ObservationIgnored private var durationTimer: Timer?
    @ObservationIgnored private var audioEngine: AVAudioEngine?

    override init() {
        super.init()
        callObserver.setDelegate(self, queue: .main)
        setupAudioEngine()
    }

    private func setupAudioEngine() {
        audioEngine = AVAudioEngine()
        let audioSession = AVAudioSession.sharedInstance()
        do {
            try audioSession.setCategory(.record, mode: .default, options: [.duckOthers])
            try audioSession.setActive(true, options: .notifyOthersOnDeactivation)
        } catch {
            print("Audio session setup error: \(error)")
        }
    }

    func callObserver(_ callObserver: CXCallObserver, callChanged call: CXCall) {
        if call.hasConnected && !isCallActive {
            startCall()
        } else if call.hasEnded {
            endCall()
        }
    }

    func startCall() {
        guard !isCallActive else { return }
        isCallActive = true
        callDuration = 0

        durationTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.callDuration += 1
        }

        do {
            try audioEngine?.start()
        } catch {
            print("Audio engine start error: \(error)")
        }
    }

    func endCall() {
        guard isCallActive else { return }
        isCallActive = false
        durationTimer?.invalidate()
        durationTimer = nil

        audioEngine?.stop()

        if let callId = activeCallId {
            Task {
                do {
                    _ = try await apiClient.endCall(callId: callId)
                } catch {
                    print("Error ending call: \(error)")
                }
            }
        }
        activeCallId = nil
        callDuration = 0
    }

    func initiateCall(profileId: String) async throws {
        do {
            let response = try await apiClient.startCall(profileId: profileId, callType: "phone")
            activeCallId = response.callId
            print("Call initiated: \(response.callId)")
        } catch {
            throw error
        }
    }

    deinit {
        durationTimer?.invalidate()
    }
}
