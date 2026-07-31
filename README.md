# IPA Maker — Hitomi Swift Full

이 저장소는 복원된 Windows/Python 다운로드 프로그램을 iPhone·iPad용 SwiftUI 앱으로 포팅하고, GitHub Actions의 macOS runner에서 **unsigned IPA**로 빌드합니다.

## 자동 빌드

`main` 브랜치에 push하거나 Actions에서 `Build unsigned IPA`를 수동 실행하면 다음 artifact가 생성됩니다.

```text
HitomiSwiftFull-unsigned-ipa/HitomiSwiftFull-unsigned.ipa
```

이 IPA는 코드 서명이 없으므로 SideStore, AltStore, Sideloadly 등의 도구에서 본인 인증서로 서명한 뒤 설치해야 합니다.

## 저장소 구조

GitHub API 업로드 제한을 피하기 위해 소스는 `bundle/` 아래 Base64 ZIP 조각으로 저장합니다. 워크플로가 `bootstrap_source.py`를 실행해 Swift 프로젝트를 복원한 다음 XcodeGen과 Xcode로 빌드합니다.

현재 GitHub 빌드는 네이티브 SwiftUI, 직접 다운로드, 일반 HTML 추출, 비암호화 HLS, 기본 DASH, 로그인 WebView, 쿠키, 로컬 API 기능을 포함합니다. 대용량 Python 3.8 바이트코드와 Python/FFmpeg/libtorrent XCFramework는 아직 저장소 번들에 포함하지 않았습니다.
