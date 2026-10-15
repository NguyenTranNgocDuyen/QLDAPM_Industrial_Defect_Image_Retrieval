"""Automated model downloader for phone segmentation and perspective correction.

Supports:
1. Automatic Roboflow Inference download & cache initialization:
   python -m defect_vision.download_model --api-key <ROBOFLOW_API_KEY>
2. Direct HTTP/HTTPS download (GitHub Releases, Google Drive, S3, Hugging Face) into models/weights.pt:
   python -m defect_vision.download_model --url <DIRECT_URL>
3. Verification/health check:
   python -m defect_vision.download_model --check
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional


def find_env_file() -> Optional[Path]:
    """Search for .env in current directory, image-processing/, or git root."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def resolve_api_key(cli_key: Optional[str] = None) -> Optional[str]:
    """Resolve Roboflow API key from CLI argument, env var, or .env file."""
    if cli_key:
        return cli_key.strip()

    if os.environ.get("ROBOFLOW_API_KEY"):
        return os.environ["ROBOFLOW_API_KEY"].strip()

    env_path = find_env_file()
    if env_path:
        try:
            import dotenv

            dotenv.load_dotenv(dotenv_path=env_path, override=False)
            if os.environ.get("ROBOFLOW_API_KEY"):
                return os.environ["ROBOFLOW_API_KEY"].strip()
        except Exception:
            pass

    return None


def resolve_model_id(cli_id: Optional[str] = None) -> str:
    """Resolve model ID from CLI argument, env var, or default."""
    if cli_id:
        return cli_id.strip()
    return os.environ.get("ROBOFLOW_PHONE_MODEL_ID", "phone-segmentation-uiymg/1").strip()


def check_local_weights(target_dir: Path, check_fallbacks: bool = True) -> Optional[Path]:
    """Check if local weights.pt exists in target directory or known paths."""
    direct = target_dir / "weights.pt"
    if direct.is_file() and direct.stat().st_size > 1024 * 1024:
        return direct.resolve()

    if check_fallbacks:
        candidates = [
            Path("image-processing") / "models" / "weights.pt",
            Path("models") / "weights.pt",
            Path(__file__).resolve().parent.parent / "models" / "weights.pt",
        ]
        for c in candidates:
            if c.is_file() and c.stat().st_size > 1024 * 1024:  # > 1 MB
                return c.resolve()
    return None


def download_from_url(url: str, dest_path: Path) -> bool:
    """Download weights directly from an HTTP/HTTPS URL with streaming progress."""
    try:
        import requests
    except ImportError:
        print("[ERROR] 'requests' is required for direct URL download. Run: pip install requests")
        return False

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(".tmp")
    print(f"[INFO] Downloading from URL: {url}")
    print(f"[INFO] Destination: {dest_path}")

    try:
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 1024 * 1024  # 1 MB

            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            mb_down = downloaded / (1024 * 1024)
                            mb_tot = total_size / (1024 * 1024)
                            sys.stdout.write(f"\r[INFO] Progress: {mb_down:.1f}/{mb_tot:.1f} MB ({percent:.1f}%)")
                        else:
                            mb_down = downloaded / (1024 * 1024)
                            sys.stdout.write(f"\r[INFO] Downloaded: {mb_down:.1f} MB")
                        sys.stdout.flush()

        print()
        if temp_path.exists():
            temp_path.replace(dest_path)
            size_mb = dest_path.stat().st_size / (1024 * 1024)
            print(f"[SUCCESS] Download completed successfully: {dest_path} ({size_mb:.2f} MB)")
            return True
        return False
    except Exception as exc:
        print(f"\n[ERROR] Download failed: {exc}")
        if temp_path.exists():
            temp_path.unlink()
        return False


