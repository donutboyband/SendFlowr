namespace SendFlowr.Connectors.Utilities;

/// <summary>
/// UUIDv7 Generator - Time-ordered UUIDs for better database performance
/// </summary>
public static class UuidV7
{
    /// <summary>
    /// Generate a new UUIDv7 (time-ordered UUID)
    /// </summary>
    public static Guid NewGuid()
    {
        // Get Unix timestamp in milliseconds
        var timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        
        // UUIDv7 format: timestamp(48 bits) + version(4 bits) + random(12 bits) + variant(2 bits) + random(62 bits)
        var bytes = new byte[16];
        
        // Timestamp (48 bits = 6 bytes) in big-endian
        bytes[0] = (byte)((timestamp >> 40) & 0xFF);
        bytes[1] = (byte)((timestamp >> 32) & 0xFF);
        bytes[2] = (byte)((timestamp >> 24) & 0xFF);
        bytes[3] = (byte)((timestamp >> 16) & 0xFF);
        bytes[4] = (byte)((timestamp >> 8) & 0xFF);
        bytes[5] = (byte)(timestamp & 0xFF);
        
        // Random data for rest
        Random.Shared.NextBytes(bytes.AsSpan(6));
        
        // Set version (4 bits) to 7
        bytes[6] = (byte)((bytes[6] & 0x0F) | 0x70);
        
        // Set variant (2 bits) to RFC 4122
        bytes[8] = (byte)((bytes[8] & 0x3F) | 0x80);
        
        return new Guid(bytes);
    }
}
