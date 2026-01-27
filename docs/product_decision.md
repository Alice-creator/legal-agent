# AI Image/Video Enhancer

A fast, open-source desktop application for AI-powered image and video enhancement using TensorRT acceleration.

## Why This Project?

**Problem:** Existing tools are either expensive (Topaz), complex (ComfyUI), or slow (CPU-based). Users want one-click enhancement with GPU acceleration.

**Solution:** A clean, modern desktop app that leverages TensorRT for blazing-fast inference on NVIDIA GPUs.

**Target users:**
- Content creators enhancing old footage
- E-commerce sellers batch processing product photos
- Anime fans upscaling/interpolating videos
- Anyone restoring old family photos/videos

## Tech Stack

| Layer | Technology | Reason |
|-------|------------|--------|
| Frontend | React 18 | Modern, familiar, component-based |
| Desktop | Tauri | Lightweight (~10MB), cross-platform |
| Backend | Rust | Performance, direct CUDA/TensorRT access |
| Inference | ONNX Runtime + TensorRT | 2-4x faster than PyTorch |

## Architecture

```
┌─────────────────────────────────────────┐
│              Tauri App                  │
├───────────────────┬─────────────────────┤
│     React 18      │        Rust         │
│    (Frontend)     │      (Backend)      │
│                   │                     │
│  - File picker    │  - ONNX Runtime     │
│  - Preview        │  - TensorRT EP      │
│  - Progress UI    │  - Image/Video I/O  │
│  - Settings       │  - GPU management   │
└───────────────────┴─────────────────────┘
```

## Features Roadmap

### Phase 1: MVP
- [ ] Load image → Upscale (Real-ESRGAN 4x) → Save
- [ ] Batch folder processing
- [ ] Before/after preview slider
- [ ] Basic video upscaling
- [ ] Progress bar with ETA

### Phase 2: Core Features
- [ ] Frame interpolation (RIFE) — 30fps → 60fps
- [ ] Background removal (RMBG/SAM)
- [ ] Denoise (image + video)
- [ ] Face enhancement (GFPGAN)
- [ ] Multiple model selection

### Phase 3: Power User
- [ ] Custom ONNX model import
- [ ] Processing queue
- [ ] Presets ("Anime 4x", "Photo Restore")
- [ ] CLI mode for automation

### Phase 4: Editor Features
- [ ] Crop/resize tools
- [ ] Basic filters
- [ ] Video timeline
- [ ] Audio passthrough
- [ ] Watermark

## Supported Models

| Task | Model | Format |
|------|-------|--------|
| Upscale (general) | Real-ESRGAN 4x | ONNX |
| Upscale (anime) | RealCUGAN / Waifu2x | ONNX |
| Frame interpolation | RIFE 4.x | ONNX |
| Face restoration | GFPGAN | ONNX |
| Background removal | RMBG v2 | ONNX |

## References

| Project | What to learn |
|---------|---------------|
| enhancr | UI/UX design, TensorRT integration |
| REAL-Video-Enhancer | Video pipeline, RIFE implementation |
| chaiNNer | Node architecture, model support |
| VideoJaNai | TensorRT + VapourSynth optimization |

## Distribution

- Open source on GitHub
- Pre-built binaries for Windows/Linux
- User brings their own NVIDIA GPU (Pascal+)
- TensorRT engines built on first run (per GPU)

---

*License: MIT (or GPL-3.0 for copyleft)*