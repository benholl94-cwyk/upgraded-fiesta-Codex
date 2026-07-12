#!/usr/bin/env swift
import Foundation
#if canImport(CryptoKit)
import CryptoKit
#endif

struct DeviceInfo: Codable {
    let schemaVersion: String
    let timestamp: String
    let host: String
    let os: String
    let cpuCores: Int
    let physicalMemoryBytes: UInt64
    let physicalMemoryGB: Double
    let uptimeSeconds: TimeInterval
    let uptimeHours: Double
}

struct DeviceManifest: Codable {
    let manifestVersion: String
    let device: DeviceInfo
    let integrityHash: String
}

enum DeviceInfoError: Error {
    case encodingFailed
}

func collectDeviceInfo() -> DeviceInfo {
    let process = ProcessInfo.processInfo

    return DeviceInfo(
        schemaVersion: "1.0.0",
        timestamp: ISO8601DateFormatter().string(from: Date()),
        host: process.hostName,
        os: process.operatingSystemVersionString,
        cpuCores: process.processorCount,
        physicalMemoryBytes: process.physicalMemory,
        physicalMemoryGB: Double(process.physicalMemory) / 1_073_741_824,
        uptimeSeconds: process.systemUptime,
        uptimeHours: process.systemUptime / 3600
    )
}

func encodeJSON<T: Codable>(_ value: T) throws -> Data {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [
        .prettyPrinted,
        .sortedKeys,
    ]

    return try encoder.encode(value)
}

func rotateRight(_ value: UInt32, by shift: UInt32) -> UInt32 {
    (value >> shift) | (value << (32 - shift))
}

func calculateSHA256(_ data: Data) -> String {
#if canImport(CryptoKit)
    let hash = SHA256.hash(data: data)
    return hash.map { String(format: "%02x", $0) }.joined()
#else
    let constants: [UInt32] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
        0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
        0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
        0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
        0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
        0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
        0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
        0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
        0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ]

    var message = [UInt8](data)
    let bitLength = UInt64(message.count) * 8
    message.append(0x80)
    while message.count % 64 != 56 {
        message.append(0)
    }
    message += (0..<8).reversed().map { UInt8((bitLength >> UInt64($0 * 8)) & 0xff) }

    var hash: [UInt32] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
        0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ]

    for chunkStart in stride(from: 0, to: message.count, by: 64) {
        let chunk = Array(message[chunkStart..<chunkStart + 64])
        var schedule = [UInt32](repeating: 0, count: 64)

        for index in 0..<16 {
            let offset = index * 4
            schedule[index] = (UInt32(chunk[offset]) << 24)
                | (UInt32(chunk[offset + 1]) << 16)
                | (UInt32(chunk[offset + 2]) << 8)
                | UInt32(chunk[offset + 3])
        }

        for index in 16..<64 {
            let s0 = rotateRight(schedule[index - 15], by: 7)
                ^ rotateRight(schedule[index - 15], by: 18)
                ^ (schedule[index - 15] >> 3)
            let s1 = rotateRight(schedule[index - 2], by: 17)
                ^ rotateRight(schedule[index - 2], by: 19)
                ^ (schedule[index - 2] >> 10)
            schedule[index] = schedule[index - 16]
                &+ s0
                &+ schedule[index - 7]
                &+ s1
        }

        var a = hash[0]
        var b = hash[1]
        var c = hash[2]
        var d = hash[3]
        var e = hash[4]
        var f = hash[5]
        var g = hash[6]
        var h = hash[7]

        for index in 0..<64 {
            let s1 = rotateRight(e, by: 6) ^ rotateRight(e, by: 11) ^ rotateRight(e, by: 25)
            let choice = (e & f) ^ (~e & g)
            let temp1 = h &+ s1 &+ choice &+ constants[index] &+ schedule[index]
            let s0 = rotateRight(a, by: 2) ^ rotateRight(a, by: 13) ^ rotateRight(a, by: 22)
            let majority = (a & b) ^ (a & c) ^ (b & c)
            let temp2 = s0 &+ majority

            h = g
            g = f
            f = e
            e = d &+ temp1
            d = c
            c = b
            b = a
            a = temp1 &+ temp2
        }

        hash[0] = hash[0] &+ a
        hash[1] = hash[1] &+ b
        hash[2] = hash[2] &+ c
        hash[3] = hash[3] &+ d
        hash[4] = hash[4] &+ e
        hash[5] = hash[5] &+ f
        hash[6] = hash[6] &+ g
        hash[7] = hash[7] &+ h
    }

    return hash.map { String(format: "%08x", $0) }.joined()
#endif
}

func createManifest() throws -> DeviceManifest {
    let device = collectDeviceInfo()
    let deviceData = try encodeJSON(device)

    return DeviceManifest(
        manifestVersion: "1.0.0",
        device: device,
        integrityHash: calculateSHA256(deviceData)
    )
}

func exportManifest() {
    do {
        let manifest = try createManifest()
        let data = try encodeJSON(manifest)

        guard let json = String(data: data, encoding: .utf8) else {
            throw DeviceInfoError.encodingFailed
        }

        print(json)
    } catch {
        print("""
        {
          "error": "manifest_export_failed",
          "details": "\(error.localizedDescription)"
        }
        """)
    }
}

exportManifest()
