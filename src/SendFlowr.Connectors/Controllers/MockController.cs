using Microsoft.AspNetCore.Mvc;
using SendFlowr.Connectors.Models;
using SendFlowr.Connectors.Services;
using System.Text.Json.Serialization;

namespace SendFlowr.Connectors.Controllers;

[ApiController]
[Route("api/[controller]")]
public class MockController : ControllerBase
{
    private readonly IEventPublisher _eventPublisher;
    private readonly IIdentityResolutionService _identityResolution;
    private readonly ILogger<MockController> _logger;

    public MockController(
        IEventPublisher eventPublisher,
        IIdentityResolutionService identityResolution,
        ILogger<MockController> logger)
    {
        _eventPublisher = eventPublisher;
        _identityResolution = identityResolution;
        _logger = logger;
    }

    [HttpPost("events/generate")]
    public async Task<IActionResult> GenerateMockEvents([FromQuery] int count = 10)
    {
        var eventTypes = new[] { "sent", "delivered", "opened", "clicked" };
        var campaigns = new[] { "welcome_series", "weekly_newsletter", "promo_jan", "re_engagement" };
        var users = new[] { "user_001", "user_002", "user_003", "user_004", "user_005" };
        var random = new Random();

        var events = new List<CanonicalEvent>();

        for (int i = 0; i < count; i++)
        {
            var userId = users[random.Next(users.Length)];
            var campaignId = campaigns[random.Next(campaigns.Length)];
            var eventType = eventTypes[random.Next(eventTypes.Length)];
            var email = $"{userId}@example.com";
            
            var universalId = await _identityResolution.ResolveIdentityAsync(
                email: email,
                klaviyoId: $"k_{userId}");
            
            var evt = new CanonicalEvent
            {
                EventId = $"mock_evt_{Guid.NewGuid():N}",
                EventType = eventType,
                Timestamp = DateTime.UtcNow.AddMinutes(-random.Next(0, 10080)), // Random time in last week
                Esp = EspProviders.Klaviyo,
                UniversalId = universalId,
                RecipientEmail = _identityResolution.HashEmail(email),  // Hash email for privacy
                CampaignId = campaignId,
                CampaignName = campaignId.Replace("_", " ").ToUpper(),
                MessageId = $"msg_{Guid.NewGuid():N}",
                Subject = GenerateSubject(campaignId),
                ClickUrl = eventType == "clicked" ? "https://example.com/link" : null,
                UserAgent = "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)",
                IpAddress = $"192.168.{random.Next(1, 255)}.{random.Next(1, 255)}",
                IngestedAt = DateTime.UtcNow,
                Metadata = new Dictionary<string, object>
                {
                    ["mock"] = true,
                    ["generated_at"] = DateTime.UtcNow.ToString("O")
                }
            };

            events.Add(evt);
            await _eventPublisher.PublishAsync("email-events", evt.UniversalId, evt);
        }

        _logger.LogInformation("Generated {Count} mock events", count);

        return Ok(new
        {
            count = events.Count,
            events = events.Take(5), // Return first 5 as sample
            message = $"Published {events.Count} mock events to Kafka topic 'email-events'"
        });
    }

    [HttpPost("events/pattern")]
    public async Task<IActionResult> GenerateRealisticPattern([FromQuery] string userId = "user_001")
    {
        var events = new List<CanonicalEvent>();
        var now = DateTime.UtcNow;

        // Generate a realistic email journey
        var campaignId = "welcome_series";
        var messageId = $"msg_{Guid.NewGuid():N}";

        // 1. Sent
        events.Add(await CreateEvent(userId, campaignId, messageId, EventTypes.Sent, now.AddMinutes(-60)));
        
        // 2. Delivered
        events.Add(await CreateEvent(userId, campaignId, messageId, EventTypes.Delivered, now.AddMinutes(-59)));
        
        // 3. Opened
        events.Add(await CreateEvent(userId, campaignId, messageId, EventTypes.Opened, now.AddMinutes(-45)));
        
        // 4. Clicked
        var clickEvent = await CreateEvent(userId, campaignId, messageId, EventTypes.Clicked, now.AddMinutes(-40));
        clickEvent.ClickUrl = "https://sendflowr.com/dashboard";
        events.Add(clickEvent);

        foreach (var evt in events)
        {
            await _eventPublisher.PublishAsync("email-events", evt.UniversalId, evt);
        }

        _logger.LogInformation("Generated realistic pattern for user {UserId}", userId);

        return Ok(new
        {
            count = events.Count,
            userId,
            events,
            message = "Published realistic email journey to Kafka"
        });
    }

