using System.Security.Cryptography;
using System.Text;
using Newtonsoft.Json.Linq;
using SendFlowr.Connectors.Interfaces;
using SendFlowr.Connectors.Models;

namespace SendFlowr.Connectors.Connectors;

public class KlaviyoConnector : IEspConnector
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<KlaviyoConnector> _logger;
    private readonly IConfiguration _configuration;
    private const string BaseUrl = "https://a.klaviyo.com/api";

    public string EspName => EspProviders.Klaviyo;

    public KlaviyoConnector(
        HttpClient httpClient,
        ILogger<KlaviyoConnector> logger,
        IConfiguration configuration)
    {
        _httpClient = httpClient;
        _logger = logger;
        _configuration = configuration;
    }

    public Task<OAuthResult> InitiateOAuthAsync(string callbackUrl)
    {
        var clientId = _configuration["Klaviyo:ClientId"];
        var state = Guid.NewGuid().ToString("N");
        
        var authUrl = $"https://www.klaviyo.com/oauth/authorize?" +
                     $"response_type=code&" +
                     $"client_id={clientId}&" +
                     $"redirect_uri={Uri.EscapeDataString(callbackUrl)}&" +
                     $"state={state}&" +
                     $"scope=events:read campaigns:read";

        return Task.FromResult(new OAuthResult
        {
            AuthorizationUrl = authUrl,
            State = state
        });
    }

    public async Task<TokenResult> ExchangeCodeForTokenAsync(string code)
    {
        var clientId = _configuration["Klaviyo:ClientId"];
        var clientSecret = _configuration["Klaviyo:ClientSecret"];
        var redirectUri = _configuration["Klaviyo:RedirectUri"];

        var request = new HttpRequestMessage(HttpMethod.Post, "https://a.klaviyo.com/oauth/token");
        var formData = new Dictionary<string, string>
        {
            ["grant_type"] = "authorization_code",
            ["code"] = code,
            ["redirect_uri"] = redirectUri,
            ["client_id"] = clientId,
            ["client_secret"] = clientSecret
        };

        request.Content = new FormUrlEncodedContent(formData);
        
        var response = await _httpClient.SendAsync(request);
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync();
        var data = JObject.Parse(json);

        return new TokenResult
        {
            AccessToken = data["access_token"]?.ToString() ?? throw new Exception("No access token"),
            RefreshToken = data["refresh_token"]?.ToString() ?? throw new Exception("No refresh token"),
            ExpiresAt = DateTime.UtcNow.AddSeconds(data["expires_in"]?.Value<int>() ?? 3600),
            AccountId = data["account_id"]?.ToString() ?? throw new Exception("No account ID")
        };
    }

    public async Task<IEnumerable<CanonicalEvent>> BackfillEventsAsync(DateTime since, string? cursor = null)
    {
        var events = new List<CanonicalEvent>();
        var accessToken = _configuration["Klaviyo:AccessToken"];

        var url = $"{BaseUrl}/events?" +
                 $"filter=greater-than(datetime,{since:yyyy-MM-ddTHH:mm:ssZ})" +
                 (cursor != null ? $"&page[cursor]={cursor}" : "");

        var request = new HttpRequestMessage(HttpMethod.Get, url);
        request.Headers.Add("Authorization", $"Klaviyo-API-Key {accessToken}");
        request.Headers.Add("revision", "2024-10-15");

        var response = await _httpClient.SendAsync(request);
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync();
        var data = JObject.Parse(json);

        foreach (var eventData in data["data"] ?? new JArray())
        {
            var canonicalEvent = ParseKlaviyoEvent(eventData);
            if (canonicalEvent != null)
            {
                events.Add(canonicalEvent);
            }
        }

        return events;
    }

    public Task<bool> ValidateWebhookSignatureAsync(string signature, string payload)
    {
        var secret = _configuration["Klaviyo:WebhookSecret"];
        
        using var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(secret));
        var hash = hmac.ComputeHash(Encoding.UTF8.GetBytes(payload));
        var computedSignature = Convert.ToBase64String(hash);

        return Task.FromResult(signature == computedSignature);
    }

    public CanonicalEvent ParseWebhookEvent(string payload)
    {
        var data = JObject.Parse(payload);
        return ParseKlaviyoEvent(data["data"]) 
            ?? throw new Exception("Could not parse webhook event");
    }

    private CanonicalEvent? ParseKlaviyoEvent(JToken? eventData)
    {
        if (eventData == null) return null;

        var attributes = eventData["attributes"];
        var eventType = MapKlaviyoEventType(attributes?["metric"]?["data"]?["attributes"]?["name"]?.ToString());
        
        if (eventType == null) return null;

        return new CanonicalEvent
        {
            EventId = eventData["id"]?.ToString() ?? Guid.NewGuid().ToString(),
            EventType = eventType,
            Timestamp = attributes?["datetime"]?.ToObject<DateTime>() ?? DateTime.UtcNow,
            Esp = EspProviders.Klaviyo,
            RecipientId = attributes?["profile"]?["data"]?["id"]?.ToString() ?? "",
            RecipientEmail = attributes?["profile"]?["data"]?["attributes"]?["email"]?.ToString(),
            CampaignId = attributes?["campaign"]?["data"]?["id"]?.ToString() ?? "",
            CampaignName = attributes?["campaign"]?["data"]?["attributes"]?["name"]?.ToString(),
            MessageId = attributes?["message_id"]?.ToString(),
            Subject = attributes?["subject"]?.ToString(),
            ClickUrl = attributes?["url"]?.ToString(),
            UserAgent = attributes?["user_agent"]?.ToString(),
            IpAddress = attributes?["ip_address"]?.ToString(),
            IngestedAt = DateTime.UtcNow,
            Metadata = new Dictionary<string, object>
            {
                ["klaviyo_event_id"] = eventData["id"]?.ToString() ?? ""
            }
        };
    }

    private string? MapKlaviyoEventType(string? klaviyoEvent)
    {
        return klaviyoEvent switch
        {
            "Sent Email" => EventTypes.Sent,
            "Received Email" => EventTypes.Delivered,
            "Opened Email" => EventTypes.Opened,
            "Clicked Email" => EventTypes.Clicked,
            "Bounced Email" => EventTypes.Bounced,
            "Unsubscribed" => EventTypes.Unsubscribed,
            "Marked Email as Spam" => EventTypes.MarkedSpam,
            _ => null
        };
    }
}
