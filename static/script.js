document.addEventListener('DOMContentLoaded', async () => {
    const profileTabsContainer = document.getElementById('profileTabsContainer');
    const profileNameInput = document.getElementById('profileNameInput');
    const sourceInput = document.getElementById('sourcePath');
    const targetInput = document.getElementById('targetPath');
    const sourceBadge = document.getElementById('sourceBadge');
    const targetBadge = document.getElementById('targetBadge');
    const browseSrcBtn = document.getElementById('browseSourceBtn');
    const browseTgtBtn = document.getElementById('browseTargetBtn');
    const autoSaveInd = document.getElementById('autoSaveIndicator');
    const openTargetBtn = document.getElementById('openTargetBtn');
    const undoBtn = document.getElementById('undoBtn');

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
    const speedTimer = document.getElementById('speedTimer');
    const activityFeed = document.getElementById('consoleOutput');

    const mProcessed = document.getElementById('metricProcessed');
    const mDuplicates = document.getElementById('metricDuplicates');
    const mConflicts = document.getElementById('metricConflicts');
    const mSkipped = document.getElementById('metricSkipped');
    const mSizeProcessed = document.getElementById('metricSizeProcessed');
    const mSizeSaved = document.getElementById('metricSizeSaved');
    const metricCards = document.querySelectorAll('.metric-card');

    let currentEventSource = null;
    let startTime = null;
    let accumulatedBytes = 0;
    let loadedConfig = null;
    let activeProfile = "mobile";

    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0.0 MB';
        const mb = bytes / (1024 * 1024);
        if (mb >= 1024) {
            return (mb / 1024).toFixed(2) + ' GB';
        }
        return mb.toFixed(1) + ' MB';
    }

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
                thumbnailStrip.innerHTML = `<div class="empty-strip">No photos, camera RAWs, or videos found.</div>`;
                previewCount.innerText = '0 files';
                return;
            }

            previewCount.innerText = `${data.files.length} previewed`;
            thumbnailStrip.innerHTML = '';
            data.files.forEach(f => {
                const card = document.createElement('div');
                card.className = 'thumb-card';
                card.title = `${f.name} (${f.size_mb} MB)`;

                if (f.type === 'image' && !['ARW', 'DNG', 'CR2', 'CR3', 'NEF'].includes(f.ext)) {
                    const img = document.createElement('img');
                    img.src = `/api/thumbnail?path=${encodeURIComponent(path)}&file=${encodeURIComponent(f.rel_path)}`;
                    img.alt = f.name;
                    img.onerror = () => {
                        card.innerHTML = `<span class="thumb-icon-placeholder">${f.ext}</span><span class="thumb-card-size">${f.size_mb}MB</span>`;
                    };
                    card.appendChild(img);
                } else {
                    card.innerHTML = `<span class="thumb-icon-placeholder">${f.ext || 'VID'}</span><span class="thumb-card-size">${f.size_mb}MB</span>`;
                }

                const badge = document.createElement('span');
                badge.className = 'thumb-format-badge';
                badge.innerText = f.ext;
                card.appendChild(badge);

                thumbnailStrip.appendChild(card);
            });
        } catch (e) {
            thumbnailStrip.innerHTML = `<div class="empty-strip">Unable to load media preview.</div>`;
        }
    }

    async function validatePath(input, badge) {
        const val = input.value.trim();
        if (!val) {
            badge.innerText = 'Not Set';
            badge.className = 'path-badge';
            return;
        }
        try {
            const res = await fetch(`/api/validate-path?path=${encodeURIComponent(val)}`);
            const data = await res.json();
            if (data.exists) {
                badge.innerText = `Valid (${data.file_count} files)`;
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

    async function checkUndoStatus() {
        try {
            const res = await fetch('/api/undo-status');
            const data = await res.json();
            if (data.can_undo) {
                undoBtn.disabled = false;
                undoBtn.innerText = `Undo Last Sort (${data.count})`;
            } else {
                undoBtn.disabled = true;
                undoBtn.innerText = 'Undo Last Sort';
            }
        } catch (e) {
            undoBtn.disabled = true;
        }
    }

    async function autoSaveProfileConfig() {
        autoSaveInd.innerText = "Syncing...";
        autoSaveInd.style.color = "var(--accent-amber)";

        if (loadedConfig && loadedConfig.profiles && loadedConfig.profiles[activeProfile]) {
            loadedConfig.profiles[activeProfile].name = profileNameInput.value.trim() || activeProfile;
            loadedConfig.profiles[activeProfile].source_path = sourceInput.value;
            loadedConfig.profiles[activeProfile].target_path = targetInput.value;
        }

        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile_key: activeProfile,
                profile_name: profileNameInput.value.trim(),
                source_path: sourceInput.value,
                target_path: targetInput.value
            })
        });

        renderProfileTabs();
        autoSaveInd.innerText = "Synced";
        autoSaveInd.style.color = "var(--accent-green)";
    }

    function renderProfileTabs() {
        if (!loadedConfig || !loadedConfig.profiles) return;
        profileTabsContainer.innerHTML = '';
        Object.keys(loadedConfig.profiles).forEach(key => {
            const p = loadedConfig.profiles[key];
            const btn = document.createElement('button');
            btn.className = `profile-tab ${key === activeProfile ? 'active' : ''}`;
            btn.innerText = p.name || key;
            btn.addEventListener('click', () => {
                switchProfile(key);
                autoSaveProfileConfig();
            });
            profileTabsContainer.appendChild(btn);
        });
    }

    function switchProfile(profileKey) {
        activeProfile = profileKey;
        renderProfileTabs();

        if (loadedConfig && loadedConfig.profiles && loadedConfig.profiles[profileKey]) {
            const p = loadedConfig.profiles[profileKey];
            profileNameInput.value = p.name || profileKey;
            sourceInput.value = p.source_path || '';
            targetInput.value = p.target_path || '';
        } else {
            profileNameInput.value = profileKey;
            sourceInput.value = '';
            targetInput.value = '';
        }

        validatePath(sourceInput, sourceBadge);
        validatePath(targetInput, targetBadge);
        loadThumbnails(sourceInput.value);
    }

    // Initial Load
    try {
        const res = await fetch('/api/config');
        loadedConfig = await res.json();
        activeProfile = loadedConfig.active_profile || 'mobile';
        switchProfile(activeProfile);
        checkUndoStatus();
    } catch (e) {
        console.error("Config fetch error", e);
    }

    profileNameInput.addEventListener('change', autoSaveProfileConfig);

    browseSrcBtn.addEventListener('click', async () => {
        const res = await fetch(`/api/browse?initial_dir=${encodeURIComponent(sourceInput.value)}`);
        const data = await res.json();
        if (data.path) {
            sourceInput.value = data.path;
            validatePath(sourceInput, sourceBadge);
            loadThumbnails(data.path);
            autoSaveProfileConfig();
        }
    });

    browseTgtBtn.addEventListener('click', async () => {
        const res = await fetch(`/api/browse?initial_dir=${encodeURIComponent(targetInput.value)}`);
        const data = await res.json();
        if (data.path) {
            targetInput.value = data.path;
            validatePath(targetInput, targetBadge);
            autoSaveProfileConfig();
        }
    });

    sourceInput.addEventListener('change', () => { validatePath(sourceInput, sourceBadge); loadThumbnails(sourceInput.value); autoSaveProfileConfig(); });
    targetInput.addEventListener('change', () => { validatePath(targetInput, targetBadge); autoSaveProfileConfig(); });

    openTargetBtn.addEventListener('click', async () => {
        if (!targetInput.value.trim()) return;
        await fetch('/api/open-folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: targetInput.value })
        });
    });

    undoBtn.addEventListener('click', async () => {
        const confirmUndo = confirm("Are you sure you want to roll back the previous batch and restore files to their source folder?");
        if (!confirmUndo) return;

        undoBtn.disabled = true;
        undoBtn.innerText = "Restoring...";
        try {
            const res = await fetch('/api/undo', { method: 'POST' });
            const data = await res.json();
            if (data.status === 'ok') {
                appendFeed("SYSTEM", `Rollback complete: ${data.restored} files restored to source folder.`);
                validatePath(sourceInput, sourceBadge);
                validatePath(targetInput, targetBadge);
                loadThumbnails(sourceInput.value);
            } else {
                appendFeed("SKIP", `Undo failed: ${data.message}`);
            }
        } catch (e) {
            appendFeed("SKIP", "Undo request failed.");
        }
        checkUndoStatus();
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

    abortBtn.addEventListener('click', async () => {
        await fetch('/api/abort', { method: 'POST' });
        abortBtn.disabled = true;
        abortBtn.innerText = "Aborting...";
    });

    runBtn.addEventListener('click', () => {
        if (!dryRunToggle.checked) {
            const profileDisplayName = profileNameInput.value.trim() || activeProfile;
            const confirmRun = confirm(`You are about to execute live sorting for [${profileDisplayName}]. Proceed?`);
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
        speedTimer.innerText = 'Starting...';

        startTime = performance.now();
        accumulatedBytes = 0;

        const dryRun = dryRunToggle.checked;
        const copyMode = copyToggle.checked;
        const url = `/api/stream?dry_run=${dryRun}&copy_mode=${copyMode}&profile=${activeProfile}`;
        currentEventSource = new EventSource(url);

        currentEventSource.onmessage = (e) => {
            const data = JSON.parse(e.data);

            if (data.type === "start") {
                appendFeed("SYSTEM", `Scanning complete. Found ${data.total} media captures in ${profileNameInput.value} source.`);
            } else if (data.type === "progress") {
                const pct = Math.round((data.index / data.total) * 100);
                progressBar.style.width = `${pct}%`;
                progressPercent.innerText = `${pct}%`;
                appendFeed(data.status, `${data.file} -> ${data.target}`);

                mSizeProcessed.innerText = formatBytes(data.bytes_processed);
                mSizeSaved.innerText = `${formatBytes(data.bytes_saved)} Saved`;

                accumulatedBytes += (data.bytes_current || 0);
                const elapsedSec = (performance.now() - startTime) / 1000;
                if (elapsedSec > 0.5) {
                    const mbps = (accumulatedBytes / (1024 * 1024)) / elapsedSec;
                    const remainingFiles = data.total - data.index;
                    const etaSec = Math.round((elapsedSec / data.index) * remainingFiles);
                    speedTimer.innerText = `Rate: ${mbps.toFixed(1)} MB/s • ETA: ${etaSec}s`;
                }
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
                mSizeProcessed.innerText = formatBytes(data.summary.bytes_processed);
                mSizeSaved.innerText = `${formatBytes(data.summary.bytes_saved)} Saved`;

                const totalSec = Math.round((performance.now() - startTime) / 1000);
                speedTimer.innerText = `Done in ${totalSec}s • ${formatBytes(data.summary.bytes_processed)} sorted`;

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
            checkUndoStatus();
        }
    });
});