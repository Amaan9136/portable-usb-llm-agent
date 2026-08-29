Portable USB LLM Agent — Windows Runtime Binary
========================================

This folder must contain a llama.cpp Windows build (llama-server.exe)
before you can run Start-Model.bat with BACKEND=llama-server. It is NOT
included in this ZIP (it is a large compiled binary with its own
license, and bundling it would make this archive stale the moment
upstream ships a new release).

ALTERNATIVE: LLAMA.EXE ALREADY ON YOUR MACHINE
-----------------------------------------------------------
If you already have a "llama.exe" CLI build installed (e.g. one that
supports a `llama.exe serve -m ... -ngl ... -t ...` subcommand), you do
NOT need anything in this folder. Start-Model.bat auto-detects: if this
folder has no llama-server.exe, it falls back to running LLAMA_EXE
(default "llama.exe", resolved via PATH) with the "serve" subcommand
instead. Set LLAMA_EXE in .env to a full path if it isn't on PATH, or
set BACKEND=llama-cli to force this mode even when llama-server.exe is
also present. See the "Configuration reference" table in RUN.md.

PICK ANY BACKEND
-----------------------------------------------------------
This project is backend-agnostic — llama-server.exe from a CPU-only,
CUDA, Vulkan, ROCm, or any other llama.cpp Windows build all work the
same way here. Choose whichever matches your hardware. Pick ONE backend
and be consistent — don't mix DLLs from different backend builds in
this folder.

WHAT TO DOWNLOAD
-----------------
1. Go to the official llama.cpp GitHub Releases page:
   https://github.com/ggml-org/llama-cpp/releases
   (If that org/repo name has moved, search GitHub for "ggml-org llama.cpp"
   or "ggerganov llama.cpp" — the project has been renamed/reorganized
   before, so verify you're on the actual upstream repo, not a fork.)

2. Find a release asset matching your chosen backend, for example:
   - CPU-only: name contains "win" with no backend suffix, e.g.
               llama-<version>-bin-win-x64.zip
   - CUDA:     name contains "cuda" and "win", e.g.
               llama-<version>-bin-win-cuda-cu12.x-x64.zip
               Match the CUDA major version to what your NVIDIA driver
               supports.
   - Vulkan:   name contains "vulkan" and "win", e.g.
               llama-<version>-bin-win-vulkan-x64.zip
               Requires a Vulkan-capable GPU driver.
   Other backends (ROCm, SYCL, etc.) follow the same pattern if a
   Windows build is published for them.

3. Download and extract that ZIP. Copy AT MINIMUM:
     - llama-server.exe
   into this folder (runtime\windows\). If the release ships supporting
   DLLs (e.g. ggml.dll, backend runtime DLLs, or a loader DLL) alongside
   the executable, copy those into this same folder too —
   llama-server.exe will fail to start without them.

4. If llama-server.exe doesn't automatically pick the right GPU device
   (common on multi-GPU systems or with some Vulkan builds), you may
   need to pass a device selector. Run:
       llama-server.exe --list-devices
   to see available device indices/names, then set EXTRA_ARGS in .env,
   for example:
       EXTRA_ARGS=-dev Vulkan1
   (the exact index depends on your system's device list — do not
   assume any particular value is correct without checking
   --list-devices first).

VERIFYING YOU HAVE THE RIGHT BUILD
------------------------------------
Open a terminal in this folder and run:

    llama-server.exe --version

This should print a version string with no DLL-not-found errors. If you
see "The code execution cannot proceed because <name>.dll was not found",
you are missing a supporting DLL from the same release archive — go back
to step 3 and copy the rest of the extracted files here.

Then run scripts\verify_environment.py from the project root, which checks
that this executable is present.

WHY THIS ISN'T AUTOMATED
--------------------------
This project deliberately does not download binaries automatically:
  - No internet access is required or used during normal agent operation.
  - You should know exactly which binary you're running, from where.
  - Release URLs and filenames change between llama.cpp versions; a
    baked-in download link becomes wrong and misleading over time.

CPU-ONLY FALLBACK
--------------------
If you don't have a supported GPU or don't want to set one up, download
a plain CPU-only Windows build instead (same releases page, look for a
"win-x64" asset without a backend name in it). Set GPU_LAYERS=0 in
.env — the project will run entirely on CPU, more slowly. See RUN.md
for expected performance implications.