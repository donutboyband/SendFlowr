#!/bin/bash

echo "🌸 SendFlowr Quick Start"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Start services
echo "🚀 Starting infrastructure..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be healthy (30 seconds)..."
sleep 30

echo ""
echo "✅ Services should be ready!"
echo ""
echo "📊 Service Status:"
docker-compose ps
echo ""

echo "🎯 Next steps:"
echo ""
echo "1. Start the connector service:"
echo "   cd src/SendFlowr.Connectors && dotnet run"
echo ""
echo "2. Generate mock data:"
echo "   curl -X POST 'http://localhost:5215/api/mock/events/generate?count=100'"
echo ""
echo "3. View Swagger UI:"
echo "   open http://localhost:5215/swagger"
echo ""
echo "4. Monitor Kafka events:"
echo "   docker exec -it sendflowr-kafka kafka-console-consumer \\"
echo "     --bootstrap-server localhost:9092 \\"
echo "     --topic email-events \\"
echo "     --from-beginning"
echo ""
echo "📖 See SETUP-COMPLETE.md and docs/MOCK-DATA.md for full details"
