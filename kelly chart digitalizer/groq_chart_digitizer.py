#!/usr/bin/env python3
"""
groq_chart_digitizer.py
======================
A single-file Chart Digitizer using Groq API's free vision models.
Extracts data points from chart images (PNG, JPG, WEBP) and saves to CSV.

Supported Groq Vision Models:
  - meta-llama/llama-4-scout-17b-16e-instruct  (recommended: tool use + JSON mode)
  - qwen/qwen3.6-27b                          (multimodal, thinking mode)
  - llama-3.2-90b-vision-preview              (legacy but works)
  - llama-3.2-11b-vision-preview              (faster, lighter)

Usage:
    python groq_chart_digitizer.py <image_path> [output.csv]
    python groq_chart_digitizer.py chart.png
    python groq_chart_digitizer.py chart.png my_data.csv
    python groq_chart_digitizer.py --create-test          # Generate demo chart
    python groq_chart_digitizer.py --model meta-llama/llama-4-scout-17b-16e-instruct chart.png

Requirements:
    pip install groq python-dotenv pandas Pillow

Environment:
    GROQ_API_KEY=gsk_your_key_here
"""

import os
import sys
import json
import base64
import mimetypes
import argparse
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from dotenv import load_dotenv

# ═══════════════════════════════════════════════════════════════════════════
# SETUP LOGGING
# ═══════════════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("groq_chart_digitizer")

# ═══════════════════════════════════════════════════════════════════════════
# LOAD ENVIRONMENT
# ═══════════════════════════════════════════════════════════════════════════
# Load .env from the SAME folder as this script (not the current working dir)
script_dir = Path(__file__).parent.resolve()
env_path = script_dir / ".env"
load_dotenv(dotenv_path=env_path)

# Debug: show which .env file was loaded
if env_path.exists():
    logger.info(f"Loading .env from: {env_path}")
else:
    logger.warning(f".env file NOT found at: {env_path}")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    logger.error("=" * 60)
    logger.error("GROQ_API_KEY not found!")
    logger.error("Create a .env file with: GROQ_API_KEY=gsk_your_key")
    logger.error("Or set it as environment variable: export GROQ_API_KEY=gsk_...")
    logger.error("=" * 60)
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════
# IMPORT GROQ SDK
# ═══════════════════════════════════════════════════════════════════════════
try:
    from groq import Groq
except ImportError as e:
    logger.error("groq package not installed. Run: pip install groq")
    sys.exit(1)

try:
    import pandas as pd
except ImportError as e:
    logger.error("pandas not installed. Run: pip install pandas")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
# Available Groq vision models (as of 2026)
VISION_MODELS = {
    "llama-4-scout": "meta-llama/llama-4-scout-17b-16e-instruct",  # Best: tool use + JSON
    "qwen-27b": "qwen/qwen3.6-27b",                                  # Multimodal + thinking
    "llama-3.2-90b": "llama-3.2-90b-vision-preview",                 # Legacy, high quality
    "llama-3.2-11b": "llama-3.2-11b-vision-preview",                # Legacy, faster
}

DEFAULT_MODEL = VISION_MODELS["llama-4-scout"]
MAX_TOKENS = 4096  # Groq default limit for most models
TEMPERATURE = 0.1   # Low temp for precise extraction

# Image limits for Groq API
MAX_IMAGE_SIZE_MB = 4  # Base64 encoded images must be < 4MB
MAX_IMAGE_RESOLUTION = 33_177_600  # 33 megapixels total

