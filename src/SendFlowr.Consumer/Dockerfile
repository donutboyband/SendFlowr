# Build stage
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Copy solution file
COPY SendFlowr.sln ./

# Copy project files
COPY src/SendFlowr.Consumer/SendFlowr.Consumer.csproj src/SendFlowr.Consumer/

# Restore dependencies
RUN dotnet restore src/SendFlowr.Consumer/SendFlowr.Consumer.csproj

# Copy source code
COPY src/SendFlowr.Consumer/ src/SendFlowr.Consumer/

# Build
WORKDIR /src/src/SendFlowr.Consumer
RUN dotnet build -c Release -o /app/build --no-restore

# Publish
RUN dotnet publish -c Release -o /app/publish --no-restore

# Runtime stage
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app

COPY --from=build /app/publish .

ENTRYPOINT ["dotnet", "SendFlowr.Consumer.dll"]
