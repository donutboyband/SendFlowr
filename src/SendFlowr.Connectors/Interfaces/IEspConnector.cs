namespace SendFlowr.Connectors.Interfaces;

using SendFlowr.Connectors.Models;

public interface IEspConnector
{
    string EspName { get; }
    
    Task<OAuthResult> InitiateOAuthAsync(string callbackUrl);
    Task<TokenResult> ExchangeCodeForTokenAsync(string code);
    Task<IEnumerable<CanonicalEvent>> BackfillEventsAsync(DateTime since, string? cursor = null);
    Task<bool> ValidateWebhookSignatureAsync(string signature, string payload);
    CanonicalEvent ParseWebhookEvent(string payload);
}

public class OAuthResult
{
    public required string AuthorizationUrl { get; set; }
    public required string State { get; set; }
}

public class TokenResult
{
    public required string AccessToken { get; set; }
    public required string RefreshToken { get; set; }
    public DateTime ExpiresAt { get; set; }
    public required string AccountId { get; set; }
}