# ═══════════════════════════════════════════════════════════════════════════
# TOOL SCHEMA: Forces model to output structured JSON
# Groq uses OpenAI-compatible function calling format
# ═══════════════════════════════════════════════════════════════════════════
EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "save_chart_data",
        "description": (
            "Saves the extracted data points from the chart into a structured format. "
            "Use this tool to output ALL extracted data points, axis labels, and metadata. "
            "Be extremely precise with numerical values."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chart_title": {
                    "type": "string",
                    "description": "The title of the chart, if visible"
                },
                "x_axis_label": {
                    "type": "string",
                    "description": "The label for the X axis (e.g., 'Year', 'Time (s)')"
                },
                "y_axis_label": {
                    "type": "string",
                    "description": "The label for the Y axis (e.g., 'Revenue ($)', 'Temperature (°C)')"
                },
                "x_axis_unit": {
                    "type": "string",
                    "description": "The unit of measurement for the X axis, if discernible (e.g., 'years', 'seconds', '$')"
                },
                "y_axis_unit": {
                    "type": "string",
                    "description": "The unit of measurement for the Y axis, if discernible (e.g., 'millions', '%', '°C')"
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["line", "bar", "scatter", "area", "pie", "histogram", "other"],
                    "description": "The type of chart"
                },
                "data_points": {
                    "type": "array",
                    "description": "All extracted data points from the chart. For bar charts, x is the category/label and y is the height/value.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "description": "The exact X-axis value (or index for categorical)"
                            },
                            "y": {
                                "type": "number",
                                "description": "The exact Y-axis value"
                            },
                            "label": {
                                "type": "string",
                                "description": "Optional label for this data point (e.g., category name, year as string)"
                            }
                        },
                        "required": ["x", "y"]
                    }
                },
                "notes": {
                    "type": "string",
                    "description": "Any observations, uncertainties, or special notes about the extraction"
                }
            },
            "required": ["x_axis_label", "y_axis_label", "chart_type", "data_points"]
        }
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """You are an expert Data Scientist and Chart Digitizer. Your task is to extract numerical data from the provided chart image with maximum precision.

STRICT DIRECTIVES:
1. Carefully examine the chart image to identify the X and Y axes, their scales, gridlines, and all plotted data points.
2. For line/scatter charts: extract every visible data point. For bar charts: extract the height/value of each bar.
3. Perform mathematical conversions from visual positions to actual chart values. Show your reasoning.
4. You MUST use the 'save_chart_data' function to output the final structured data.
5. Include axis units if visible (e.g., "M" for millions, "K" for thousands, "$", "%", "°C").
6. Be highly precise. Do not guess. If a value is ambiguous, note it in the 'notes' field.
7. If the chart has multiple series, extract all series or clearly label points.
8. For the Y-axis, if values are in thousands/millions, convert to actual numbers (e.g., 3.5M = 3500000).
"""

# ═══════════════════════════════════════════════════════════════════════════
# INITIALIZE GROQ CLIENT
# ═══════════════════════════════════════════════════════════════════════════
client = Groq(api_key=GROQ_API_KEY)


# ═══════════════════════════════════════════════════════════════════════════
# STEP 1: IMAGE ENCODING (Groq supports base64 data URLs)
# ═══════════════════════════════════════════════════════════════════════════
def encode_image(image_path: str) -> Tuple[str, str, int, int]:
    """
    Encode an image file to base64 for Groq API.
    Groq accepts base64 images as data URLs in the format:
    data:image/png;base64,...

    Args:
        image_path: Path to the image file

    Returns:
        Tuple of (base64_data_url, media_type, width, height)

    Raises:
        FileNotFoundError: If image doesn't exist
        ValueError: If image exceeds Groq size limits
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Detect MIME type
    media_type, _ = mimetypes.guess_type(str(path))
    if not media_type or not media_type.startswith("image/"):
        ext = path.suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
        }
        media_type = mime_map.get(ext, "image/png")
        logger.warning(f"Could not detect MIME type, assuming: {media_type}")

    # Read and encode
    with open(path, "rb") as f:
        image_bytes = f.read()

    # Check file size (before base64 encoding)
    file_size_mb = len(image_bytes) / (1024 * 1024)
    logger.info(f"Image file size: {file_size_mb:.2f} MB")

    # Base64 encoding increases size by ~33%
    estimated_b64_mb = file_size_mb * 1.37
    if estimated_b64_mb > MAX_IMAGE_SIZE_MB:
        logger.warning(
            f"Image may exceed Groq's 4MB base64 limit ({estimated_b64_mb:.2f} MB estimated). "
            f"Consider compressing or resizing."
        )

    base64_data = base64.b64encode(image_bytes).decode("utf-8")

    # Build data URL format required by Groq
    data_url = f"data:{media_type};base64,{base64_data}"

    # Validate image dimensions
    width, height = 0, 0
    try:
        from PIL import Image
        with Image.open(path) as img:
            width, height = img.size
            mp = (width * height) / 1_000_000
            logger.info(f"Image dimensions: {width}x{height} ({mp:.2f} MP)")

            if (width * height) > MAX_IMAGE_RESOLUTION:
                raise ValueError(
                    f"Image resolution ({width*height} pixels) exceeds Groq limit "
                    f"({MAX_IMAGE_RESOLUTION} pixels / 33 MP). Please resize."
                )
    except ImportError:
        logger.warning("Pillow not installed. Cannot validate image dimensions.")

    return data_url, media_type, width, height


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2: BUILD MESSAGE PAYLOAD (OpenAI-compatible format)
# ═══════════════════════════════════════════════════════════════════════════
def build_messages(
    image_data_url: str, 
    user_prompt: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Build the messages payload for Groq API.
    Uses OpenAI-compatible multimodal format with image_url type.
    """
    default_prompt = (
        "Please digitize this chart image. Extract all visible data points precisely, "
        "identify the axes and their labels/units, and output using the save_chart_data function. "
        "Convert any abbreviated units (K, M, B) to full numbers."
    )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": user_prompt or default_prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_data_url
                    }
                }
            ]
        }
    ]
    return messages


