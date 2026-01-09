using Confluent.Kafka;
using ClickHouse.Client.ADO;
using Newtonsoft.Json;

Console.WriteLine("🌸 SendFlowr Event Consumer");
Console.WriteLine("===========================");
Console.WriteLine();

// Configuration
var kafkaConfig = new ConsumerConfig
{
    BootstrapServers = "localhost:9092",
    GroupId = "sendflowr-consumer",
    AutoOffsetReset = AutoOffsetReset.Earliest,
    EnableAutoCommit = false
};

var clickhouseConnectionString = "Host=localhost;Port=8123;Database=sendflowr;Username=sendflowr;Password=sendflowr_dev";

using var consumer = new ConsumerBuilder<string, string>(kafkaConfig).Build();
consumer.Subscribe("email-events");

using var clickhouseConnection = new ClickHouseConnection(clickhouseConnectionString);
await clickhouseConnection.OpenAsync();

Console.WriteLine("✅ Connected to Kafka and ClickHouse");
Console.WriteLine("📊 Consuming events from 'email-events' topic...");
Console.WriteLine();

var eventCount = 0;
var cts = new CancellationTokenSource();

Console.CancelKeyPress += (_, e) =>
{
    e.Cancel = true;
    cts.Cancel();
};

try
{
    while (!cts.Token.IsCancellationRequested)
    {
        var consumeResult = consumer.Consume(TimeSpan.FromSeconds(1));
        
        if (consumeResult == null)
            continue;

        try
        {
            var eventData = JsonConvert.DeserializeObject<CanonicalEvent>(consumeResult.Message.Value);
            
            if (eventData == null)
            {
                Console.WriteLine($"⚠️  Failed to deserialize event");
                consumer.Commit(consumeResult);
                continue;
            }

            // Insert into ClickHouse using direct SQL
            var metadataJson = eventData.Metadata != null ? JsonConvert.SerializeObject(eventData.Metadata).Replace("'", "''") : "";
            
            var insertQuery = $@"
                INSERT INTO email_events 
                (event_id, event_type, timestamp, esp, recipient_id, recipient_email, 
                 campaign_id, campaign_name, message_id, subject, click_url, bounce_type, 
                 user_agent, ip_address, metadata, ingested_at)
                VALUES 
                ('{eventData.EventId.Replace("'", "''")}', 
                 '{eventData.EventType.Replace("'", "''")}', 
                 '{eventData.Timestamp:yyyy-MM-dd HH:mm:ss}', 
                 '{eventData.Esp.Replace("'", "''")}', 
                 '{eventData.RecipientId.Replace("'", "''")}', 
                 '{(eventData.RecipientEmail ?? "").Replace("'", "''")}',
                 '{eventData.CampaignId.Replace("'", "''")}', 
                 '{(eventData.CampaignName ?? "").Replace("'", "''")}', 
                 '{(eventData.MessageId ?? "").Replace("'", "''")}', 
                 '{(eventData.Subject ?? "").Replace("'", "''")}', 
                 '{(eventData.ClickUrl ?? "").Replace("'", "''")}', 
                 '{(eventData.BounceType ?? "").Replace("'", "''")}',
                 '{(eventData.UserAgent ?? "").Replace("'", "''")}', 
                 '{(eventData.IpAddress ?? "").Replace("'", "''")}', 
                 '{metadataJson}', 
                 '{eventData.IngestedAt:yyyy-MM-dd HH:mm:ss}')";

            using var command = clickhouseConnection.CreateCommand();
            command.CommandText = insertQuery;
            await command.ExecuteNonQueryAsync();

            eventCount++;
            if (eventCount % 10 == 0)
            {
                Console.WriteLine($"✅ Processed {eventCount} events...");
            }

            consumer.Commit(consumeResult);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Error processing event: {ex.Message}");
            consumer.Commit(consumeResult); // Commit anyway to move forward
        }
    }
}
catch (OperationCanceledException)
{
    Console.WriteLine();
    Console.WriteLine("⏹️  Shutting down consumer...");
}
finally
{
    consumer.Close();
    Console.WriteLine($"✅ Processed {eventCount} total events");
    Console.WriteLine("🎯 Consumer stopped");
}

public class CanonicalEvent
{
    public string EventId { get; set; } = "";
    public string EventType { get; set; } = "";
    public DateTime Timestamp { get; set; }
    public string Esp { get; set; } = "";
    public string RecipientId { get; set; } = "";
    public string? RecipientEmail { get; set; }
    public string CampaignId { get; set; } = "";
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
