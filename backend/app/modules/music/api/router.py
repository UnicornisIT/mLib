from fastapi import APIRouter

from app.modules.music.api.catalog import router as catalog_router
from app.modules.music.api.imports import router as imports_router
from app.modules.music.api.playlists import router as playlists_router
from app.modules.music.api.tracks import router as tracks_router

router = APIRouter(prefix="/music")
router.include_router(tracks_router)
router.include_router(catalog_router)
router.include_router(playlists_router)
router.include_router(imports_router)