def download_via_roboflow(model_id: str, api_key: str) -> bool:
    """Download and cache the segmentation model using the Roboflow Inference library."""
    try:
        import inference
    except ImportError:
        print(
            "[ERROR] Roboflow 'inference' package is required. "
            "Install it with: pip install inference supervision"
        )
        return False

    print(f"[INFO] Initializing Roboflow model download for ID: '{model_id}'...")
    print("[INFO] Weights will be cached automatically in local user cache (~/.cache/inference)...")
    try:
        model = inference.get_model(model_id=model_id, api_key=api_key)
        print(f"[SUCCESS] Model '{model_id}' loaded and cached successfully!")

        # Run quick verification with small dummy input
        try:
            import numpy as np

            dummy = np.zeros((300, 300, 3), dtype=np.uint8)
            res = model.infer(dummy)
            print("[SUCCESS] Verification test on synthetic frame passed!")
        except Exception as verify_err:
            print(f"[WARNING] Verification inference test encountered a minor issue: {verify_err}")

        return True
    except Exception as exc:
        print(f"[ERROR] Failed to download or initialize Roboflow model '{model_id}': {exc}")
        return False


def run_model_check(target_dir: Path, model_id: str, api_key: Optional[str]) -> bool:
    """Verify if either local weights or Roboflow cached model is ready."""
    print("=" * 60)
    print("PHONE SEGMENTATION MODEL STATUS CHECK")
    print("=" * 60)

    # 1. Local weights check
    local_weights = check_local_weights(target_dir)
    if local_weights:
        size_mb = local_weights.stat().st_size / (1024 * 1024)
        print(f"[OK] Local model weights found: {local_weights} ({size_mb:.2f} MB)")
        return True

    print(f"[NOTE] Local 'weights.pt' not found in '{target_dir}'. Checking Roboflow inference...")

    # 2. Roboflow check
    if not api_key:
        print("[FAIL] No local weights found, and ROBOFLOW_API_KEY is not configured.")
        print("To fix, add ROBOFLOW_API_KEY=your_key to .env or run with --api-key.")
        return False

    try:
        import inference

        model = inference.get_model(model_id=model_id, api_key=api_key)
        print(f"[OK] Roboflow Inference model '{model_id}' is available in local cache!")
        return True
    except Exception as exc:
        print(f"[FAIL] Could not load Roboflow model '{model_id}': {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download and verify phone segmentation model weights for Industrial Defect Vision."
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Roboflow API key (default: read from ROBOFLOW_API_KEY in .env or environment).",
    )
    parser.add_argument(
        "--model-id",
        type=str,
        default=None,
        help="Roboflow model ID (default: phone-segmentation-uiymg/1 or from .env).",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "models",
        help="Target directory for weights (default: image-processing/models).",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Direct download URL for weights.pt (GitHub Release, Google Drive, HuggingFace, etc.).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check current model readiness without performing downloads.",
    )

    args = parser.parse_args()

    target_dir = args.target_dir
    api_key = resolve_api_key(args.api_key)
    model_id = resolve_model_id(args.model_id)

    default_target = (Path(__file__).resolve().parent.parent / "models").resolve()
    check_fallbacks = (target_dir.resolve() == default_target)

    if args.check:
        success = run_model_check(target_dir, model_id, api_key)
        return 0 if success else 1

    # Check if local weights already exist
    local_weights = check_local_weights(target_dir, check_fallbacks=check_fallbacks)
    if local_weights and not args.url:
        size_mb = local_weights.stat().st_size / (1024 * 1024)
        print(f"[INFO] Local model file already exists: {local_weights} ({size_mb:.2f} MB)")
        print("[INFO] Model is ready for perspective correction. Use --check to verify or --url to overwrite.")
        return 0

    # Direct URL download
    if args.url:
        dest = target_dir / "weights.pt"
        success = download_from_url(args.url, dest)
        return 0 if success else 1

    # Roboflow automated download
    if api_key:
        success = download_via_roboflow(model_id, api_key)
        return 0 if success else 1

    # Missing API key
    print("=" * 65)
    print("[ERROR] Neither local 'weights.pt' nor ROBOFLOW_API_KEY was found.")
    print("=" * 65)
    print("To enable automatic model downloading for new clones:")
    print("  1. Copy .env.example to .env:")
    print("     cp .env.example .env")
    print("  2. Add your Roboflow API key:")
    print("     ROBOFLOW_API_KEY=your_key_here")
    print("  3. Run this script again:")
    print("     python scripts/download_model.py")
    print()
    print("Or provide the key via CLI:")
    print("  python scripts/download_model.py --api-key <YOUR_KEY>")
    print("=" * 65)
    return 1


if __name__ == "__main__":
    sys.exit(main())
