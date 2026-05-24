/* ─── API Client ─────────────────────────────────────────────────────── */

const API = {
    base: '',

    async request(method, path, body = null) {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body) opts.body = JSON.stringify(body);

        const resp = await fetch(`${this.base}${path}`, opts);
        const data = await resp.json();
        return data;
    },

    // ── Novels ──
    listNovels() {
        return this.request('GET', '/api/novels');
    },

    getNovel(name) {
        return this.request('GET', `/api/novels/${encodeURIComponent(name)}`);
    },

    createNovel(data) {
        return this.request('POST', '/api/novels/create', data);
    },

    readFile(novelName, path) {
        return this.request('GET', `/api/novels/${encodeURIComponent(novelName)}/file?path=${encodeURIComponent(path)}`);
    },

    readChapter(novelName, chRef) {
        return this.request('GET', `/api/novels/${encodeURIComponent(novelName)}/chapters/${encodeURIComponent(chRef)}`);
    },

    readReview(novelName, chRef) {
        return this.request('GET', `/api/novels/${encodeURIComponent(novelName)}/reviews/${encodeURIComponent(chRef)}`);
    },

    getStatus(novelName) {
        return this.request('GET', `/api/novels/${encodeURIComponent(novelName)}/status`);
    },

    readOutline(novelName, volRef) {
        return this.request('GET', `/api/novels/${encodeURIComponent(novelName)}/outline/${encodeURIComponent(volRef)}`);
    },

    // ── Writing ──
    generateChapter(novelName, data) {
        return this.request('POST', `/api/novels/${encodeURIComponent(novelName)}/generate-chapter`, data);
    },

    reviewChapter(novelName, data) {
        return this.request('POST', `/api/novels/${encodeURIComponent(novelName)}/review-chapter`, data);
    },

    // ── AI ──
    aiChat(data) {
        return this.request('POST', '/api/ai/chat', data);
    },

    // ── Scripts ──
    runScript(novelName, data) {
        return this.request('POST', `/api/novels/${encodeURIComponent(novelName)}/run-script`, data);
    },

    // ── Status ──
    updateStatus(novelName, content) {
        return this.request('POST', `/api/novels/${encodeURIComponent(novelName)}/update-status`, { content });
    },

    // ── Config ──
    getConfig() {
        return this.request('GET', '/api/config');
    },

    saveConfig(data) {
        return this.request('POST', '/api/config/save', data);
    },

    testConfig() {
        return this.request('POST', '/api/config/test');
    },

    // ── Templates ──
    getTemplates() {
        return this.request('GET', '/api/templates');
    },
};
