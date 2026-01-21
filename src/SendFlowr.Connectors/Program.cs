using SendFlowr.Connectors.Connectors;
using SendFlowr.Connectors.Interfaces;
using SendFlowr.Connectors.Services;
using Scalar.AspNetCore;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();

// Use Swashbuckle for OpenAPI spec generation (compatible with Scalar)
builder.Services.AddSwaggerGen(options =>
{
    options.SwaggerDoc("v1", new Microsoft.OpenApi.Models.OpenApiInfo
    {
        Title = "SendFlowr Connector API",
        Version = "v1",
        Description = "Event ingestion and identity resolution service"
    });
});

builder.Services.AddHttpClient<IEspConnector, KlaviyoConnector>();
builder.Services.AddHttpClient<IIdentityResolutionService, IdentityResolutionService>();
builder.Services.AddSingleton<IEventPublisher, KafkaEventPublisher>();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger(options =>
    {
        options.RouteTemplate = "openapi/{documentName}.json";
    });
    
    app.MapScalarApiReference(options =>
    {
        options
            .WithTitle("SendFlowr Connector API")
            .WithTheme(ScalarTheme.DeepSpace)
            .WithDefaultHttpClient(ScalarTarget.CSharp, ScalarClient.HttpClient);
    });
}

app.UseHttpsRedirection();
app.MapControllers();

app.Run();

