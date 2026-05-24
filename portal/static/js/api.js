/* ─── API Client ─────────────────────────────────────────────────────── */

const API = {
    base: '',

    async request(method, path, body = null) {
        const opts = { method, headers: { 'Content-Type': 'application/json' } };
        if (body) opts.body = JSON.stringify(body);
        const resp = await fetch(`${this.base}${path}`, opts);
        const data = await resp.json();
        return data;
    },

    // ── Novels ──
    listNovels() { return this.request('GET', '/api/novels'); },
    getNovel(name) { return this.request('GET', `/api/novels/${encodeURIComponent(name)}`); },
    createNovel(data) { return this.request('POST', '/api/novels/create', data); },
    readFile(novel, path) { return this.request('GET', `/api/novels/${encodeURIComponent(novel)}/file?path=${encodeURIComponent(path)}`); },
    writeFile(novel, path, content) { return this.request('POST', `/api/novels/${encodeURIComponent(novel)}/file/write`, { path, content }); },
    readChapter(novel, ref) { return this.request('GET', `/api/novels/${encodeURIComponent(novel)}/chapters/${encodeURIComponent(ref)}`); },
    editChapter(novel, ref, content) { return this.request('POST', `/api/novels/${encodeURIComponent(novel)}/chapters/${encodeURIComponent(ref)}/edit`, { content }); },
    readReview(novel, ref) { return this.request('GET', `/api/novels/${encodeURIComponent(novel)}/reviews/${encodeURIComponent(ref)}`); },
    getStatus(novel) { return this.request('GET', `/api/novels/${encodeURIComponent(novel)}/status`); },
    readOutline(novel, vol) { return this.request('GET', `/api/novels/${encodeURIComponent(novel)}/outline/${encodeURIComponent(vol)}`); },
    editOutline(novel, vol, content) { return this.request('POST', `/api/novels/${encodeURIComponent(novel)}/outline/${encodeURIComponent(vol)}/edit`, { content }); },

    // ── Writing ──
    generateChapter(novel, data) { return this.request('POST', `/api/novels/${encodeURIComponent(novel)}/generate-chapter`, data); },
    reviewChapter(novel, data) { return this.request('POST', `/api/novels/${encodeURIComponent(novel)}/review-chapter`, data); },

    // ── AI ──
    aiChat(data) { return this.request('POST', '/api/ai/chat', data); },
    aiStream(data) { return this.request('POST', '/api/ai/stream', data); },

    // ── Scripts ──
    runScript(novel, data) { return this.request('POST', `/api/novels/${encodeURIComponent(novel)}/run-script`, data); },

    // ── Optimize ──
    optimizeChapter(novel, data) { return this.request('POST', `/api/novels/${encodeURIComponent(novel)}/optimize-chapter`, data); },

    // ── Status ──
    updateStatus(novel, content) { return this.request('POST', `/api/novels/${encodeURIComponent(novel)}/update-status`, { content }); },

    // ── Config ──
    getConfig() { return this.request('GET', '/api/config'); },
    saveConfig(data) { return this.request('POST', '/api/config/save', data); },
    testConfig() { return this.request('POST', '/api/config/test'); },

    // ── Wizard ──
    wizardStep(data) { return this.request('POST', '/api/wizard/step', data); },
    getTemplates() { return this.request('GET', '/api/templates'); },
};
