import Darwin
import Foundation

@MainActor
final class PythonRuntime: ObservableObject {
    static let shared = PythonRuntime()

    @Published private(set) var isAvailable = false
    @Published private(set) var status = "Python 3.8 런타임을 찾는 중"
    @Published private(set) var loadedExtractors = 0
    @Published private(set) var failedExtractors = 0

    private var started = false
    private var library: DynamicPythonLibrary?

    private init() {}

    func startIfAvailable() {
        guard !started else { return }
        started = true

        guard let pythonRoot = Bundle.main.resourceURL?.appendingPathComponent("PythonApp"),
              let pythonHome = Bundle.main.resourceURL?.appendingPathComponent("python"),
              FileManager.default.fileExists(atPath: pythonRoot.path),
              FileManager.default.fileExists(atPath: pythonHome.path)
        else {
            status = "IPA에 PythonApp 또는 Python 표준 라이브러리가 없습니다."
            return
        }

        do {
            let library = try DynamicPythonLibrary.load()
            self.library = library

            setenv("PYTHONHOME", pythonHome.path, 1)
            let paths = [
                pythonRoot.appendingPathComponent("ios_compat").path,
                pythonRoot.path,
                pythonRoot.appendingPathComponent("vendor").path,
                pythonRoot.appendingPathComponent("original_pyc.zip").path
            ]
            setenv("PYTHONPATH", paths.joined(separator: ":"), 1)
            setenv("PYTHONDONTWRITEBYTECODE", "1", 1)
            setenv("PYTHONNOUSERSITE", "1", 1)

            library.initialize()
            guard library.isInitialized() != 0 else {
                status = "Py_Initialize 실패"
                return
            }

            guard library.run("import sys; import ios_bridge") == 0 else {
                library.printError?()
                status = "ios_bridge 또는 Python 의존성 로드 실패"
                return
            }

            isAvailable = true
            status = "Python 3.8 레거시 추출기 엔진 준비됨"
            Task { await refreshDiagnostics() }
        } catch {
            status = error.localizedDescription
        }
    }

    func resolve(_ url: URL) async throws -> ResolvedMedia {
        guard let library, isAvailable else {
            throw ResolverError.pythonUnavailable(status)
        }

        let options: [String: Any] = [
            "max_resolution": UserDefaults.standard.integer(forKey: "maxResolution"),
            "prefer_mp4": UserDefaults.standard.bool(forKey: "preferMP4")
        ]
        let optionsData = try JSONSerialization.data(withJSONObject: options)
        let optionsJSON = String(data: optionsData, encoding: .utf8) ?? "{}"
        let output = try await runJSON(
            library: library,
            function: "resolve_json",
            arguments: [url.absoluteString, optionsJSON]
        )
        guard let data = output.data(using: .utf8) else {
            throw ResolverError.invalidResponse
        }
        return try JSONDecoder().decode(ResolvedMedia.self, from: data)
    }

    func refreshDiagnostics() async {
        guard let library, isAvailable else { return }
        do {
            let output = try await runJSON(
                library: library,
                function: "probe_json",
                arguments: []
            )
            if let data = output.data(using: .utf8),
               let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                loadedExtractors = object["loaded"] as? Int ?? 0
                failedExtractors = object["failed"] as? Int ?? 0
            }
        } catch {
            status = "추출기 진단 실패: \(error.localizedDescription)"
        }
    }

    func runUserScript(at url: URL) async throws -> String {
        guard let library, isAvailable else {
            throw ResolverError.pythonUnavailable(status)
        }
        return try await runJSON(
            library: library,
            function: "run_user_script_json",
            arguments: [url.path]
        )
    }

    private func runJSON(
        library: DynamicPythonLibrary,
        function: String,
        arguments: [String]
    ) async throws -> String {
        let outputURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("python-\(UUID().uuidString).json")
        let argumentList = arguments.map(Self.pythonLiteral).joined(separator: ", ")
        let outputLiteral = Self.pythonLiteral(outputURL.path)
        let code = """
        import ios_bridge
        _hitomi_result = ios_bridge.\(function)(\(argumentList))
        with open(\(outputLiteral), 'w', encoding='utf-8') as _hitomi_file:
            _hitomi_file.write(_hitomi_result)
        """

        let result: Int32 = await Task.detached(priority: .userInitiated) {
            let state = library.ensureGIL()
            defer { library.releaseGIL(state) }
            let result = library.run(code)
            if result != 0 { library.printError?() }
            return result
        }.value

        guard result == 0 else {
            throw ResolverError.pythonUnavailable("Python 함수 \(function) 실행 실패")
        }
        defer { try? FileManager.default.removeItem(at: outputURL) }
        return try String(contentsOf: outputURL, encoding: .utf8)
    }

    private static func pythonLiteral(_ value: String) -> String {
        guard let data = try? JSONSerialization.data(withJSONObject: [value]),
              let array = String(data: data, encoding: .utf8),
              array.count >= 2
        else { return "''" }
        return String(array.dropFirst().dropLast())
    }
}

