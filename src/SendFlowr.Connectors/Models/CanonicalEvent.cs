namespace SendFlowr.Connectors.Models;

public class CanonicalEvent
{
    public required string EventId { get; set; }
    public required string EventType { get; set; }
    public required DateTime Timestamp { get; set; }
    public required string Esp { get; set; }
    public required string RecipientId { get; set; }
    public string? RecipientEmail { get; set; }
    public required string CampaignId { get; set; }
    public string? CampaignName { get; set; }
    public string? MessageId { get; set; }
    public string? Subject { get; set; }
    public string? ClickUrl { get; set; }
    public string? BounceType { get; set; }
    public string? UserAgent { get; set; }
    public string? IpAddress { get; set; }
    public Dictionary<string, object>? Metadata { get; set; }
    public DateTime IngestedAt { get; set; }
}

public static class EventTypes
{
    public const string Sent = "sent";
    public const string Delivered = "delivered";
    public const string Opened = "opened";
    public const string Clicked = "clicked";
    public const string Bounced = "bounced";
    public const string Unsubscribed = "unsubscribed";
    public const string MarkedSpam = "marked_spam";
}

public static class EspProviders
{
    public const string Klaviyo = "klaviyo";
    public const string SendGrid = "sendgrid";
    public const string Mailchimp = "mailchimp";
    public const string Braze = "braze";
}
