import hashlib
import json
import os
import sys
from contextlib import asynccontextmanager

import hvac
import structlog
import torch
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from minio import Minio
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sentence_transformers import CrossEncoder, SentenceTransformer
from transformers import DistilBertForSequenceClassification, DistilBertTokenizerFast

from routes import classify, embed, ner, rerank, summarize

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

EMBED_MODEL_NAME = "BAAI/bge-base-en-v1.5"
CROSS_ENCODER_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CLASSIFIER_BUCKET = "models"
CLASSIFIER_PREFIX = "classifier"


def _load_vault_secrets() -> dict:
    addr = os.environ["VAULT_ADDR"]
    token = os.environ["VAULT_ROOT_TOKEN"]
    client = hvac.Client(url=addr, token=token)
    if not client.is_authenticated():
        log.error("vault_auth_failed")
        sys.exit(1)
    data = client.secrets.kv.v2.read_secret_version(path="app", mount_point="secret")
    return data["data"]["data"]


def _download_classifier(minio_endpoint: str, access_key: str, secret_key: str, local_dir: str) -> None:
    client = Minio(minio_endpoint, access_key=access_key, secret_key=secret_key, secure=False)
    os.makedirs(local_dir, exist_ok=True)
    for obj in client.list_objects(CLASSIFIER_BUCKET, prefix=CLASSIFIER_PREFIX + "/", recursive=True):
        rel = obj.object_name[len(CLASSIFIER_PREFIX) + 1:]
        dest = os.path.join(local_dir, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        client.fget_object(CLASSIFIER_BUCKET, obj.object_name, dest)


def _verify_sha256(model_dir: str) -> None:
    card_path = os.path.join(model_dir, "model_card.json")
    weights_path = os.path.join(model_dir, "model.safetensors")
    if not os.path.exists(card_path) or not os.path.exists(weights_path):
        raise FileNotFoundError("classifier_files_missing")
    card = json.loads(open(card_path).read())
    expected = card.get("weights_sha256", "")
    actual = hashlib.sha256(open(weights_path, "rb").read()).hexdigest()
    if expected != actual:
        raise ValueError(f"sha256_mismatch expected={expected[:12]} actual={actual[:12]}")
    log.info("sha256_ok", sha=actual[:12])


def _setup_tracing(service_name: str) -> trace.Tracer:
    endpoint = os.environ.get("OTLP_ENDPOINT", "http://localhost:4317")
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor().instrument()
    return trace.get_tracer(service_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("modelserver_starting")
    secrets = _load_vault_secrets()
    minio_endpoint = os.environ["MINIO_ENDPOINT"]
    classifier_dir = "/tmp/classifier"

    tokenizer = None
    classifier = None
    try:
        log.info("downloading_classifier")
        _download_classifier(minio_endpoint, secrets["MINIO_ACCESS_KEY"], secrets["MINIO_SECRET_KEY"], classifier_dir)
        _verify_sha256(classifier_dir)
        log.info("loading_classifier")
        tokenizer = DistilBertTokenizerFast.from_pretrained(classifier_dir)
        classifier = DistilBertForSequenceClassification.from_pretrained(classifier_dir)
        classifier.eval()
        if torch.cuda.is_available():
            classifier = classifier.cuda()
    except Exception as e:
        log.warning("classifier_unavailable_using_llm_fallback", reason=str(e))

    # Classical model (optional — skip if not uploaded yet)
    classical_pipeline = None
    try:
        import joblib
        import io as _io
        minio_c = Minio(minio_endpoint, access_key=secrets["MINIO_ACCESS_KEY"],
                        secret_key=secrets["MINIO_SECRET_KEY"], secure=False)
        resp = minio_c.get_object("models", "classical/pipeline.joblib")
        classical_pipeline = joblib.load(_io.BytesIO(resp.read()))
        log.info("classical_model_loaded")
    except Exception as e:
        log.warning("classical_model_unavailable", reason=str(e))

    log.info("loading_embed_model", name=EMBED_MODEL_NAME)
    embed_model = SentenceTransformer(EMBED_MODEL_NAME)

    log.info("loading_cross_encoder", name=CROSS_ENCODER_NAME)
    cross_encoder = CrossEncoder(CROSS_ENCODER_NAME)

    model_name = "distilbert-base-uncased"
    if classifier is not None:
        card = json.loads(open(os.path.join(classifier_dir, "model_card.json")).read())
        model_name = card.get("architecture", model_name)
    app.state.tokenizer = tokenizer
    app.state.model = classifier
    app.state.model_name = model_name
    app.state.classical_pipeline = classical_pipeline
    app.state.embed_model = embed_model
    app.state.cross_encoder = cross_encoder
    app.state.llm_api_key = secrets["LLM_API_KEY"]
    app.state.tracer = _setup_tracing("modelserver")

    log.info("modelserver_ready")
    yield
    log.info("modelserver_shutdown")


app = FastAPI(title="Model Server", lifespan=lifespan)

app.include_router(classify.router)
app.include_router(ner.router)
app.include_router(summarize.router)
app.include_router(embed.router)
app.include_router(rerank.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled", error=str(exc), path=request.url.path)
    return JSONResponse(status_code=500, content={"error": "internal error"})
