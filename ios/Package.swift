// swift-tools-version:5.9
import PackageDescription

// EtudeCore holds the platform-agnostic "brain": note math, pitch detection,
// score following and the lesson state machine. It has no UIKit/AVFoundation
// dependency, so it compiles and unit-tests on any Swift toolchain (including
// the Command Line Tools) — the SwiftUI iOS app links against it.
let package = Package(
    name: "EtudeCore",
    products: [
        .library(name: "EtudeCore", targets: ["EtudeCore"]),
        .executable(name: "EtudeVerify", targets: ["EtudeVerify"]),
    ],
    targets: [
        .target(name: "EtudeCore"),
        // XCTest suite — runs under full Xcode (`swift test`).
        .testTarget(name: "EtudeCoreTests", dependencies: ["EtudeCore"]),
        // Dependency-free checker — runs under Command Line Tools (`swift run EtudeVerify`).
        .executableTarget(name: "EtudeVerify", dependencies: ["EtudeCore"]),
    ]
)
