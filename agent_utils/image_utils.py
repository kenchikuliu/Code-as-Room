"""
Image-processing utilities
==========================

Features:
1. Encode images as base64
2. Get image MIME types
3. Compress / resize images (keeping size near a target)

Usage:
    # Compress a single image
    python image_utils.py --input image.png --target-size 800

    # Compress an entire directory
    python image_utils.py --input-dir /path/to/images --target-size 800

    # Import as a module
    from image_utils import compress_image, compress_to_target_size
    compressed_path = compress_to_target_size("input.png", target_kb=800)
"""

import base64
import os
import sys
import argparse
from pathlib import Path
from typing import Optional, Tuple
from io import BytesIO

# Try to import Pillow
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Pillow is not installed; some image-processing features are unavailable")
    print("   Install: pip install Pillow")


# ============================================================================
# Basic helpers
# ============================================================================

def encode_image(image_path: str) -> str:
    """Encode an image as base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')


def get_image_mime_type(image_path: str) -> str:
    """Get the MIME type of an image"""
    ext = os.path.splitext(image_path)[1].lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    return mime_types.get(ext, 'image/jpeg')


def get_file_size_kb(file_path: str) -> float:
    """Return the file size in KB"""
    return os.path.getsize(file_path) / 1024


def get_image_info(image_path: str) -> dict:
    """Return basic info about an image"""
    info = {
        "path": image_path,
        "size_kb": get_file_size_kb(image_path),
        "mime_type": get_image_mime_type(image_path)
    }

    if PIL_AVAILABLE:
        with Image.open(image_path) as img:
            info["width"] = img.width
            info["height"] = img.height
            info["mode"] = img.mode
            info["format"] = img.format

    return info


# ============================================================================
# Image compression / resize
# ============================================================================

def resize_image(
    image_path: str,
    output_path: str = None,
    max_dimension: int = 2048,
    quality: int = 85
) -> str:
    """
    Resize an image so the longer side does not exceed `max_dimension`.

    Args:
        image_path: input image path
        output_path: output path (defaults to original name + _resized)
        max_dimension: maximum side length
        quality: JPEG quality (1-100)

    Returns:
        output file path
    """
    if not PIL_AVAILABLE:
        raise ImportError("Pillow is required: pip install Pillow")

    with Image.open(image_path) as img:
        # Compute scale ratio
        ratio = min(max_dimension / img.width, max_dimension / img.height)

        if ratio < 1:
            new_width = int(img.width * ratio)
            new_height = int(img.height * ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Build output path
        if output_path is None:
            base, ext = os.path.splitext(image_path)
            output_path = f"{base}_resized{ext}"

        # Make sure the output directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # Save
        if img.mode == 'RGBA' and output_path.lower().endswith(('.jpg', '.jpeg')):
            # JPEG does not support an alpha channel; convert to RGB
            img = img.convert('RGB')

        save_kwargs = {}
        if output_path.lower().endswith(('.jpg', '.jpeg')):
            save_kwargs['quality'] = quality
            save_kwargs['optimize'] = True
        elif output_path.lower().endswith('.png'):
            save_kwargs['optimize'] = True

        img.save(output_path, **save_kwargs)

    return output_path


def compress_image(
    image_path: str,
    output_path: str = None,
    quality: int = 85,
    max_dimension: int = None
) -> str:
    """
    Compress an image (lower JPEG quality, optional resize).

    Args:
        image_path: input image path
        output_path: output path
        quality: JPEG quality (1-100)
        max_dimension: max side length (None means no resize)

    Returns:
        output file path
    """
    if not PIL_AVAILABLE:
        raise ImportError("Pillow is required: pip install Pillow")

    with Image.open(image_path) as img:
        # Optional resize
        if max_dimension is not None:
            ratio = min(max_dimension / img.width, max_dimension / img.height, 1.0)
            if ratio < 1:
                new_width = int(img.width * ratio)
                new_height = int(img.height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Build output path
        if output_path is None:
            base, ext = os.path.splitext(image_path)
            # Standardize compressed output to JPEG
            output_path = f"{base}_compressed.jpg"

        # Make sure the output directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # Convert to RGB (JPEG cannot hold alpha)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        # Save as JPEG
        img.save(output_path, format='JPEG', quality=quality, optimize=True)

    return output_path


def compress_to_target_size(
    image_path: str,
    output_path: str = None,
    target_kb: int = 800,
    tolerance_kb: int = 100,
    min_quality: int = 30,
    max_quality: int = 95,
    min_dimension: int = 800,
    verbose: bool = True
) -> str:
    """
    Compress an image so its file size lands within a target range.

    Searches over scale factors and JPEG qualities (binary search on quality)
    until the encoded byte size lies within [target - tolerance, target + tolerance].

    Args:
        image_path: input image path
        output_path: output path (defaults to original name + _compressed)
        target_kb: target file size (KB)
        tolerance_kb: tolerance (KB); valid range is [target - tolerance, target + tolerance]
        min_quality: lower bound for JPEG quality
        max_quality: upper bound for JPEG quality
        min_dimension: minimum side length (will not resize below this)
        verbose: whether to print details

    Returns:
        output file path
    """
    if not PIL_AVAILABLE:
        raise ImportError("Pillow is required: pip install Pillow")

    original_size_kb = get_file_size_kb(image_path)

    if verbose:
        print(f"Source image: {image_path}")
        print(f"   Original size: {original_size_kb:.1f} KB")
        print(f"   Target size: {target_kb} KB (+/- {tolerance_kb} KB)")

    # Already in range -> just copy
    if target_kb - tolerance_kb <= original_size_kb <= target_kb + tolerance_kb:
        if verbose:
            print(f"Image is already within the target range; no compression needed")
        if output_path:
            import shutil
            shutil.copy(image_path, output_path)
            return output_path
        return image_path

    # Build output path
    if output_path is None:
        base, _ = os.path.splitext(image_path)
        output_path = f"{base}_compressed.jpg"

    # Make sure the output directory exists
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with Image.open(image_path) as img:
        original_width = img.width
        original_height = img.height

        # Convert to RGB
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        # Target range
        target_min = target_kb - tolerance_kb
        target_max = target_kb + tolerance_kb

        best_output = None
        best_size = float('inf')
        best_params = None

        # Try different scale + quality combinations
        scale_factors = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]

        for scale in scale_factors:
            new_width = max(int(original_width * scale), min_dimension)
            new_height = max(int(original_height * scale), min_dimension)

            # Skip smaller scales when both dims already hit min_dimension
            if new_width <= min_dimension and new_height <= min_dimension and scale < 1.0:
                continue

            # Resize
            if scale < 1.0:
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            else:
                resized_img = img.copy()

            # Binary-search the best quality
            low_q, high_q = min_quality, max_quality

            while low_q <= high_q:
                mid_q = (low_q + high_q) // 2

                # Encode into memory to check size
                buffer = BytesIO()
                resized_img.save(buffer, format='JPEG', quality=mid_q, optimize=True)
                size_kb = buffer.tell() / 1024

                if target_min <= size_kb <= target_max:
                    # In range -> save and return
                    resized_img.save(output_path, format='JPEG', quality=mid_q, optimize=True)
                    actual_size = get_file_size_kb(output_path)

                    if verbose:
                        print(f"Compression succeeded")
                        print(f"   scale: {scale*100:.0f}%")
                        print(f"   JPEG quality: {mid_q}")
                        print(f"   output size: {actual_size:.1f} KB")
                        print(f"   output dims: {new_width}x{new_height}")
                        print(f"   output path: {output_path}")

                    return output_path

                # Track the closest miss
                if abs(size_kb - target_kb) < abs(best_size - target_kb):
                    best_size = size_kb
                    best_params = (resized_img.copy(), mid_q, new_width, new_height, scale)

                if size_kb > target_max:
                    high_q = mid_q - 1
                else:
                    low_q = mid_q + 1

            # Cleanup
            if scale < 1.0:
                resized_img.close()

        # No exact match -> use the closest
        if best_params:
            best_img, best_q, best_w, best_h, best_scale = best_params
            best_img.save(output_path, format='JPEG', quality=best_q, optimize=True)
            actual_size = get_file_size_kb(output_path)

            if verbose:
                print(f"Could not hit the target exactly; using the closest result:")
                print(f"   scale: {best_scale*100:.0f}%")
                print(f"   JPEG quality: {best_q}")
                print(f"   output size: {actual_size:.1f} KB")
                print(f"   output dims: {best_w}x{best_h}")
                print(f"   output path: {output_path}")

            best_img.close()
            return output_path

    # All attempts failed; return the original
    if verbose:
        print(f"Compression failed; returning the source image")
    return image_path


def process_input_directory(
    input_dir: str,
    output_dir: str = None,
    target_kb: int = 800,
    verbose: bool = True
) -> dict:
    """
    Process every image in an input directory.

    Args:
        input_dir: input directory
        output_dir: output directory (defaults to <input_dir>/compressed)
        target_kb: target file size (KB)
        verbose: whether to print details

    Returns:
        a dict describing the result
    """
    input_path = Path(input_dir)

    if output_dir is None:
        output_dir = input_path / "compressed"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Supported formats
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

    results = {
        "processed": [],
        "skipped": [],
        "failed": []
    }

    image_files = [
        f for f in input_path.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ]

    if verbose:
        print(f"\nProcessing directory: {input_dir}")
        print(f"   found {len(image_files)} image(s)")
        print(f"   output directory: {output_dir}")
        print(f"   target size: {target_kb} KB")
        print("=" * 50)

    for img_file in image_files:
        output_path = output_dir / f"{img_file.stem}_compressed.jpg"

        try:
            original_size = get_file_size_kb(str(img_file))

            if verbose:
                print(f"\nProcessing: {img_file.name} ({original_size:.1f} KB)")

            result_path = compress_to_target_size(
                str(img_file),
                str(output_path),
                target_kb=target_kb,
                verbose=verbose
            )

            new_size = get_file_size_kb(result_path)

            results["processed"].append({
                "input": str(img_file),
                "output": result_path,
                "original_size_kb": original_size,
                "final_size_kb": new_size,
                "reduction": f"{(1 - new_size/original_size)*100:.1f}%" if original_size > 0 else "N/A"
            })

        except Exception as e:
            if verbose:
                print(f"Failed: {e}")
            results["failed"].append({
                "input": str(img_file),
                "error": str(e)
            })

    if verbose:
        print("\n" + "=" * 50)
        print(f"Done:")
        print(f"   succeeded: {len(results['processed'])}")
        print(f"   failed: {len(results['failed'])}")

    return results


# ============================================================================
# Convenience helpers for unified_pipeline
# ============================================================================

def prepare_image_for_pipeline(
    image_path: str,
    output_dir: str = None,
    target_kb: int = 800,
    verbose: bool = True
) -> str:
    """
    Prepare an image for the pipeline (compress to a reasonable size).

    Returns the original path if the image is already small enough; otherwise
    compresses and returns the new path.

    Args:
        image_path: input image path
        output_dir: output directory (defaults to <image_dir>/compressed)
        target_kb: target file size (KB)
        verbose: whether to print details

    Returns:
        the path of the prepared image
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image does not exist: {image_path}")

    current_size = get_file_size_kb(image_path)

    # Already in a reasonable range -> return as-is (allow 20% slack)
    if current_size <= target_kb * 1.2:
        if verbose:
            print(f"Image size is fine ({current_size:.1f} KB); skipping compression")
        return image_path

    # Build output path
    if output_dir is None:
        output_dir = Path(image_path).parent / "compressed"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{Path(image_path).stem}_compressed.jpg"

    return compress_to_target_size(
        image_path,
        str(output_path),
        target_kb=target_kb,
        verbose=verbose
    )


