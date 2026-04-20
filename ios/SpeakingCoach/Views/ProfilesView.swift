import SwiftUI

struct ProfilesView: View {
    @State private var profiles: [CoachingProfile] = []
    @State private var isLoading = false

    var body: some View {
        NavigationStack {
            VStack {
                if profiles.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "slider.horizontal.3")
                            .font(.system(size: 48))
                            .foregroundColor(.gray)
                        Text("No Profiles Yet")
                            .font(.headline)
                        Text("Create your first coaching profile to get started")
                            .foregroundColor(.gray)
                    }
                } else {
                    List {
                        ForEach(profiles) { profile in
                            VStack(alignment: .leading) {
                                Text(profile.name)
                                    .fontWeight(.semibold)
                                Text(profile.profileType.capitalized)
                                    .font(.caption)
                                    .foregroundColor(.gray)
                            }
                        }
                    }
                }

                Button(action: {}) {
                    Label("Create Profile", systemImage: "plus.circle.fill")
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
                .padding()
            }
            .navigationTitle("Profiles")
            .onAppear(perform: loadProfiles)
        }
    }

    private func loadProfiles() {
        isLoading = true
        Task {
            do {
                profiles = try await APIClient.shared.getProfiles()
            } catch {
                print("Error loading profiles: \(error)")
            }
            isLoading = false
        }
    }
}

#Preview {
    ProfilesView()
}
