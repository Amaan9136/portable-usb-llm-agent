export const html = `
<div id="cliModal" class="modal-overlay hidden">
  <div class="modal-card !max-w-2xl">
    <h3 class="font-display text-lg mb-3 flex items-center gap-2"><i class="fa-solid fa-terminal text-cyan" aria-hidden="true"></i>Command-line access</h3>
    <p class="text-dim text-xs mb-3 leading-relaxed">
      Everything this UI does is also available from a terminal, using the same running agent server.
    </p>
    <pre class="cli-block">python cli.py --task "add input validation" --project my-app</pre>
    <pre class="cli-block">python cli.py --task "run the test suite" --project my-app --allow-commands</pre>
    <pre class="cli-block">python cli.py --list-projects</pre>
    <pre class="cli-block">python cli.py --import "C:\\path\\to\\folder" --name my-app</pre>
    <pre class="cli-block">python cli.py --list-models</pre>
    <pre class="cli-block">python cli.py --model "llama3.2:latest" --backend ollama</pre>
    <pre class="cli-block">python cli.py --download-zip --project my-app</pre>
    <div class="flex justify-end mt-4">
      <button id="btnCloseCli" class="px-3 py-1.5 text-xs rounded border border-line text-dim hover:text-starlight transition-colors">Close</button>
    </div>
  </div>
</div>`;
