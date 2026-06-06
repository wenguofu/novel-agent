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
    exportNovelUrl(novel, format) { return `/api/novels/${encodeURIComponent(novel)}/export?format=${encodeURIComponent(format)}`; },

    // ── Writing ──
    generateChapter(novel, data) { return this.request('POST', `/api/novels/${encodeURIComponent(novel)}/generate-chapter`, data); },
    reviewChapter(novel, data) { return this.request('POST', `/api/novels/${encodeURIComponent(novel)}/review-chapter`, data); },

    // ── AI ──
    aiChat(data) { return this.request('POST', '/api/ai/chat', data); },
    aiStream(data) { return this.request('POST', '/api/ai/stream', data); },

    // ── Context ──
    contextBuild(data) { return this.request('POST', '/api/context/build', data); },
    contextStats(novel, vol, ch) { return this.request('GET', `/api/context/stats/${encodeURIComponent(novel)}/${vol}/${ch}`); },
    initFull(novel) { return this.request('POST', `/api/init/full/${encodeURIComponent(novel)}`); },
    ragQuery(data) { return this.request('POST', '/api/rag/query', data); },

    // ── Scripts ──
    runScript(novel, data) { return this.request('POST', `/api/novels/${encodeURIComponent(novel)}/run-script`, data); },

    // ── Workflow Enforcement ──
    preflightCheck(novel, data) { return this.request('POST', `/api/workflow/preflight/${encodeURIComponent(novel)}`, data); },
    postflightCheck(novel, data) { return this.request('POST', `/api/workflow/postflight/${encodeURIComponent(novel)}`, data); },
    runAllChecks(novel, data) { return this.request('POST', `/api/novels/${encodeURIComponent(novel)}/run-all-checks`, data); },

    // ── Optimize ──
    optimizeChapter(novel, data) { return this.request('POST', `/api/novels/${encodeURIComponent(novel)}/optimize-chapter`, data); },

    // ── Status ──
    updateStatus(novel, content) { return this.request('POST', `/api/novels/${encodeURIComponent(novel)}/update-status`, { content }); },

    // ── Config ──
    getConfig() { return this.request('GET', '/api/config'); },
    saveConfig(data) { return this.request('POST', '/api/config/save', data); },
    testConfig() { return this.request('POST', '/api/config/test'); },

    // ── Usage Stats ──
    usageStats(params = {}) { return this.request('GET', `/api/usage/stats?${new URLSearchParams(params)}`); },

    // ── V3 Management: World Building ──
    worldBuilding: {
        list(novel, params = {}) { return API.request('GET', `/api/world_building/${encodeURIComponent(novel)}?${new URLSearchParams(params)}`); },
        create(novel, data) { return API.request('POST', `/api/world_building/${encodeURIComponent(novel)}`, data); },
        update(novel, id, data) { return API.request('PUT', `/api/world_building/${encodeURIComponent(novel)}/${id}`, data); },
        delete(novel, id) { return API.request('DELETE', `/api/world_building/${encodeURIComponent(novel)}/${id}`); },
    },

    // ── V3 Management: Plot Arcs ──
    plotArcs: {
        list(novel, params = {}) { return API.request('GET', `/api/plot_arcs/${encodeURIComponent(novel)}?${new URLSearchParams(params)}`); },
        create(novel, data) { return API.request('POST', `/api/plot_arcs/${encodeURIComponent(novel)}`, data); },
        update(novel, id, data) { return API.request('PUT', `/api/plot_arcs/${encodeURIComponent(novel)}/${id}`, data); },
        delete(novel, id) { return API.request('DELETE', `/api/plot_arcs/${encodeURIComponent(novel)}/${id}`); },
    },

    // ── V3 Management: Pacing Control ──
    pacingControl: {
        list(novel, params = {}) { return API.request('GET', `/api/pacing_control/${encodeURIComponent(novel)}?${new URLSearchParams(params)}`); },
        create(novel, data) { return API.request('POST', `/api/pacing_control/${encodeURIComponent(novel)}`, data); },
        update(novel, id, data) { return API.request('PUT', `/api/pacing_control/${encodeURIComponent(novel)}/${id}`, data); },
        delete(novel, id) { return API.request('DELETE', `/api/pacing_control/${encodeURIComponent(novel)}/${id}`); },
    },

    // ── V3 Management: Revelation Schedule ──
    revelationSchedule: {
        list(novel, params = {}) { return API.request('GET', `/api/revelation_schedule/${encodeURIComponent(novel)}?${new URLSearchParams(params)}`); },
        create(novel, data) { return API.request('POST', `/api/revelation_schedule/${encodeURIComponent(novel)}`, data); },
        update(novel, id, data) { return API.request('PUT', `/api/revelation_schedule/${encodeURIComponent(novel)}/${id}`, data); },
        delete(novel, id) { return API.request('DELETE', `/api/revelation_schedule/${encodeURIComponent(novel)}/${id}`); },
    },

    // ── Wizard ──
    wizardStep(data) { return this.request('POST', '/api/wizard/step', data); },
    getTemplates() { return this.request('GET', '/api/templates'); },
};
