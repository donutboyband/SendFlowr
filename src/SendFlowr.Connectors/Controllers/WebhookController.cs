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
    private readonly ILogger<WebhookController> _logger;

    public WebhookController(
        IEspConnector connector,
        IEventPublisher eventPublisher,
        ILogger<WebhookController> logger)
    {
        _connector = connector;
        _eventPublisher = eventPublisher;
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
            await _eventPublisher.PublishAsync("email-events", canonicalEvent.RecipientId, canonicalEvent);

            _logger.LogInformation("Webhook processed: {EventType} for recipient {RecipientId}", 
                canonicalEvent.EventType, canonicalEvent.RecipientId);

            return Ok();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Webhook processing failed");
            return StatusCode(500);
        }
    }
}
