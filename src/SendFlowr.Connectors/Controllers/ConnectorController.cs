using Microsoft.AspNetCore.Mvc;
using SendFlowr.Connectors.Interfaces;
using SendFlowr.Connectors.Services;

namespace SendFlowr.Connectors.Controllers;

[ApiController]
[Route("api/[controller]")]
public class ConnectorController : ControllerBase
{
    private readonly IEspConnector _connector;
    private readonly IEventPublisher _eventPublisher;
    private readonly IIdentityResolutionService _identityResolution;
    private readonly ILogger<ConnectorController> _logger;

    public ConnectorController(
        IEspConnector connector,
        IEventPublisher eventPublisher,
        IIdentityResolutionService identityResolution,
        ILogger<ConnectorController> logger)
    {
        _connector = connector;
        _eventPublisher = eventPublisher;
        _identityResolution = identityResolution;
        _logger = logger;
    }

    [HttpGet("oauth/authorize")]
    public async Task<IActionResult> InitiateOAuth([FromQuery] string callbackUrl)
    {
        var result = await _connector.InitiateOAuthAsync(callbackUrl);
        return Ok(new { authorizationUrl = result.AuthorizationUrl, state = result.State });
    }

    [HttpGet("oauth/callback")]
    public async Task<IActionResult> OAuthCallback([FromQuery] string code, [FromQuery] string state)
    {
        try
        {
            var tokenResult = await _connector.ExchangeCodeForTokenAsync(code);
            _logger.LogInformation("OAuth completed for account {AccountId}", tokenResult.AccountId);
            
            return Ok(new { 
                success = true, 
                accountId = tokenResult.AccountId,
                expiresAt = tokenResult.ExpiresAt 
            });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "OAuth callback failed");
            return BadRequest(new { error = ex.Message });
        }
    }

    [HttpPost("backfill")]
    public async Task<IActionResult> Backfill([FromQuery] int days = 90)
    {
        try
        {
            var since = DateTime.UtcNow.AddDays(-days);
            var events = await _connector.BackfillEventsAsync(since);
            
            var eventList = events.ToList();
            foreach (var evt in eventList)
            {
                var plainEmail = evt.RecipientEmail;  // Keep original for resolution
                
                var universalId = await _identityResolution.ResolveIdentityAsync(
                    email: plainEmail,
                    klaviyoId: evt.Metadata?.GetValueOrDefault("klaviyo_profile_id")?.ToString());
                
                evt.UniversalId = universalId;
                evt.RecipientEmail = _identityResolution.HashEmail(plainEmail);  // Hash before publishing
                await _eventPublisher.PublishAsync("email-events", evt.UniversalId, evt);
            }

            _logger.LogInformation("Backfilled {Count} events since {Since}", eventList.Count, since);
            return Ok(new { count = eventList.Count, since });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Backfill failed");
            return StatusCode(500, new { error = ex.Message });
        }
    }
}
