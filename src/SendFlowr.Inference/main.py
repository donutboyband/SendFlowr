"""
SendFlowr Timing Layer API
Clean layered architecture: Controllers → Services → Repositories
"""
from fastapi import FastAPI
from scalar_fastapi import get_scalar_api_reference
from models.requests import TimingRequest, LegacyPredictionRequest
from models.responses import TimingDecisionResponse
from controllers.timing_controller import TimingController
from services.timing_service import TimingService
from services.feature_service import FeatureService
from repositories.event_repository import EventRepository
from repositories.feature_repository import FeatureRepository
from repositories.explanation_repository import ExplanationRepository


# Initialize FastAPI app
app = FastAPI(
    title="SendFlowr Timing Layer API",
    version="2.0.0",
    description="""
    **SendFlowr Timing Intelligence Layer**
    
    Minute-level precision timing decisions with latency awareness.
    
    ## Features
    - 🎯 10,080 minute-slot resolution (canonical time grid)
    - 📊 Click-based engagement modeling (MPP resilient)
    - ⚡ Latency-aware trigger computation
    - 🔄 Continuous probability curves
    - 📝 Explainable decision outputs
    
    ## Architecture
    Clean layered design: **Controllers → Services → Repositories**
    
    ## Spec Compliance
    Fully compliant with LLM-Ref specifications
    """,
    contact={
        "name": "SendFlowr Team",
    },
    license_info={
        "name": "Proprietary",
    }
)

# Initialize layers (Dependency Injection)
event_repo = EventRepository()
feature_repo = FeatureRepository()
explanation_repo = ExplanationRepository()

# Identity resolution layer
from repositories.identity_repository import IdentityRepository
from services.identity_service import IdentityResolver

identity_repo = IdentityRepository(event_repo.client)  # Reuse ClickHouse client
identity_resolver = IdentityResolver(identity_repo)

# Feature and timing services
feature_service = FeatureService(event_repo, feature_repo)
timing_service = TimingService(feature_service, identity_resolver, feature_repo, explanation_repo)

controller = TimingController(timing_service, feature_service)


# Routes - thin layer, delegates to controller
@app.get("/")
def root():
    return {
        "service": "SendFlowr Timing Layer API",
        "version": "2.0.0",
        "architecture": "Layered (Controller → Service → Repository)",
        "compliance": "Minute-level resolution with latency awareness",
        "documentation": {
            "swagger": "/docs",
            "scalar": "/scalar",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        },
        "endpoints": {
            "timing_decision": "/timing-decision (primary)",
            "predict": "/predict (legacy STO fallback)",
            "features": "/features/{recipient_id}",
            "compute_features": "/compute-features",
            "health": "/health"
        }
    }


@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    """Scalar API documentation UI"""
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )


@app.get("/health",
        tags=["System"],
        summary="Health check",
        description="Check API health and database connectivity")
