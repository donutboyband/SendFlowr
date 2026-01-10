# Build stage
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Copy solution file
COPY SendFlowr.sln ./

# Copy project files
COPY src/SendFlowr.Connectors/SendFlowr.Connectors.csproj src/SendFlowr.Connectors/

# Restore dependencies
RUN dotnet restore src/SendFlowr.Connectors/SendFlowr.Connectors.csproj

# Copy source code
COPY src/SendFlowr.Connectors/ src/SendFlowr.Connectors/

# Build
WORKDIR /src/src/SendFlowr.Connectors
RUN dotnet build -c Release -o /app/build --no-restore

# Publish
RUN dotnet publish -c Release -o /app/publish --no-restore

# Runtime stage
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app

COPY --from=build /app/publish .

EXPOSE 5215

ENV ASPNETCORE_URLS=http://+:5215
ENV ASPNETCORE_ENVIRONMENT=Development

ENTRYPOINT ["dotnet", "SendFlowr.Connectors.dll"]
