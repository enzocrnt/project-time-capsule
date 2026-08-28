document.addEventListener('DOMContentLoaded', async () => {
    const sourceInput = document.getElementById('sourcePath');
    const targetInput = document.getElementById('targetPath');
    const sourceBadge = document.getElementById('sourceBadge');
    const targetBadge = document.getElementById('targetBadge');
    const browseSrcBtn = document.getElementById('browseSourceBtn');
    const browseTgtBtn = document.getElementById('browseTargetBtn');
    const autoSaveInd = document.getElementById('autoSaveIndicator');
    const openTargetBtn = document.getElementById('openTargetBtn');

    const thumbnailStrip = document.getElementById('thumbnailStrip');
    const previewCount = document.getElementById('previewCount');

    const dryRunToggle = document.getElementById('dryRunToggle');
    const copyToggle = document.getElementById('copyModeToggle');
    const runBtn = document.getElementById('runPipelineBtn');
    const abortBtn = document.getElementById('abortBtn');
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
    const metricCards = document.querySelectorAll('.metric-card');

    let currentEventSource = null;

    // 1. Fetch & Render Thumbnail Strip
    async function loadThumbnails(path) {
        if (!path || !path.trim()) {
            thumbnailStrip.innerHTML = `<div class="empty-strip">Select a valid source folder with media to preview captures.</div>`;
            previewCount.innerText = '0 files';
            return;
        }
        try {
            const res = await fetch(`/api/incoming-files?path=${encodeURIComponent(path)}&limit=20`);
            const data = await res.json();
            if (!data.files || data.files.length === 0) {
                thumbnailStrip.innerHTML = `<div class="empty-strip">No photos or videos found in selected folder.</div>`;
                previewCount.innerText = '0 files';
                return;
            }

            previewCount.innerText = `${data.files.length} previewed`;
            thumbnailStrip.innerHTML = '';
            data.files.forEach(f => {
                const card = document.createElement('div');
                card.className = 'thumb-card';
                card.title = `${f.name} (${f.size_mb} MB)`;

                if (f.type === 'image') {
                    const img = document.createElement('img');
                    img.src = `/api/thumbnail?path=${encodeURIComponent(path)}&file=${encodeURIComponent(f.rel_path)}`;
                    img.alt = f.name;
                    img.onerror = () => {
                        card.innerHTML = `<span class="thumb-video-icon">IMG</span><span class="thumb-card-size">${f.size_mb}MB</span>`;
                    };
                    card.appendChild(img);
                } else {
                    card.innerHTML = `<span class="thumb-video-icon">VID</span><span class="thumb-card-size">${f.size_mb}MB</span>`;
                }
                thumbnailStrip.appendChild(card);
            });
        } catch (e) {
            thumbnailStrip.innerHTML = `<div class="empty-strip">Unable to load media preview.</div>`;
        }
    }

    // 2. Path Validation & Auto-Save
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

    // 3. Initial Load
    try {
        const res = await fetch('/api/config');
        const config = await res.json();
        sourceInput.value = config.source_path || '';
        targetInput.value = config.target_path || '';
        validatePath(sourceInput, sourceBadge);
        validatePath(targetInput, targetBadge);
        loadThumbnails(sourceInput.value);
    } catch (e) {
        console.error("Config fetch error", e);
    }

    // Directory Browser Handlers
    browseSrcBtn.addEventListener('click', async () => {
        const res = await fetch(`/api/browse?initial_dir=${encodeURIComponent(sourceInput.value)}`);
        const data = await res.json();
        if (data.path) {
            sourceInput.value = data.path;
            validatePath(sourceInput, sourceBadge);
            loadThumbnails(data.path);
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

    sourceInput.addEventListener('change', () => {
        validatePath(sourceInput, sourceBadge);
        loadThumbnails(sourceInput.value);
        autoSaveConfig();
    });
    targetInput.addEventListener('change', () => {
        validatePath(targetInput, targetBadge);
        autoSaveConfig();
    });

    openTargetBtn.addEventListener('click', async () => {
        if (!targetInput.value.trim()) return;
        await fetch('/api/open-folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: targetInput.value })
        });
    });

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
        div.dataset.status = status;
        div.innerHTML = `<span class="feed-tag">${status}</span> <span class="feed-text">${text}</span>`;
        activityFeed.appendChild(div);
        activityFeed.scrollTop = activityFeed.scrollHeight;
    }

    // 4. Metric Filter Click Handler
    metricCards.forEach(card => {
        card.addEventListener('click', () => {
            metricCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            const filter = card.dataset.filter;

            const feedItems = activityFeed.querySelectorAll('.feed-item');
            feedItems.forEach(item => {
                const itemStatus = item.dataset.status;
                if (filter === 'ALL' || itemStatus === 'SYSTEM' || itemStatus === filter) {
                    item.classList.remove('hidden');
                } else {
                    item.classList.add('hidden');
                }
            });
        });
    });

    // 5. Abort Sorting
    abortBtn.addEventListener('click', async () => {
        await fetch('/api/abort', { method: 'POST' });
        abortBtn.disabled = true;
        abortBtn.innerText = "Aborting...";
    });

    // 6. Live Sorting Pipeline Trigger
    runBtn.addEventListener('click', () => {
        if (!dryRunToggle.checked) {
            const confirmRun = confirm("You are about to execute a live sort. Files will be organized into your destination archive. Proceed?");
            if (!confirmRun) return;
        }

        runBtn.disabled = true;
        abortBtn.disabled = false;
        abortBtn.classList.add('active');
        abortBtn.innerText = "Abort";

        appStatus.innerText = "Processing";
        statusDot.className = "pulse-dot running";
        activityFeed.innerHTML = '';
        progressBar.style.width = '0%';
        progressPercent.innerText = '0%';
        progressText.innerText = '0 / 0 Files';

        const dryRun = dryRunToggle.checked;
        const copyMode = copyToggle.checked;
        const url = `/api/stream?dry_run=${dryRun}&copy_mode=${copyMode}`;
        currentEventSource = new EventSource(url);

        currentEventSource.onmessage = (e) => {
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
            } else if (data.type === "aborted") {
                appendFeed("SKIP", "Sorting process was aborted by user.");
                appStatus.innerText = "Aborted";
                statusDot.className = "pulse-dot aborted";
                finalizeRun();
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
                finalizeRun();
            } else if (data.type === "error") {
                appendFeed("SKIP", data.message);
                appStatus.innerText = "Error";
                statusDot.className = "pulse-dot";
                finalizeRun();
            }
        };

        currentEventSource.onerror = () => {
            appendFeed("SKIP", "Connection stream closed.");
            finalizeRun();
        };

        function finalizeRun() {
            runBtn.disabled = false;
            abortBtn.disabled = true;
            abortBtn.classList.remove('active');
            abortBtn.innerText = "Cancel";
            if (currentEventSource) currentEventSource.close();
            validatePath(sourceInput, sourceBadge);
            validatePath(targetInput, targetBadge);
            loadThumbnails(sourceInput.value);
        }
    });
});