    private async Task<CanonicalEvent> CreateEvent(string userId, string campaignId, string messageId, string eventType, DateTime timestamp)
    {
        var email = $"{userId}@example.com";
        var universalId = await _identityResolution.ResolveIdentityAsync(
            email: email,
            klaviyoId: $"k_{userId}");
            
        return new CanonicalEvent
        {
            EventId = $"mock_evt_{Guid.NewGuid():N}",
            EventType = eventType,
            Timestamp = timestamp,
            Esp = EspProviders.Klaviyo,
            UniversalId = universalId,
            RecipientEmail = _identityResolution.HashEmail(email),  // Hash email for privacy
            CampaignId = campaignId,
            CampaignName = "Welcome Series",
            MessageId = messageId,
            Subject = "Welcome to SendFlowr!",
            UserAgent = "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)",
            IpAddress = "192.168.1.100",
            IngestedAt = DateTime.UtcNow,
            Metadata = new Dictionary<string, object>
            {
                ["mock"] = true,
                ["pattern"] = "realistic_journey"
            }
        };
    }

    [HttpPost("events/synthetic")]
    public async Task<IActionResult> IngestSyntheticEvent([FromBody] SyntheticEventRequest request)
    {
        try
        {
            // Resolve identity (universal_id) from provided identifiers
            var universalId = await _identityResolution.ResolveIdentityAsync(
                email: request.RecipientEmail,
                klaviyoId: request.Metadata?.GetValueOrDefault("klaviyo_id")?.ToString());
            
            // Create canonical event with resolved identity and hashed email
            var evt = new CanonicalEvent
            {
                EventId = request.EventId ?? $"synth_evt_{Guid.NewGuid():N}",
                EventType = request.EventType,
                Timestamp = request.Timestamp,
                Esp = request.Esp ?? EspProviders.Klaviyo,
                UniversalId = universalId,
                RecipientEmail = _identityResolution.HashEmail(request.RecipientEmail),
                CampaignId = request.CampaignId,
                CampaignName = request.CampaignName,
                MessageId = request.MessageId,
                Subject = request.Subject,
                ClickUrl = request.ClickUrl,
                UserAgent = request.UserAgent,
                IpAddress = request.IpAddress,
                IngestedAt = DateTime.UtcNow,
                Metadata = request.Metadata ?? new Dictionary<string, object>()
            };
            
            // Publish to Kafka
            await _eventPublisher.PublishAsync("email-events", evt.UniversalId, evt);
            
            return Ok(new
            {
                success = true,
                universal_id = universalId,
                event_id = evt.EventId,
                event_type = evt.EventType
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to ingest synthetic event");
            return BadRequest(new { error = ex.Message });
        }
    }

    private string GenerateSubject(string campaignId)
    {
        return campaignId switch
        {
            "welcome_series" => "Welcome to SendFlowr! 🌸",
            "weekly_newsletter" => "This Week's Top Tips",
            "promo_jan" => "🔥 January Sale - 50% Off!",
            "re_engagement" => "We miss you! Come back for 20% off",
            _ => "Email from SendFlowr"
        };
    }
}

public class SyntheticEventRequest
{
    [JsonPropertyName("event_id")]
    public string? EventId { get; set; }
    
    [JsonPropertyName("event_type")]
    public string EventType { get; set; } = string.Empty;
    
    [JsonPropertyName("timestamp")]
    public DateTime Timestamp { get; set; }
    
    [JsonPropertyName("esp")]
    public string? Esp { get; set; }
    
    [JsonPropertyName("recipient_email")]
    public string RecipientEmail { get; set; } = string.Empty;
    
    [JsonPropertyName("campaign_id")]
    public string CampaignId { get; set; } = string.Empty;
    
    [JsonPropertyName("campaign_name")]
    public string CampaignName { get; set; } = string.Empty;
    
    [JsonPropertyName("message_id")]
    public string MessageId { get; set; } = string.Empty;
    
    [JsonPropertyName("subject")]
    public string Subject { get; set; } = string.Empty;
    
    [JsonPropertyName("click_url")]
    public string? ClickUrl { get; set; }
    
    [JsonPropertyName("user_agent")]
    public string? UserAgent { get; set; }
    
    [JsonPropertyName("ip_address")]
    public string? IpAddress { get; set; }
    
    [JsonPropertyName("metadata")]
    public Dictionary<string, object>? Metadata { get; set; }
}