private enum DynamicPythonError: LocalizedError {
    case frameworkMissing
    case symbolMissing(String)

    var errorDescription: String? {
        switch self {
        case .frameworkMissing:
            "Python 런타임 심볼을 앱 실행 파일이나 Frameworks 폴더에서 찾지 못했습니다."
        case .symbolMissing(let name):
            "Python 런타임에 \(name) 심볼이 없습니다."
        }
    }
}

private final class DynamicPythonLibrary: @unchecked Sendable {
    typealias Initialize = @convention(c) () -> Void
    typealias IsInitialized = @convention(c) () -> Int32
    typealias RunSimpleString = @convention(c) (UnsafePointer<CChar>?) -> Int32
    typealias GILEnsure = @convention(c) () -> Int32
    typealias GILRelease = @convention(c) (Int32) -> Void
    typealias PrintError = @convention(c) () -> Void

    let initialize: Initialize
    let isInitialized: IsInitialized
    let runSimpleString: RunSimpleString
    let ensureGIL: GILEnsure
    let releaseGIL: GILRelease
    let printError: PrintError?
    private let handle: UnsafeMutableRawPointer
    private let shouldClose: Bool

    private init(handle: UnsafeMutableRawPointer, shouldClose: Bool = true) throws {
        self.handle = handle
        self.shouldClose = shouldClose
        self.initialize = try Self.symbol("Py_Initialize", handle: handle)
        self.isInitialized = try Self.symbol("Py_IsInitialized", handle: handle)
        self.runSimpleString = try Self.symbol("PyRun_SimpleString", handle: handle)
        self.ensureGIL = try Self.symbol("PyGILState_Ensure", handle: handle)
        self.releaseGIL = try Self.symbol("PyGILState_Release", handle: handle)
        self.printError = Self.optionalSymbol("PyErr_Print", handle: handle)
    }

    deinit {
        if shouldClose { dlclose(handle) }
    }

    static func load() throws -> DynamicPythonLibrary {
        if let handle = dlopen(nil, RTLD_NOW | RTLD_GLOBAL) {
            do {
                return try DynamicPythonLibrary(handle: handle, shouldClose: false)
            } catch {
                // Fall through to a dynamically embedded framework for
                // compatibility with alternative runtime packages.
            }
        }

        let candidates = [
            Bundle.main.privateFrameworksPath.map { "\($0)/Python.framework/Python" },
            Bundle.main.bundlePath.appending("/Frameworks/Python.framework/Python"),
            "Python.framework/Python"
        ].compactMap { $0 }

        for path in candidates {
            if let handle = dlopen(path, RTLD_NOW | RTLD_GLOBAL) {
                return try DynamicPythonLibrary(handle: handle)
            }
        }
        throw DynamicPythonError.frameworkMissing
    }

    func run(_ code: String) -> Int32 {
        code.withCString { runSimpleString($0) }
    }

    private static func symbol<T>(_ name: String, handle: UnsafeMutableRawPointer) throws -> T {
        guard let value = dlsym(handle, name) else {
            throw DynamicPythonError.symbolMissing(name)
        }
        return unsafeBitCast(value, to: T.self)
    }

    private static func optionalSymbol<T>(_ name: String, handle: UnsafeMutableRawPointer) -> T? {
        guard let value = dlsym(handle, name) else { return nil }
        return unsafeBitCast(value, to: T.self)
    }
}
