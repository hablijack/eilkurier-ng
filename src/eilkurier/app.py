from typing import Annotated

from fastapi import Depends, FastAPI, Response

from eilkurier import __version__
from eilkurier.render import EditionRenderer, Theme
from eilkurier.settings import Settings, get_settings

API_PREFIX = "/api/v1"


def get_renderer(settings: Annotated[Settings, Depends(get_settings)]) -> EditionRenderer:
    return EditionRenderer(settings.resource_root)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Eilkurier API",
        version=__version__,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )

    @app.get("/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    def ready() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        f"{API_PREFIX}/samples/edition.pdf",
        tags=["samples"],
        response_class=Response,
        responses={200: {"content": {"application/pdf": {}}, "description": "Sample edition as PDF"}},
    )
    def sample_edition_pdf(
        renderer: Annotated[EditionRenderer, Depends(get_renderer)],
        theme: Theme = Theme.KLASSISCH,
    ) -> Response:
        """Typesets the bundled sample edition in the given theme (layout preview)."""
        pdf = renderer.render_pdf(renderer.sample_edition(theme))
        return Response(
            pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="eilkurier-beispiel-{theme.value}.pdf"'},
        )

    return app
