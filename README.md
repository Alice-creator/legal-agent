# Real Studio

> A fast, open-source desktop application for AI-powered image and video enhancement using TensorRT acceleration.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tauri](https://img.shields.io/badge/Tauri-2.0-blue.svg)](https://tauri.app/)
[![React](https://img.shields.io/badge/React-18-61dafb.svg)](https://reactjs.org/)
[![Rust](https://img.shields.io/badge/Rust-1.70+-orange.svg)](https://www.rust-lang.org/)

## Why Real Studio?

**Problem:** Existing tools are either expensive, complex, or slow.

**Solution:** A clean, modern desktop app that leverages TensorRT for blazing-fast inference on NVIDIA GPUs.

### Target Users
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

## Project Structure

```
real-studio/
├── src/                    # Frontend (React 18)
│   ├── components/        # UI components
│   │   ├── common/       # Reusable components
│   │   ├── upscaler/     # Upscaling UI
│   │   ├── video/        # Video processing UI
│   │   ├── preview/      # Before/after preview
│   │   ├── batch/        # Batch processing UI
│   │   ├── queue/        # Processing queue UI
│   │   └── settings/     # Settings panel
│   ├── hooks/            # React custom hooks
│   ├── utils/            # Frontend utilities
│   └── styles/           # CSS/SCSS
│
├── src-tauri/             # Backend (Rust)
│   └── src/
│       ├── inference/    # AI inference engine
│       │   ├── tensorrt/ # TensorRT execution
│       │   └── onnx/     # ONNX runtime
│       ├── video/        # Video processing
│       ├── image/        # Image processing
│       ├── models/       # Model management
│       └── gpu/          # GPU management
│
├── models/                # AI Models (ONNX)
│   ├── upscaler/         # Real-ESRGAN, CUGAN
│   ├── interpolation/    # RIFE
│   ├── face/             # GFPGAN
│   └── background/       # RMBG
│
└── docs/                  # Documentation
```

## Prerequisites

- **OS:** Windows 10+ or Linux
- **GPU:** NVIDIA GPU (Pascal architecture or newer)
- **CUDA:** 11.8 or higher
- **TensorRT:** 8.6 or higher
- **Node.js:** 18+
- **Rust:** 1.70+

## Installation

### For Users

Download the latest release from [Releases](https://github.com/Alice-creator/real-studio/releases).

TensorRT engines will be built automatically on first run (per GPU model).

### For Developers

1. **Clone the repository**
   ```bash
   git clone https://github.com/Alice-creator/real-studio.git
   cd real-studio
   ```

2. **Install frontend dependencies**
   ```bash
   npm install
   ```

3. **Install Rust dependencies**
   ```bash
   cd src-tauri
   cargo build
   ```

4. **Download AI models**
   ```bash
   npm run download-models
   ```

5. **Run in development mode**
   ```bash
   npm run tauri dev
   ```

## Development

### Build for Production
```bash
npm run tauri build
```

### Run Tests
```bash
# Frontend tests
npm test

# Backend tests
cd src-tauri
cargo test
```

### Code Formatting
```bash
# Format React code
npm run format

# Format Rust code
cd src-tauri
cargo fmt
```

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Real-ESRGAN team for the upscaling models
- ONNX Runtime team for inference engine
- Tauri team for the desktop framework
- All contributors and testers

---

**Note:** This project requires an NVIDIA GPU for optimal performance. TensorRT engines are built on first run and cached for your specific GPU.