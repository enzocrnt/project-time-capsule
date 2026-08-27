document.addEventListener('DOMContentLoaded', async () => {
    const sourceInput = document.getElementById('sourcePath');
    const targetInput = document.getElementById('targetPath');
    const saveBtn = document.getElementById('saveConfigBtn');
    const runBtn = document.getElementById('runPipelineBtn');
    const dryRunToggle = document.getElementById('dryRunToggle');
    const copyToggle = document.getElementById('copyModeToggle');
    const appStatus = document.getElementById('appStatus');
    const consoleBox = document.getElementById('consoleOutput');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');

    const metricProcessed = document.getElementById('metricProcessed');
    const metricDuplicates = document.getElementById('metricDuplicates');
    const metricConflicts = document.getElementById('metricConflicts');
    const metricSkipped = document.getElementById('metricSkipped');

    // 1. Fetch saved config on startup
    try {
        const res = await fetch('/api/config');
        const config = await res.json();
        sourceInput.value = config.source_path || '';
        targetInput.value = config.target_path || '';
    } catch (e) {
        console.error("Failed to load config", e);
    }

    // 2. Save Config Button
    saveBtn.addEventListener('click', async () => {
        saveBtn.innerText = "Saving...";
        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source_path: sourceInput.value,
                target_path: targetInput.value
            })
        });
        saveBtn.innerText = "Settings Saved!";
        setTimeout(() => saveBtn.innerText = "Save Directory Settings", 2000);
    });

    function appendLog(status, text) {
        const div = document.createElement('div');
        div.className = `log-entry ${status}`;
        div.innerText = `[${status}] ${text}`;
        consoleBox.appendChild(div);
        consoleBox.scrollTop = consoleBox.scrollHeight;
    }

    // 3. Start Live Stream Sorting
    runBtn.addEventListener('click', () => {
        runBtn.disabled = true;
        appStatus.innerText = "Sorting";
        appStatus.className = "status-badge running";
        consoleBox.innerHTML = '';
        progressBar.style.width = '0%';
        progressPercent.innerText = '0%';

        const dryRun = dryRunToggle.checked;
        const copyMode = copyToggle.checked;
        const url = `/api/stream?dry_run=${dryRun}&copy_mode=${copyMode}`;

        const eventSource = new EventSource(url);

        eventSource.onmessage = (e) => {
            const data = JSON.parse(e.data);

            if (data.type === "start") {
                appendLog("INFO", `Found ${data.total} media files to inspect.`);
            } else if (data.type === "progress") {
                const pct = Math.round((data.index / data.total) * 100);
                progressBar.style.width = `${pct}%`;
                progressPercent.innerText = `${pct}%`;
                appendLog(data.status, `${data.file} -> ${data.target}`);
            } else if (data.type === "done") {
                progressBar.style.width = '100%';
                progressPercent.innerText = '100%';

                metricProcessed.innerText = data.summary.processed;
                metricDuplicates.innerText = data.summary.duplicates;
                metricConflicts.innerText = data.summary.conflicts;
                metricSkipped.innerText = data.summary.skipped;

                appendLog("INFO", "Media sorting run complete.");
                appStatus.innerText = "Completed";
                appStatus.className = "status-badge done";
                runBtn.disabled = false;
                eventSource.close();
            } else if (data.type === "error") {
                appendLog("ERROR", data.message);
                appStatus.innerText = "Error";
                runBtn.disabled = false;
                eventSource.close();
            }
        };

        eventSource.onerror = () => {
            appendLog("ERROR", "Event stream connection lost.");
            runBtn.disabled = false;
            eventSource.close();
        };
    });
});