using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace SendFlowr.Connectors.Services;

public interface IIdentityResolutionService
{
    Task<string> ResolveIdentityAsync(string? email, string? phone = null, string? klaviyoId = null, string? shopifyCustomerId = null);
    string? HashEmail(string? email);
}

public class IdentityResolutionService : IIdentityResolutionService
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<IdentityResolutionService> _logger;
    private readonly string _inferenceServiceUrl;

    public IdentityResolutionService(
        HttpClient httpClient,
        ILogger<IdentityResolutionService> logger,
        IConfiguration configuration)
    {
        _httpClient = httpClient;
        _logger = logger;
        _inferenceServiceUrl = configuration["InferenceService:Url"] ?? "http://localhost:8001";
    }

    public async Task<string> ResolveIdentityAsync(
        string? email,
        string? phone = null,
        string? klaviyoId = null,
        string? shopifyCustomerId = null)
    {
        try
        {
            var queryParams = new List<string>();
            
            if (!string.IsNullOrWhiteSpace(email))
                queryParams.Add($"email={Uri.EscapeDataString(email)}");
            
            if (!string.IsNullOrWhiteSpace(phone))
                queryParams.Add($"phone={Uri.EscapeDataString(phone)}");
            
            if (!string.IsNullOrWhiteSpace(klaviyoId))
                queryParams.Add($"klaviyo_id={Uri.EscapeDataString(klaviyoId)}");
            
            if (!string.IsNullOrWhiteSpace(shopifyCustomerId))
                queryParams.Add($"shopify_customer_id={Uri.EscapeDataString(shopifyCustomerId)}");

            if (queryParams.Count == 0)
            {
                // No identifiable information - generate placeholder
                return $"sf_unknown_{Guid.NewGuid():N}";
            }

            var queryString = string.Join("&", queryParams);
            var url = $"{_inferenceServiceUrl}/resolve-identity?{queryString}";

            var response = await _httpClient.PostAsync(url, null);
            
            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning("Identity resolution failed with status {StatusCode}. Generating placeholder.", response.StatusCode);
                return $"sf_unknown_{Guid.NewGuid():N}";
            }

            var jsonResponse = await response.Content.ReadAsStringAsync();
            using var doc = JsonDocument.Parse(jsonResponse);
            
            var universalId = doc.RootElement.GetProperty("universal_id").GetString();
            
            if (string.IsNullOrWhiteSpace(universalId))
            {
                _logger.LogWarning("Identity resolution returned empty universal_id. Generating placeholder.");
                return $"sf_unknown_{Guid.NewGuid():N}";
            }

            _logger.LogDebug("Resolved identity to {UniversalId}", universalId);
            return universalId;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error resolving identity. Generating placeholder.");
            return $"sf_unknown_{Guid.NewGuid():N}";
        }
    }

    public string? HashEmail(string? email)
    {
        if (string.IsNullOrWhiteSpace(email))
            return null;

        var normalized = email.Trim().ToLowerInvariant();
        using var sha256 = SHA256.Create();
        var hashBytes = sha256.ComputeHash(Encoding.UTF8.GetBytes(normalized));
        return Convert.ToHexString(hashBytes).ToLowerInvariant();
    }
}
