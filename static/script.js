document.addEventListener('DOMContentLoaded', async () => {
    const sourceInput = document.getElementById('sourcePath');
    const targetInput = document.getElementById('targetPath');
    const sourceBadge = document.getElementById('sourceBadge');
    const targetBadge = document.getElementById('targetBadge');
    const browseSrcBtn = document.getElementById('browseSourceBtn');
    const browseTgtBtn = document.getElementById('browseTargetBtn');
    const autoSaveInd = document.getElementById('autoSaveIndicator');

    const dryRunToggle = document.getElementById('dryRunToggle');
    const copyToggle = document.getElementById('copyModeToggle');
    const runBtn = document.getElementById('runPipelineBtn');
    const statusDot = document.getElementById('statusDot');
    const appStatus = document.getElementById('appStatus');

    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    const progressText = document.getElementById('progressText');
    const activityFeed = document.getElementById('consoleOutput');

    const mProcessed = document.getElementById('metricProcessed');
    const mDuplicates = document.getElementById('metricDuplicates');
    const mConflicts = document.getElementById('metricConflicts');
    const mSkipped = document.getElementById('metricSkipped');

    async function validatePath(input, badge) {
        if (!input.value.trim()) {
            badge.innerText = 'Empty';
            badge.className = 'path-badge';
            return;
        }
        try {
            const res = await fetch(`/api/validate-path?path=${encodeURIComponent(input.value)}`);
            const data = await res.json();
            if (data.exists) {
                badge.innerText = `Valid (${data.file_count} files found)`;
                badge.className = 'path-badge valid';
            } else {
                badge.innerText = 'Path not found';
                badge.className = 'path-badge invalid';
            }
        } catch (e) {
            badge.innerText = 'Offline';
            badge.className = 'path-badge';
        }
    }

    async function autoSaveConfig() {
        autoSaveInd.innerText = "Syncing...";
        autoSaveInd.style.color = "var(--accent-amber)";
        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source_path: sourceInput.value,
                target_path: targetInput.value
            })
        });
        autoSaveInd.innerText = "Synced";
        autoSaveInd.style.color = "var(--accent-green)";
    }

    try {
        const res = await fetch('/api/config');
        const config = await res.json();
        sourceInput.value = config.source_path || '';
        targetInput.value = config.target_path || '';
        validatePath(sourceInput, sourceBadge);
        validatePath(targetInput, targetBadge);
    } catch (e) {
        console.error("Config fetch error", e);
    }

    browseSrcBtn.addEventListener('click', async () => {
        const res = await fetch(`/api/browse?initial_dir=${encodeURIComponent(sourceInput.value)}`);
        const data = await res.json();
        if (data.path) {
            sourceInput.value = data.path;
            validatePath(sourceInput, sourceBadge);
            autoSaveConfig();
        }
    });

    browseTgtBtn.addEventListener('click', async () => {
        const res = await fetch(`/api/browse?initial_dir=${encodeURIComponent(targetInput.value)}`);
        const data = await res.json();
        if (data.path) {
            targetInput.value = data.path;
            validatePath(targetInput, targetBadge);
            autoSaveConfig();
        }
    });

    sourceInput.addEventListener('change', () => { validatePath(sourceInput, sourceBadge); autoSaveConfig(); });
    targetInput.addEventListener('change', () => { validatePath(targetInput, targetBadge); autoSaveConfig(); });

    dryRunToggle.addEventListener('change', () => {
        if (dryRunToggle.checked) {
            runBtn.className = "btn btn-action preview-mode";
            runBtn.innerHTML = `<span class="btn-text">Run Safe Preview</span>`;
        } else {
            runBtn.className = "btn btn-action live-mode";
            runBtn.innerHTML = `<span class="btn-text">Start Media Sorting</span>`;
        }
    });

    function appendFeed(status, text) {
        const div = document.createElement('div');
        div.className = `feed-item ${status}`;
        div.innerHTML = `<span class="feed-tag">${status}</span> <span class="feed-text">${text}</span>`;
        activityFeed.appendChild(div);
        activityFeed.scrollTop = activityFeed.scrollHeight;
    }

    runBtn.addEventListener('click', () => {
        if (!dryRunToggle.checked) {
            const confirmRun = confirm("You are about to execute a live sort. Files will be organized into your destination archive. Proceed?");
            if (!confirmRun) return;
        }

        runBtn.disabled = true;
        appStatus.innerText = "Processing";
        statusDot.className = "pulse-dot running";
        activityFeed.innerHTML = '';
        progressBar.style.width = '0%';
        progressPercent.innerText = '0%';
        progressText.innerText = '0 / 0 Files';

        const dryRun = dryRunToggle.checked;
        const copyMode = copyToggle.checked;
        const url = `/api/stream?dry_run=${dryRun}&copy_mode=${copyMode}`;
        const eventSource = new EventSource(url);

        eventSource.onmessage = (e) => {
            const data = JSON.parse(e.data);

            if (data.type === "start") {
                progressText.innerText = `0 / ${data.total} Files`;
                appendFeed("SYSTEM", `Scanning complete. Found ${data.total} media captures.`);
            } else if (data.type === "progress") {
                const pct = Math.round((data.index / data.total) * 100);
                progressBar.style.width = `${pct}%`;
                progressPercent.innerText = `${pct}%`;
                progressText.innerText = `${data.index} / ${data.total} Files`;
                appendFeed(data.status, `${data.file} -> ${data.target}`);
            } else if (data.type === "done") {
                progressBar.style.width = '100%';
                progressPercent.innerText = '100%';

                mProcessed.innerText = data.summary.processed;
                mDuplicates.innerText = data.summary.duplicates;
                mConflicts.innerText = data.summary.conflicts;
                mSkipped.innerText = data.summary.skipped;

                appendFeed("SYSTEM", "Pipeline execution complete.");
                appStatus.innerText = "Completed";
                statusDot.className = "pulse-dot completed";
                runBtn.disabled = false;
                eventSource.close();
                validatePath(sourceInput, sourceBadge);
                validatePath(targetInput, targetBadge);
            } else if (data.type === "error") {
                appendFeed("SKIP", data.message);
                appStatus.innerText = "Error";
                statusDot.className = "pulse-dot";
                runBtn.disabled = false;
                eventSource.close();
            }
        };

        eventSource.onerror = () => {
            appendFeed("SKIP", "Connection to stream interrupted.");
            runBtn.disabled = false;
            eventSource.close();
        };
    });
});