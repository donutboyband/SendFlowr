using Microsoft.AspNetCore.Mvc;
using SendFlowr.Connectors.Interfaces;
using SendFlowr.Connectors.Services;

namespace SendFlowr.Connectors.Controllers;

[ApiController]
[Route("api/[controller]")]
public class WebhookController : ControllerBase
{
    private readonly IEspConnector _connector;
    private readonly IEventPublisher _eventPublisher;
    private readonly IIdentityResolutionService _identityResolution;
    private readonly ILogger<WebhookController> _logger;

    public WebhookController(
        IEspConnector connector,
        IEventPublisher eventPublisher,
        IIdentityResolutionService identityResolution,
        ILogger<WebhookController> logger)
    {
        _connector = connector;
        _eventPublisher = eventPublisher;
        _identityResolution = identityResolution;
        _logger = logger;
    }

    [HttpPost("klaviyo")]
    public async Task<IActionResult> HandleKlaviyoWebhook()
    {
        try
        {
            using var reader = new StreamReader(Request.Body);
            var payload = await reader.ReadToEndAsync();

            var signature = Request.Headers["X-Klaviyo-Signature"].FirstOrDefault();
            if (signature == null)
            {
                return Unauthorized(new { error = "Missing signature" });
            }

            var isValid = await _connector.ValidateWebhookSignatureAsync(signature, payload);
            if (!isValid)
            {
                _logger.LogWarning("Invalid webhook signature");
                return Unauthorized(new { error = "Invalid signature" });
            }

            var canonicalEvent = _connector.ParseWebhookEvent(payload);
            
            var plainEmail = canonicalEvent.RecipientEmail;  // Keep original for resolution
            
            var universalId = await _identityResolution.ResolveIdentityAsync(
                email: plainEmail,
                klaviyoId: canonicalEvent.Metadata?.GetValueOrDefault("klaviyo_profile_id")?.ToString());
            
            canonicalEvent.UniversalId = universalId;
            canonicalEvent.RecipientEmail = _identityResolution.HashEmail(plainEmail);  // Hash before publishing
            await _eventPublisher.PublishAsync("email-events", canonicalEvent.UniversalId, canonicalEvent);

            _logger.LogInformation("Webhook processed: {EventType} for universal_id {UniversalId}", 
                canonicalEvent.EventType, canonicalEvent.UniversalId);

            return Ok();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Webhook processing failed");
            return StatusCode(500);
        }
    }
}
