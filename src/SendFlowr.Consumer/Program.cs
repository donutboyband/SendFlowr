using Confluent.Kafka;
using ClickHouse.Client.ADO;
using Newtonsoft.Json;
using System.Text;

Console.WriteLine("🌸 SendFlowr Event Consumer");
Console.WriteLine("===========================");
Console.WriteLine();

// Configuration from environment variables
var kafkaBootstrapServers = Environment.GetEnvironmentVariable("Kafka__BootstrapServers") ?? "localhost:9092";
var clickhouseHost = Environment.GetEnvironmentVariable("ClickHouse__Host") ?? "localhost";
var clickhousePort = Environment.GetEnvironmentVariable("ClickHouse__Port") ?? "8123";
var clickhouseDatabase = Environment.GetEnvironmentVariable("ClickHouse__Database") ?? "sendflowr";
var clickhouseUser = Environment.GetEnvironmentVariable("ClickHouse__User") ?? "sendflowr";
var clickhousePassword = Environment.GetEnvironmentVariable("ClickHouse__Password") ?? "sendflowr_dev";

var kafkaConfig = new ConsumerConfig
{
    BootstrapServers = kafkaBootstrapServers,
    GroupId = "sendflowr-consumer",
    AutoOffsetReset = AutoOffsetReset.Earliest,
    EnableAutoCommit = false
};

var clickhouseConnectionString = $"Host={clickhouseHost};Port={clickhousePort};Database={clickhouseDatabase};Username={clickhouseUser};Password={clickhousePassword}";

Console.WriteLine($"Kafka: {kafkaBootstrapServers}");
Console.WriteLine($"ClickHouse: {clickhouseHost}:{clickhousePort}/{clickhouseDatabase}");
Console.WriteLine();

using var consumer = new ConsumerBuilder<string, string>(kafkaConfig).Build();
consumer.Subscribe("email-events");

var producerConfig = new ProducerConfig
{
    BootstrapServers = kafkaConfig.BootstrapServers,
    ClientId = "sendflowr-consumer-dlq",
    Acks = Acks.All,
    EnableIdempotence = true
};

using var dlqProducer = new ProducerBuilder<string, string>(producerConfig).Build();

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
            var rawPayload = consumeResult.Message.Value;
            var eventData = JsonConvert.DeserializeObject<CanonicalEvent>(rawPayload);

            ValidateEvent(eventData);

            // Insert into ClickHouse using direct SQL
            var metadataJson = eventData.Metadata != null
                ? JsonConvert.SerializeObject(eventData.Metadata).Replace("'", "''")
                : "{}";
            
            var insertQuery = $@"
                INSERT INTO email_events 
                (event_id, event_type, timestamp, esp, universal_id, recipient_email_hash, 
                 campaign_id, campaign_name, message_id, subject, click_url, bounce_type, 
                 user_agent, ip_address, metadata, ingested_at)
                VALUES 
                ('{eventData.EventId.Replace("'", "''")}', 
                 '{eventData.EventType.Replace("'", "''")}', 
                 '{eventData.Timestamp.ToUniversalTime():yyyy-MM-dd HH:mm:ss}', 
                 '{eventData.Esp.Replace("'", "''")}', 
                 '{eventData.UniversalId.Replace("'", "''")}', 
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
            Console.WriteLine($"❌ Error processing event {consumeResult?.Message?.Key}: {ex.Message}");
            await SendToDlqAsync(dlqProducer, consumeResult, ex);
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

static void ValidateEvent(CanonicalEvent? evt)
{
    if (evt == null)
    {
        throw new InvalidOperationException("Event payload could not be deserialized");
    }

    if (string.IsNullOrWhiteSpace(evt.EventId) || string.IsNullOrWhiteSpace(evt.EventType) || evt.Timestamp == default)
    {
        throw new InvalidOperationException("Event payload missing required fields");
    }
}

static async Task SendToDlqAsync(IProducer<string, string> dlqProducer, ConsumeResult<string, string>? consumeResult, Exception ex)
{
    if (consumeResult == null)
    {
        return;
    }

    var payload = new
    {
        error = ex.Message,
        original_key = consumeResult.Message.Key,
        original_value = consumeResult.Message.Value,
        partition = consumeResult.Partition.Value,
        offset = consumeResult.Offset.Value,
        ingested_at = DateTime.UtcNow
    };

    var serialized = JsonConvert.SerializeObject(payload);
    await dlqProducer.ProduceAsync("email-events-dlq", new Message<string, string>
    {
        Key = consumeResult.Message.Key,
        Value = serialized
    });
}

public class CanonicalEvent
{
    [JsonProperty("event_id")]
    public string EventId { get; set; } = "";
    
    [JsonProperty("event_type")]
    public string EventType { get; set; } = "";
    
    [JsonProperty("timestamp")]
    public DateTime Timestamp { get; set; }
    
    [JsonProperty("esp")]
    public string Esp { get; set; } = "";
    
    [JsonProperty("universal_id")]
    public string UniversalId { get; set; } = "";
    
    [JsonProperty("recipient_email")]
    public string? RecipientEmail { get; set; }
    
    [JsonProperty("campaign_id")]
    public string CampaignId { get; set; } = "";
    
    [JsonProperty("campaign_name")]
    public string? CampaignName { get; set; }
    
    [JsonProperty("message_id")]
    public string? MessageId { get; set; }
    
    [JsonProperty("subject")]
    public string? Subject { get; set; }
    
    [JsonProperty("click_url")]
    public string? ClickUrl { get; set; }
    
    [JsonProperty("bounce_type")]
    public string? BounceType { get; set; }
    
    [JsonProperty("user_agent")]
    public string? UserAgent { get; set; }
    
    [JsonProperty("ip_address")]
    public string? IpAddress { get; set; }
    
    [JsonProperty("metadata")]
    public Dictionary<string, object>? Metadata { get; set; }
    
    [JsonProperty("ingested_at")]
    public DateTime IngestedAt { get; set; }
}
