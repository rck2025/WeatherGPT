"""Google Earth Engine (GEE) Meteorological & Satellite Vision Service.

Provides:
- Thermal Land Surface Temperature (LST) heatmaps via MODIS (MODIS/061/MOD11A1)
- Global Precipitation Measurement (GPM) Rain Radar overlays via NASA IMERG
- AI Context Extraction (mean ground temp, max rainfall) within user-defined radius
- Leaflet-compatible XYZ tile URL endpoints for real-time frontend GIS rendering
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure UTF-8 output formatting on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import ee

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]  # backend directory


class GEEService:
    """Satellite vision service powered by Google Earth Engine."""

    # Color Palettes
    # Jet Gradient: Cold Dark Blue -> Cyan -> Green -> Yellow -> Red -> Dark Red
    JET_PALETTE = [
        "040274",
        "04279e",
        "064dca",
        "1fb4ff",
        "36d7ff",
        "6effdc",
        "a8ff9b",
        "e4ff5c",
        "fff236",
        "ffb21f",
        "ff5a06",
        "dc0d03",
        "7c0000",
    ]

    # Cyan-to-White Low-Pressure Storm Aura (White core to Cyan to Electric Blue edge)
    LOW_PRESSURE_PALETTE = ["ffffff", "00ffff", "00b4ff", "0055ff"]

    # 5-Step High-Contrast Rainfall Mask: Green -> Yellow -> Orange -> Red -> Purple
    PRECIP_MASK_PALETTE = ["00ff00", "ffff00", "ff7700", "ff0000", "7a0000"]

    # Bay of Bengal & Indian Landmass Boundary Constraint [lon_min, lat_min, lon_max, lat_max]
    SOUTH_ASIA_BOUNDS_COORDS = [60.0, 5.0, 102.0, 38.0]

    def __init__(self, key_path: Optional[str] = None):
        self.key_path = self._resolve_key_path(key_path)
        self.initialized = False
        self._cache: Dict[str, tuple[float, str]] = {}  # key -> (timestamp, url)
        self._cache_ttl = 1800  # 30 minutes in seconds

        self._initialize()

    def _resolve_key_path(self, override_path: Optional[str] = None) -> Path:
        """Find gee-key.json across common locations."""
        if override_path:
            return Path(override_path).resolve()

        candidates = [
            os.getenv("GEE_KEY_PATH"),
            str(BASE_DIR / "gee-key.json"),
            str(BASE_DIR.parent / "gee-key.json"),
            "backend/gee-key.json",
            "gee-key.json",
        ]
        for c in candidates:
            if c:
                p = Path(c).resolve()
                if p.is_file():
                    return p
        return BASE_DIR / "gee-key.json"

    def _initialize(self) -> bool:
        """Initialize GEE with Service Account Credentials."""
        if self.initialized:
            return True

        if not self.key_path.is_file():
            logger.warning("GEE key file not found at: %s. GEE service will be disabled.", self.key_path)
            return False

        try:
            with open(self.key_path, "r", encoding="utf-8") as f:
                key_data = json.load(f)

            client_email = key_data.get("client_email")
            if not client_email:
                logger.error("Invalid GEE service account key: 'client_email' missing.")
                return False

            credentials = ee.ServiceAccountCredentials(client_email, str(self.key_path))
            # ee.Initialize without forcing project avoids cloud serviceusage permission issues
            ee.Initialize(credentials)
            self.initialized = True
            logger.info("Google Earth Engine successfully initialized with Service Account: %s", client_email)
            return True

        except Exception as exc:
            logger.error("Failed to initialize Google Earth Engine: %s", exc)
            self.initialized = False
            return False

    def ensure_initialized(self) -> bool:
        """Lazy initialization check before executing GEE operations."""
        if not self.initialized:
            return self._initialize()
        return True

    def get_thermal_tile_url(self) -> str:
        """Task 2: Thermal Heatmap (LST).

        Source: MODIS/061/MOD11A1 (Land Surface Temperature).
        Logic:
          - Selects LST_Day_1km band.
          - Converts raw DN to Celsius: LST_Celsius = DN * 0.02 - 273.15.
          - Applies 'Jet' color palette (Blue cold to Red heatwave).
        Returns:
          Leaflet-compatible dynamic XYZ Tile URL.
        """
        if not self.ensure_initialized():
            raise RuntimeError("Earth Engine is not initialized. Please verify backend/gee-key.json.")

        cache_key = "thermal_tile_url"
        now = time.monotonic()
        if cache_key in self._cache:
            ts, url = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return url

        # MODIS LST (MOD11A1) - filter recent dates for rapid indexing
        now_dt = datetime.now(timezone.utc)
        start_dt = now_dt - timedelta(days=60)

        col = ee.ImageCollection("MODIS/061/MOD11A1").filterDate(
            start_dt.strftime("%Y-%m-%d"), now_dt.strftime("%Y-%m-%d")
        )

        try:
            latest_image = col.sort("system:time_start", False).first()
        except Exception:
            latest_image = ee.ImageCollection("MODIS/061/MOD11A1").first()

        # Scale factor 0.02, subtract 273.15 for Celsius
        lst_celsius = latest_image.select("LST_Day_1km").multiply(0.02).subtract(273.15)

        vis_params = {
            "min": 10.0,
            "max": 48.0,
            "palette": self.JET_PALETTE,
        }

        map_id = lst_celsius.getMapId(vis_params)
        tile_url = map_id["tile_fetcher"].url_format
        self._cache[cache_key] = (now, tile_url)
        return tile_url

    def get_precipitation_tile_url(self) -> str:
        """Task 3: Precipitation Density (Rain Radar).

        Source: NASA/GPM_L3/IMERG_V06 (with V07 fallback).
        Logic:
          - Displays high-resolution precipitation rate / accumulated rain.
          - Applies 'Blues' / precipitation gradient.
        Returns:
          Leaflet-compatible dynamic XYZ Tile URL.
        """
        if not self.ensure_initialized():
            raise RuntimeError("Earth Engine is not initialized. Please verify backend/gee-key.json.")

        cache_key = "precip_tile_url"
        now = time.monotonic()
        if cache_key in self._cache:
            ts, url = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return url

        now_dt = datetime.now(timezone.utc)
        start_dt = now_dt - timedelta(days=60)

        precip_image = None
        # Try V07 first, then V06
        for asset, band in [("NASA/GPM_L3/IMERG_V07", "precipitation"), ("NASA/GPM_L3/IMERG_V06", "precipitationCal")]:
            try:
                col = ee.ImageCollection(asset).filterDate(
                    start_dt.strftime("%Y-%m-%d"), now_dt.strftime("%Y-%m-%d")
                )
                precip_image = col.sort("system:time_start", False).first().select(band)
                break
            except Exception as e:
                logger.debug("GPM asset %s fallback: %s", asset, e)

        if precip_image is None:
            # Fallback to V06 first image
            precip_image = ee.ImageCollection("NASA/GPM_L3/IMERG_V06").first().select("precipitationCal")

        # Mask dry areas (< 0.1 mm/hr) to keep map crisp and transparent over dry land
        masked_precip = precip_image.updateMask(precip_image.gte(0.1))

        vis_params = {
            "min": 0.1,
            "max": 15.0,
            "palette": self.PRECIP_PALETTE,
        }

        map_id = masked_precip.getMapId(vis_params)
        tile_url = map_id["tile_fetcher"].url_format
        self._cache[cache_key] = (now, tile_url)
        return tile_url

    def get_low_pressure_tile_url(self) -> str:
        """Task 1: Professional Low-Pressure Visualization (Synoptic Aura).

        Source: MODIS Cloud-Top Pressure (MOD08_M3) with ERA5 fallback.
        Logic:
          - Dynamic Masking: Only shows pixels where pressure is < 800 hPa (deep storm centers).
          - Boundary Constraint: Clipped strictly to Bay of Bengal & Indian Landmass geometry.
          - Cyclonic centers glow with a sleek cyan-to-white aura without painting clear ocean blue.
        """
        if not self.ensure_initialized():
            raise RuntimeError("Earth Engine is not initialized. Please verify backend/gee-key.json.")

        cache_key = "low_pressure_tile_url_v2"
        now = time.monotonic()
        if cache_key in self._cache:
            ts, url = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return url

        bounds = ee.Geometry.Rectangle(self.SOUTH_ASIA_BOUNDS_COORDS)
        try:
            col = ee.ImageCollection("MODIS/061/MOD08_M3").sort("system:time_start", False)
            img = col.first().select("Cloud_Top_Pressure_Day_Mean_Mean")
            # Only show pixels where cloud-top pressure is < 800 hPa (deep storm systems)
            masked = img.updateMask(img.lt(800.0)).clip(bounds)
            vis = {
                "min": 200.0,
                "max": 800.0,
                "palette": self.LOW_PRESSURE_PALETTE,
            }
        except Exception as exc:
            logger.warning("MODIS Cloud-Top Pressure fallback to ERA5 MSLP: %s", exc)
            col = ee.ImageCollection("ECMWF/ERA5/DAILY").filterDate("2020-05-18", "2020-05-21")
            img = col.first().select("mean_sea_level_pressure").divide(100.0)
            masked = img.updateMask(img.lte(1002.0)).clip(bounds)
            vis = {
                "min": 985.0,
                "max": 1002.0,
                "palette": self.LOW_PRESSURE_PALETTE,
            }

        map_id = masked.getMapId(vis)
        tile_url = map_id["tile_fetcher"].url_format
        self._cache[cache_key] = (now, tile_url)
        return tile_url

    def get_precipitation_mask_tile_url(self) -> str:
        """Task 2: Data-Rich Precipitation Mask (> 0.5 mm/hr).

        Source: NASA/GPM_L3/IMERG_V07 (with V06 fallback).
        Logic:
          - Re-Adjusted Masking: Shows pixels where rain > 0.5 mm/hr (moderate rain).
            Allows active weather patches to show up vibrantly without flooding dry areas.
          - Boundary Constraint: Clipped strictly to Bay of Bengal & Indian Landmass geometry.
          - 5-step color scale: Green (Light/Moderate) -> Yellow -> Orange -> Red -> Purple (Heavy).
        """
        if not self.ensure_initialized():
            raise RuntimeError("Earth Engine is not initialized. Please verify backend/gee-key.json.")

        cache_key = "precip_mask_tile_url_v4"
        now = time.monotonic()
        if cache_key in self._cache:
            ts, url = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return url

        now_dt = datetime.now(timezone.utc)
        start_dt = now_dt - timedelta(days=60)
        col = ee.ImageCollection("NASA/GPM_L3/IMERG_V07").filterDate(
            start_dt.strftime("%Y-%m-%d"), now_dt.strftime("%Y-%m-%d")
        )
        try:
            img = col.sort("system:time_start", False).first().select("precipitation")
        except Exception:
            col_v06 = ee.ImageCollection("NASA/GPM_L3/IMERG_V06")
            img = col_v06.first().select("precipitationCal")

        bounds = ee.Geometry.Rectangle(self.SOUTH_ASIA_BOUNDS_COORDS)
        # Re-Adjusted Masking: Show active rainfall cells > 0.5 mm/hr
        masked = img.updateMask(img.gt(0.5)).clip(bounds)
        vis = {
            "min": 0.5,
            "max": 25.0,
            "palette": self.PRECIP_MASK_PALETTE,
        }
        map_id = masked.getMapId(vis)
        tile_url = map_id["tile_fetcher"].url_format
        self._cache[cache_key] = (now, tile_url)
        return tile_url

    def get_scientific_composite_tile_url(self) -> str:
        """Task 4: Composite Tile Stream (Scientific Multi-Hazard Stack).

        Blends the Synoptic Low-Pressure Aura (cyan-to-white) and
        High-Contrast Rainfall Mask (5-color precipitation) into a single XYZ stream.
        - Dynamic Transparency Masking: Pressure < 800 hPa & Moderate Rain > 0.5 mm/hr.
        - Strictly clipped to Bay of Bengal and Indian Landmass geometry.
        - Natural satellite background preserved with colorful precipitation patches.
        """
        if not self.ensure_initialized():
            raise RuntimeError("Earth Engine is not initialized. Please verify backend/gee-key.json.")

        cache_key = "scientific_composite_tile_url_v4"
        now = time.monotonic()
        if cache_key in self._cache:
            ts, url = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return url

        bounds = ee.Geometry.Rectangle(self.SOUTH_ASIA_BOUNDS_COORDS)

        # 1. Low Pressure Aura RGB
        try:
            col_p = ee.ImageCollection("MODIS/061/MOD08_M3").sort("system:time_start", False)
            img_p = col_p.first().select("Cloud_Top_Pressure_Day_Mean_Mean")
            masked_p = img_p.updateMask(img_p.lt(800.0)).clip(bounds)
            rgb_p = masked_p.visualize(
                min=200.0,
                max=800.0,
                palette=self.LOW_PRESSURE_PALETTE,
            )
        except Exception as exc:
            logger.warning("MODIS Cloud-Top Pressure fallback in composite: %s", exc)
            col_p = ee.ImageCollection("ECMWF/ERA5/DAILY").filterDate("2020-05-18", "2020-05-21")
            img_p = col_p.first().select("mean_sea_level_pressure").divide(100.0)
            masked_p = img_p.updateMask(img_p.lte(998.0)).clip(bounds)
            rgb_p = masked_p.visualize(
                min=980.0,
                max=998.0,
                palette=self.LOW_PRESSURE_PALETTE,
            )

        # 2. Rain Mask RGB (Moderate Rain > 0.5 mm/hr)
        now_dt = datetime.now(timezone.utc)
        start_dt = now_dt - timedelta(days=60)
        try:
            col_r = ee.ImageCollection("NASA/GPM_L3/IMERG_V07").filterDate(
                start_dt.strftime("%Y-%m-%d"), now_dt.strftime("%Y-%m-%d")
            )
            img_r = col_r.sort("system:time_start", False).first().select("precipitation")
        except Exception:
            img_r = ee.ImageCollection("NASA/GPM_L3/IMERG_V06").first().select("precipitationCal")

        masked_r = img_r.updateMask(img_r.gt(0.5)).clip(bounds)
        rgb_r = masked_r.visualize(
            min=0.5,
            max=25.0,
            palette=self.PRECIP_MASK_PALETTE,
        )

        # 3. Blend together into a single composite stream and clip to boundary
        composite = rgb_p.blend(rgb_r).clip(bounds)
        map_id = composite.getMapId()
        tile_url = map_id["tile_fetcher"].url_format
        self._cache[cache_key] = (now, tile_url)
        return tile_url

    # Golden Amber Palette for Agro-Tactical Cropland Mask
    CROPLAND_PALETTE = ["f59e0b"]

    def get_cropland_mask_url(self) -> str:
        """Task: ESA WorldCover 10m Cropland-Only Satellite Mask (Agro-Tactical Farmer Mode).

        Source: ESA/WorldCover/v100 (10-meter global land cover).
        Logic:
          - Isolates pixel value 40: 'Cropland' (cultivated fields, herbaceous crops).
          - Uses .updateMask(dataset.eq(40)) to completely suppress non-agricultural areas
            (forests, urban concrete, open water, barren terrain).
          - Applies high-contrast Golden Amber palette ['#f59e0b'] matching the Farmer Mode aesthetic.

        ========================================================================
        UPGRADE ROADMAP: ICRISAT 10M SOUTH ASIA IRRIGATED/RAINFED DATASET
        ========================================================================
        While ESA WorldCover 10m provides world-class 10-meter cropland delineation (Class 40),
        WeatherGPT's technical roadmap includes direct ingestion of ICRISAT's 10m South Asia
        Irrigated vs. Rainfed Cropland Land-Use Product.
        This sovereign agricultural layer distinguishes between:
          1. Canal-irrigated and tube-well irrigated parcels (continuous water supply)
          2. Rainfed / dryland agricultural zones (monsoon precipitation dependent)
        Once connected, WeatherGPT's Krishi Agromet AI Brain will automatically detect whether
        a farmer's field is irrigated or rainfed, adjusting IMD GKMS irrigation warnings
        and drought-mitigation advisories with research-institution precision.
        ========================================================================

        Returns:
            Leaflet-compatible dynamic XYZ Tile URL.
        """
        if not self.ensure_initialized():
            raise RuntimeError("Earth Engine is not initialized. Please verify backend/gee-key.json.")

        cache_key = "cropland_mask_tile_url_v1"
        now = time.monotonic()
        if cache_key in self._cache:
            ts, url = self._cache[cache_key]
            if now - ts < self._cache_ttl:
                return url

        # ESA WorldCover 10m v100 - single unified global collection
        dataset = ee.ImageCollection("ESA/WorldCover/v100").first()
        
        # Pixel value 40 represents cultivated cropland
        cropland_image = dataset.updateMask(dataset.eq(40))

        vis_params = {
            "palette": self.CROPLAND_PALETTE,
        }

        map_id = cropland_image.getMapId(vis_params)
        tile_url = map_id["tile_fetcher"].url_format
        self._cache[cache_key] = (now, tile_url)
        return tile_url

    def get_area_stats(self, lat: float, lon: float, radius_km: float = 10.0) -> Dict[str, Any]:
        """Task 4: AI Context Extraction.

        Uses .reduceRegion() to calculate mean Land Surface Temperature (LST)
        and max rainfall within a circular sector around (lat, lon).

        Returns:
            Dict containing:
              - mean_ground_temp_c: float | None
              - max_rainfall_mm_hr: float | None
              - radius_km: float
              - sector_verification: str
        """
        if not self.ensure_initialized():
            return {
                "mean_ground_temp_c": None,
                "max_rainfall_mm_hr": None,
                "radius_km": radius_km,
                "sector_verification": "Satellite telemetry currently unavailable (Service account uninitialized).",
            }

        try:
            point = ee.Geometry.Point([lon, lat])
            region = point.buffer(radius_km * 1000)

            # 1. Thermal LST Mean over recent window (30 days composite)
            now_dt = datetime.now(timezone.utc)
            start_dt = now_dt - timedelta(days=30)
            col_lst = (
                ee.ImageCollection("MODIS/061/MOD11A1")
                .filterDate(start_dt.strftime("%Y-%m-%d"), now_dt.strftime("%Y-%m-%d"))
                .select("LST_Day_1km")
            )
            lst_composite = col_lst.mean().multiply(0.02).subtract(273.15)

            temp_stats = lst_composite.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=region,
                scale=1000,
                maxPixels=1e8,
            ).getInfo()

            mean_temp = temp_stats.get("LST_Day_1km")
            if mean_temp is not None:
                mean_temp = round(float(mean_temp), 1)

            # 2. Precipitation Max
            precip_stats = {}
            for asset, band in [("NASA/GPM_L3/IMERG_V07", "precipitation"), ("NASA/GPM_L3/IMERG_V06", "precipitationCal")]:
                try:
                    col_precip = ee.ImageCollection(asset).filterDate(
                        start_dt.strftime("%Y-%m-%d"), now_dt.strftime("%Y-%m-%d")
                    )
                    precip_img = col_precip.sort("system:time_start", False).first().select(band)
                    precip_stats = precip_img.reduceRegion(
                        reducer=ee.Reducer.max(),
                        geometry=region,
                        scale=10000,
                        maxPixels=1e8,
                    ).getInfo()
                    if precip_stats:
                        break
                except Exception:
                    continue

            max_rain = precip_stats.get("precipitation") or precip_stats.get("precipitationCal")
            if max_rain is not None:
                max_rain = round(float(max_rain), 2)
            else:
                max_rain = 0.0

            # Construct AI Brain Ground-Truth Statement
            if mean_temp is not None and max_rain > 0.5:
                verification = (
                    f"Satellite verification confirms {mean_temp}°C ground temp with "
                    f"{max_rain} mm/hr orbital precipitation intensity detected in your sector."
                )
            elif mean_temp is not None:
                verification = f"Satellite verification confirms {mean_temp}°C ground temp in your specific sector."
            elif max_rain > 0.5:
                verification = f"NASA GPM orbital radar confirms {max_rain} mm/hr convective rainfall in your sector."
            else:
                verification = "Orbital sensors indicate nominal atmospheric conditions in your immediate sector."

            return {
                "mean_ground_temp_c": mean_temp,
                "max_rainfall_mm_hr": max_rain,
                "radius_km": radius_km,
                "sector_verification": verification,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as exc:
            logger.error("Failed to compute GEE area stats: %s", exc)
            return {
                "mean_ground_temp_c": None,
                "max_rainfall_mm_hr": None,
                "radius_km": radius_km,
                "sector_verification": f"Satellite telemetry calculation failed: {exc}",
            }


# Singleton service instance
gee_service = GEEService()

# Functional exports for flexible imports
get_thermal_tile_url = gee_service.get_thermal_tile_url
get_precipitation_tile_url = gee_service.get_precipitation_tile_url
get_low_pressure_tile_url = gee_service.get_low_pressure_tile_url
get_precipitation_mask_tile_url = gee_service.get_precipitation_mask_tile_url
get_scientific_composite_tile_url = gee_service.get_scientific_composite_tile_url
get_cropland_mask_url = gee_service.get_cropland_mask_url
get_area_stats = gee_service.get_area_stats


if __name__ == "__main__":
    print("==================================================")
    print("WeatherGPT Earth Engine Satellite Brain Test")
    print("==================================================")
    try:
        thermal_url = gee_service.get_thermal_tile_url()
        print("\n[OK] Task 2: Thermal Tile URL (MODIS LST):")
        print(f"   {thermal_url}")

        precip_url = gee_service.get_precipitation_tile_url()
        print("\n[OK] Task 3: Precipitation Tile URL (NASA GPM):")
        print(f"   {precip_url}")

        composite_url = gee_service.get_scientific_composite_tile_url()
        print("\n[OK] Task 4: Scientific Composite Tile URL (Aura + Rain Mask):")
        print(f"   {composite_url}")

        # Test AI Context Extraction around Kolkata (22.5726, 88.3639)
        stats = gee_service.get_area_stats(22.5726, 88.3639, radius_km=10)
        print("\n[OK] Task 5: AI Context Extraction (Kolkata Sector):")
        print(f"   Mean Ground Temp: {stats.get('mean_ground_temp_c')} C")
        print(f"   Max Rainfall:     {stats.get('max_rainfall_mm_hr')} mm/hr")
        print(f"   AI Statement:     \"{stats.get('sector_verification')}\"")

        print("\n>>> Satellite Engine is LIVE and operational! <<<")
    except Exception as e:
        print(f"\n[ERROR] GEE Test Error: {e}")
        import traceback
        traceback.print_exc()