# ═══════════════════════════════════════════════════════════════════════════
# STEP 3: CALL GROQ API
# ═══════════════════════════════════════════════════════════════════════════
def call_groq(
    messages: List[Dict[str, Any]], 
    model: str = DEFAULT_MODEL,
    use_tools: bool = True
) -> Dict[str, Any]:
    """
    Send request to Groq API with tool use.

    Args:
        messages: OpenAI-compatible message list
        model: Groq model ID
        use_tools: Whether to enable function calling

    Returns:
        Dict with: 'tool_calls', 'content', 'usage', 'model'
    """
    logger.info(f"Sending request to Groq...")
    logger.info(f"  Model: {model}")
    logger.info(f"  Max tokens: {MAX_TOKENS}")
    logger.info(f"  Temperature: {TEMPERATURE}")
    logger.info(f"  Tool use: {'enabled' if use_tools else 'disabled'}")

    try:
        if use_tools:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=TEMPERATURE,
                max_completion_tokens=MAX_TOKENS,
                tools=[EXTRACTION_TOOL],
                tool_choice="auto",  # Let model decide, or use {"type": "function", "function": {"name": "save_chart_data"}} to force
                stream=False
            )
        else:
            # Fallback: JSON mode without tools
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=TEMPERATURE,
                max_completion_tokens=MAX_TOKENS,
                response_format={"type": "json_object"},
                stream=False
            )
    except Exception as e:
        logger.error(f"API request failed: {e}")
        raise

    # Extract response data
    message = response.choices[0].message
    usage = response.usage

    logger.info(f"Response received:")
    logger.info(f"  Prompt tokens: {usage.prompt_tokens}")
    logger.info(f"  Completion tokens: {usage.completion_tokens}")
    logger.info(f"  Total tokens: {usage.total_tokens}")

    result = {
        "tool_calls": getattr(message, "tool_calls", None),
        "content": message.content,
        "usage": {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens
        },
        "model": response.model
    }

    return result