def health_check():
    """Health check endpoint"""
    try:
        feature_repo.client.ping()
        event_repo.client.execute("SELECT 1")
        return {
            "status": "healthy",
            "redis": "ok",
            "clickhouse": "ok",
            "architecture": "layered"
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.post("/timing-decision", 
         response_model=TimingDecisionResponse,
         tags=["Timing Decisions"],
         summary="Generate timing decision (Primary)",
         description="""
         Generate a spec-compliant timing decision with minute-level precision.
         
         **This is the primary endpoint for production use.**
         
         ### Features:
         - Minute-level resolution (10,080 slots)
         - Click-based engagement modeling
         - Latency-aware trigger computation
         - Context-aware (hot paths, circuit breakers)
         - Explainable outputs
         
         ### Returns:
         TimingDecision object per spec.json schema
         """)
def generate_timing_decision(request: TimingRequest):
    """
    Primary endpoint: Generate timing decision per spec.json
    
    Delegates to: TimingController → TimingService → Repositories
    """
    return controller.generate_timing_decision(request)


@app.post("/predict",
         tags=["Legacy"],
         summary="Hourly STO prediction (Legacy)",
         description="""
         Legacy hour-level Send Time Optimization endpoint.
         
         **Deprecated:** Use `/timing-decision` for minute-level precision.
         
         This endpoint is maintained for backwards compatibility only.
         """,
         deprecated=True)
def legacy_predict(request: LegacyPredictionRequest):
    """
    Legacy STO fallback endpoint
    
    Per spec: "Hour-level Send Time Optimization MUST remain supported"
    """
    return controller.legacy_predict(request)


@app.get("/features/{recipient_id}",
        tags=["Features"],
        summary="Get computed features",
        description="Retrieve cached minute-level features for a recipient")
def get_features(recipient_id: str):
    """Get cached features (v2 minute-level)"""
    return controller.get_features(recipient_id)


@app.post("/compute-features/{recipient_id}",
         tags=["Features"],
         summary="Compute features on-demand",
         description="Force recomputation of features for a specific user")
def compute_features_for_user(recipient_id: str):
    """Compute features on-demand for a specific user"""
    return controller.compute_features(recipient_id)


@app.post("/compute-features",
         tags=["Features"],
         summary="Compute features for all users",
         description="Batch compute minute-level features for all active users")
def compute_all_features():
    """Compute minute-level features for all active users"""
    return controller.compute_features()


# Identity Resolution Endpoints
@app.post("/resolve-identity",
         tags=["Identity"],
         summary="Resolve identity to Universal SendFlowr ID",
         description="""
         Resolves multiple identity keys to a single Universal SendFlowr ID.
         
         **Deterministic keys** (highest priority):
         - email (hashed internally)
         - phone (normalized to E.164)
         
         **Probabilistic keys** (graph-based matching):
         - klaviyo_id
         - shopify_customer_id
         - esp_user_id
         
         Returns Universal ID with audit trail.
         """)
def resolve_identity(
    email: str = None,
    phone: str = None,
    klaviyo_id: str = None,
    shopify_customer_id: str = None,
    esp_user_id: str = None
):
    """Resolve identity keys to Universal SendFlowr ID"""
    identifiers = {}
    if email:
        identifiers['email'] = email
    if phone:
        identifiers['phone'] = phone
    if klaviyo_id:
        identifiers['klaviyo_id'] = klaviyo_id
    if shopify_customer_id:
        identifiers['shopify_customer_id'] = shopify_customer_id
    if esp_user_id:
        identifiers['esp_user_id'] = esp_user_id
    
    if not identifiers:
        return {"error": "No identity keys provided"}
    
    resolution = identity_resolver.resolve(identifiers)
    return resolution.to_dict()


@app.post("/link-identifiers",
         tags=["Identity"],
         summary="Link two identifiers in identity graph",
         description="""
         Create bidirectional link between identifiers.
         
         **Weight** determines confidence:
         - 1.0 = deterministic (same person)
         - < 1.0 = probabilistic (likely same person)
         
         **Source** tracks origin:
         - 'klaviyo_webhook', 'shopify_order', 'manual', etc.
         """)
def link_identifiers(
    identifier_a: str,
    type_a: str,
    identifier_b: str,
    type_b: str,
    weight: float = 1.0,
    source: str = "api"
):
    """Link two identifiers in identity graph"""
    from core.identity_model import IdentifierType
    
    try:
        type_a_enum = IdentifierType(type_a)
        type_b_enum = IdentifierType(type_b)
    except ValueError:
        return {"error": f"Invalid identifier type. Must be one of: {[t.value for t in IdentifierType]}"}
    
    identity_resolver.link_identifiers(
        identifier_a, type_a_enum,
        identifier_b, type_b_enum,
        weight, source
    )
    
    return {
        "status": "linked",
        "identifier_a": identifier_a,
        "identifier_b": identifier_b,
        "weight": weight
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
