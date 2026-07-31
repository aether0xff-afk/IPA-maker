import Foundation
import SwiftUI

@MainActor
final class AppModel: ObservableObject {
    @Published var pendingURL: URL?
    @Published var lastError: String?
    @Published var isResolving = false
    @Published var resolvedPreview: ResolvedMedia?

    let downloads = DownloadCoordinator.shared
    let resolver = ResolverService()
    let cookies = CookieVault.shared
    let python = PythonRuntime.shared
    var localServer = LocalAPIServer.shared
    let plugins = PluginManager.shared

    init() {
        downloads.restore()
        plugins.reload()
        _ = TorrentEngine.shared
    }

    func resolve(_ text: String) async {
        let value = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: value) else {
            lastError = "올바른 URL이 아닙니다."
            return
        }

        isResolving = true
        defer { isResolving = false }

        do {
            resolvedPreview = try await resolver.resolve(url)
            lastError = nil
        } catch {
            resolvedPreview = nil
            lastError = error.localizedDescription
        }
    }

    func queue(_ media: ResolvedMedia) {
        downloads.enqueue(media)
        resolvedPreview = nil
    }

    func resolveAndQueue(_ text: String) async {
        await resolve(text)
        if let resolvedPreview {
            queue(resolvedPreview)
        }
    }
}