# ═══════════════════════════════════════════════════════════════════════════
# STEP 4: PARSE TOOL OUTPUT & SAVE
# ═══════════════════════════════════════════════════════════════════════════
def parse_and_save(result: Dict[str, Any], output_path: str) -> pd.DataFrame:
    """
    Parse the tool output JSON, create DataFrame, and save to CSV.

    Args:
        result: The dict returned by call_groq()
        output_path: Path to save the CSV file

    Returns:
        pandas DataFrame of extracted data
    """
    tool_calls = result.get("tool_calls")
    content = result.get("content", "")

    # ─── CHECK FOR TOOL CALLS ────────────────────────────────────────────
    if tool_calls and len(tool_calls) > 0:
        logger.info("Model used tool calling ✓")

        # Find our save_chart_data tool call
        chart_data = None
        for tc in tool_calls:
            if tc.function.name == "save_chart_data":
                try:
                    chart_data = json.loads(tc.function.arguments)
                    logger.info("Successfully parsed tool arguments")
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse tool arguments: {e}")
                    logger.error(f"Raw: {tc.function.arguments[:500]}")
                    continue

        if not chart_data:
            raise ValueError("Model called tools but save_chart_data not found or invalid")

    # ─── FALLBACK: PARSE JSON FROM CONTENT ───────────────────────────────
    elif content:
        logger.warning("Model did not use tools. Attempting to parse JSON from content...")

        # Try to extract JSON from markdown code blocks or raw text
        try:
            # Look for JSON in code blocks
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                chart_data = json.loads(content[json_start:json_end].strip())
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                chart_data = json.loads(content[json_start:json_end].strip())
            else:
                # Try to find JSON object in text
                start_idx = content.find("{")
                end_idx = content.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    chart_data = json.loads(content[start_idx:end_idx+1])
                else:
                    raise ValueError("No JSON found in response")

            logger.info("Successfully parsed JSON from content")
        except Exception as e:
            logger.error(f"Failed to parse JSON from content: {e}")
            logger.error(f"Raw content: {content[:1000]}")
            raise ValueError("Could not extract structured data from model response")

    else:
        raise ValueError("No tool calls and no content in response")

    # ─── EXTRACT METADATA ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("EXTRACTED CHART METADATA:")
    print("=" * 60)
    print(f"  Title:     {chart_data.get('chart_title', 'N/A')}")
    print(f"  Type:      {chart_data.get('chart_type', 'N/A')}")
    print(f"  X-Axis:    {chart_data.get('x_axis_label', 'N/A')}")
    print(f"  X-Unit:    {chart_data.get('x_axis_unit', 'N/A')}")
    print(f"  Y-Axis:    {chart_data.get('y_axis_label', 'N/A')}")
    print(f"  Y-Unit:    {chart_data.get('y_axis_unit', 'N/A')}")
    if chart_data.get('notes'):
        print(f"  Notes:     {chart_data['notes'][:300]}")
    print("=" * 60)

    # ─── BUILD DATAFRAME ─────────────────────────────────────────────────
    data_points = chart_data.get("data_points", [])
    if not data_points:
        raise ValueError("No data points were extracted")

    df = pd.DataFrame(data_points)

    # Reorder columns for readability
    cols = ["x", "y"]
    if "label" in df.columns:
        cols = ["label", "x", "y"]
    df = df[[c for c in cols if c in df.columns]]

    print(f"\nExtracted {len(df)} data points:")
    print(df.to_string())

    # ─── SAVE TO CSV ─────────────────────────────────────────────────────
    df.to_csv(output_path, index=False)
    logger.info(f"DataFrame saved to: {os.path.abspath(output_path)}")

    return df


# ═══════════════════════════════════════════════════════════════════════════
# STEP 5: MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════
def digitize_chart(
    image_path: str,
    output_path: Optional[str] = None,
    user_prompt: Optional[str] = None,
    model: str = DEFAULT_MODEL
) -> pd.DataFrame:
    """
    Main entry point: encode image, call Groq, parse results, save CSV.

    Args:
        image_path: Path to chart image
        output_path: Optional custom CSV output path
        user_prompt: Optional custom prompt to guide extraction
        model: Groq model ID to use

    Returns:
        pandas DataFrame of extracted data
    """
    if output_path is None:
        stem = Path(image_path).stem
        output_path = f"{stem}_data.csv"

    print(f"\n{'='*60}")
    print("CHART DIGITIZER — Groq API (Free Tier)")
    print(f"{'='*60}")
    print(f"Input:  {image_path}")
    print(f"Output: {output_path}")
    print(f"Model:  {model}")
    print(f"{'='*60}\n")

    # Step 1: Encode image
    logger.info("Step 1: Encoding image for Groq...")
    data_url, media_type, width, height = encode_image(image_path)
    logger.info(f"  MIME type: {media_type}")
    logger.info(f"  Data URL length: {len(data_url)} chars")

    # Step 2: Build messages
    logger.info("Step 2: Building API payload...")
    messages = build_messages(data_url, user_prompt)

    # Step 3: Call Groq
    logger.info("Step 3: Calling Groq API (fast inference)...")
    result = call_groq(messages, model=model)

    # Step 4: Parse and save
    logger.info("Step 4: Parsing results...")
    df = parse_and_save(result, output_path)

    print(f"\n{'='*60}")
    print("SUCCESS! Chart digitized.")
    print(f"{'='*60}")
    print(f"CSV saved: {os.path.abspath(output_path)}")
    print(f"Rows: {len(df)}")
    print(f"Tokens used: {result['usage']['total_tokens']}")
    print(f"{'='*60}\n")

    return df


