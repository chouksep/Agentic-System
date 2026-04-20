import SwiftUI

@main
struct SpeakingCoachApp: App {
    @State private var authManager = AuthManager()

    var body: some Scene {
        WindowGroup {
            if authManager.isLoggedIn {
                TabView {
                    DashboardView()
                        .tabItem {
                            Label("Dashboard", systemImage: "house.fill")
                        }

                    ProfilesView()
                        .tabItem {
                            Label("Profiles", systemImage: "slider.horizontal.3")
                        }

                    AnalyticsView()
                        .tabItem {
                            Label("Analytics", systemImage: "chart.bar.fill")
                        }

                    SettingsView(authManager: authManager)
                        .tabItem {
                            Label("Settings", systemImage: "gear")
                        }
                }
            } else {
                LoginView(authManager: authManager)
            }
        }
    }
}
