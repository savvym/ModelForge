from nta_backend.api.app import create_app
from nta_backend.core.logging_setup import configure_logging

configure_logging("api")

app = create_app()