# ═══════════════════════════════════════════════════════════════════════════
# STEP 6: CREATE A TEST CHART
# ═══════════════════════════════════════════════════════════════════════════
def create_test_chart(output_path: str = "test_chart.png") -> str:
    """
    Generate a simple test chart so you can verify the digitizer works.
    Requires matplotlib.
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        logger.error("matplotlib and numpy required for test chart. Run: pip install matplotlib numpy")
        sys.exit(1)

    # Create sample data: exponential growth
    years = np.arange(2015, 2026)
    revenue = np.array([1.2, 1.5, 1.8, 2.3, 2.9, 3.5, 4.2, 5.1, 6.3, 7.8, 9.5])

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(years, revenue, marker='o', linewidth=2, markersize=8, color='#2E86AB')
    ax.fill_between(years, revenue, alpha=0.3, color='#2E86AB')

    ax.set_xlabel("Year", fontsize=12)
    ax.set_ylabel("Revenue ($M)", fontsize=12)
    ax.set_title("Company Revenue Growth (2015-2025)", fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_xticks(years)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    logger.info(f"Test chart created: {os.path.abspath(output_path)}")
    return output_path


# ═══════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="Digitize chart images using Groq API vision models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  python groq_chart_digitizer.py chart.png
  python groq_chart_digitizer.py chart.png output.csv
  python groq_chart_digitizer.py --create-test
  python groq_chart_digitizer.py --model llama-3.2-90b chart.png

Available models:
  llama-4-scout  : {VISION_MODELS['llama-4-scout']}  (default, supports tools)
  qwen-27b       : {VISION_MODELS['qwen-27b']}  (multimodal)
  llama-3.2-90b  : {VISION_MODELS['llama-3.2-90b']}  (high quality)
  llama-3.2-11b  : {VISION_MODELS['llama-3.2-11b']}  (fast, light)
        """
    )
    parser.add_argument("image", nargs="?", help="Path to chart image")
    parser.add_argument("output", nargs="?", help="Output CSV path (optional)")
    parser.add_argument("--create-test", action="store_true", help="Create a test chart and exit")
    parser.add_argument("--model", choices=list(VISION_MODELS.keys()), 
                        default="llama-4-scout", help="Groq vision model to use")
    parser.add_argument("--prompt", help="Custom extraction prompt")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--no-tools", action="store_true", 
                        help="Disable tool use (fallback to JSON mode)")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create test chart mode
    if args.create_test:
        path = args.image or "test_chart.png"
        create_test_chart(path)
        print(f"\nTest chart saved to: {os.path.abspath(path)}")
        print("Now run: python groq_chart_digitizer.py", path)
        return

    # Validate image path
    if not args.image:
        parser.print_help()
        sys.exit(1)

    if not Path(args.image).exists():
        logger.error(f"File not found: {args.image}")
        sys.exit(1)

    # Resolve model ID
    model_id = VISION_MODELS[args.model]

    # Run digitizer
    try:
        df = digitize_chart(
            image_path=args.image,
            output_path=args.output,
            user_prompt=args.prompt,
            model=model_id
        )
    except FileNotFoundError as e:
        logger.error(f"File error: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Data extraction error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