# ============================================================================
# Command-line entry
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Image-compression utility - compress images to a target size",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compress a single image to 800 KB
  python image_utils.py --input image.png --target-size 800

  # Compress an entire directory
  python image_utils.py --input-dir ./images --target-size 800

  # Specify the output path
  python image_utils.py --input image.png --output compressed.jpg --target-size 500

  # Show image info
  python image_utils.py --info image.png
"""
    )

    parser.add_argument("--input", "-i", help="input image path")
    parser.add_argument("--input-dir", "-d", help="input directory path")
    parser.add_argument("--output", "-o", help="output path")
    parser.add_argument("--output-dir", help="output directory")
    parser.add_argument("--target-size", "-s", type=int, default=800, help="target file size (KB)")
    parser.add_argument("--tolerance", "-t", type=int, default=100, help="tolerance (KB)")
    parser.add_argument("--info", help="show image info")
    parser.add_argument("--quiet", "-q", action="store_true", help="quiet mode")

    args = parser.parse_args()

    # Show image info
    if args.info:
        if not os.path.exists(args.info):
            print(f"File does not exist: {args.info}")
            return 1

        info = get_image_info(args.info)
        print(f"\nImage info: {args.info}")
        print(f"   size: {info['size_kb']:.1f} KB")
        print(f"   type: {info['mime_type']}")
        if PIL_AVAILABLE:
            print(f"   dims: {info['width']}x{info['height']}")
            print(f"   mode: {info['mode']}")
            print(f"   format: {info['format']}")
        return 0

    # Process a directory
    if args.input_dir:
        if not os.path.isdir(args.input_dir):
            print(f"Directory does not exist: {args.input_dir}")
            return 1

        process_input_directory(
            args.input_dir,
            args.output_dir,
            target_kb=args.target_size,
            verbose=not args.quiet
        )
        return 0

    # Process a single image
    if args.input:
        if not os.path.exists(args.input):
            print(f"File does not exist: {args.input}")
            return 1

        compress_to_target_size(
            args.input,
            args.output,
            target_kb=args.target_size,
            tolerance_kb=args.tolerance,
            verbose=not args.quiet
        )
        return 0

    # Default: process the agent_input directory
    default_input_dir = Path(__file__).parent.parent / "agent_input"
    if default_input_dir.exists():
        print(f"Using default input directory: {default_input_dir}")
        process_input_directory(
            str(default_input_dir),
            target_kb=args.target_size,
            verbose=not args.quiet
        )
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    exit(main())
