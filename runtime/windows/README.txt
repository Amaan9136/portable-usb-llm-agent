PortableCoder — Windows Runtime Binary
========================================

This folder must contain a CUDA-enabled llama.cpp Windows build before you
can run Start-Model.bat. It is NOT included in this ZIP (it is a large
compiled binary with its own license, and bundling it would make this
archive stale the moment upstream ships a new release).

PRIMARY BACKEND: CUDA (with a verified Vulkan fallback)
-----------------------------------------------------------
This project targets CUDA as the primary backend, per its design spec —
your NVIDIA driver (610.x) supports CUDA 12.x. A Vulkan-enabled build has
also been confirmed to work on this same hardware profile (RTX 3050
Laptop GPU, 4 GB VRAM) and is documented here as a working fallback if
you hit CUDA toolkit/driver mismatches. Pick ONE backend and be
consistent — don't mix DLLs from different backend builds in this folder.

WHAT TO DOWNLOAD
-----------------
1. Go to the official llama.cpp GitHub Releases page:
   https://github.com/ggml-org/llama-cpp/releases
   (If that org/repo name has moved, search GitHub for "ggml-org llama.cpp"
   or "ggerganov llama.cpp" — the project has been renamed/reorganized
   before, so verify you're on the actual upstream repo, not a fork.)

2. Find a release asset matching your chosen backend:
   - CUDA:   name contains "cuda" and "win", e.g.
             llama-<version>-bin-win-cuda-cu12.x-x64.zip
             Your NVIDIA driver (610.x) supports CUDA 12.x runtimes —
             pick a CUDA 12-targeted build, not CUDA 11.
   - Vulkan: name contains "vulkan" and "win", e.g.
             llama-<version>-bin-win-vulkan-x64.zip
             Requires a Vulkan-capable driver, which recent NVIDIA laptop
             drivers (including 610.x) provide.

3. Download and extract that ZIP. Copy AT MINIMUM:
     - llama-server.exe
   into this folder (runtime\windows\). If the release ships supporting
   DLLs (e.g. ggml.dll, cuda runtime DLLs like cudart64_*.dll, or Vulkan
   loader DLLs) alongside the executable, copy those into this same
   folder too — llama-server.exe will fail to start without them.

4. If using Vulkan and llama-server.exe doesn't automatically pick your
   GPU, you may need to pass a device selector. Run:
       llama-server.exe --list-devices
   to see available device indices/names, then set EXTRA_ARGS in
   .env.example, for example:
       EXTRA_ARGS=-dev Vulkan1
   (the exact index depends on your system's device list — do not assume
   Vulkan1 is correct without checking --list-devices first).

VERIFYING YOU HAVE THE RIGHT BUILD
------------------------------------
Open a terminal in this folder and run:

    llama-server.exe --version

This should print a version string with no DLL-not-found errors. If you
see "The code execution cannot proceed because <name>.dll was not found",
you are missing a supporting DLL from the same release archive — go back
to step 3 and copy the rest of the extracted files here.

Then run scripts\verify_environment.py from the project root, which checks
for this executable and reports whether it appears to be CUDA-enabled.

WHY THIS ISN'T AUTOMATED
--------------------------
This project deliberately does not download binaries automatically:
  - No internet access is required or used during normal agent operation.
  - You should know exactly which binary you're running, from where.
  - Release URLs and filenames change between llama.cpp versions; a
    baked-in download link becomes wrong and misleading over time.

CPU-ONLY FALLBACK
--------------------
If you cannot get a CUDA build working, download a plain CPU-only Windows
build instead (same releases page, look for a "win-x64" asset without
"cuda" in the name). The project works with GPU_LAYERS=0 in .env.example —
it will simply run entirely on CPU, more slowly. See README.md for
expected performance implications.
