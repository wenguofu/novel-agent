/* ─── Novel Agent Web Portal - Main App v2.0 ────────────────────────── */

const App = {
    currentView: 'dashboard',
    currentNovel: null,
    novels: [],
    config: {},
    streamAbort: null,
    _recentActivity: [],

    // ── Init ──
    async init() {
        const cfgResp = await API.getConfig();
        if (cfgResp.success) { this.config = cfgResp; this._updateSidebarStatus(cfgResp); }
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => { e.preventDefault(); this.navigate(item.dataset.view); });
        });
        await this.navigate('dashboard');
    },

    async navigate(view, params = {}) {
        this.currentView = view;
        document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.view === view));
        const mc = document.getElementById('mainContent');
        mc.innerHTML = '<div class="loading"><div class="spinner"></div><span>加载中...</span></div>';
        try {
            switch (view) {
                case 'dashboard': await this._renderDashboard(mc); break;
                case 'novels': await this._renderNovels(mc); break;
                case 'new-book': await this._renderNewBook(mc); break;
                case 'writing': await this._renderWriting(mc, params); break;
                case 'review': await this._renderReview(mc, params); break;
                case 'chapters': await this._renderChapters(mc, params); break;
                case 'outlines': await this._renderOutlines(mc); break;
                case 'settings': await this._renderSettings(mc); break;
                default: mc.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🤷</div><div class="empty-state-title">页面不存在</div></div>';
            }
        } catch (e) {
            console.error(e);
            mc.innerHTML = `<div class="empty-state"><div class="empty-state-icon">💥</div><div class="empty-state-title">加载失败</div><div class="empty-state-desc">${e.message}</div></div>`;
        }
    },

    // ── Toast ──
    toast(message, type = 'info') {
        let container = document.querySelector('.toast-container');
        if (!container) { container = document.createElement('div'); container.className = 'toast-container'; document.body.appendChild(container); }
        const el = document.createElement('div'); el.className = `toast toast-${type}`; el.textContent = message;
        container.appendChild(el);
        setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateX(100%)'; setTimeout(() => el.remove(), 300); }, 3500);
    },

    // ── Modal ──
    modal(title, contentHtml, footerHtml = '', width = '') {
        const overlay = document.createElement('div'); overlay.className = 'modal-overlay';
        overlay.innerHTML = `<div class="modal" style="${width ? 'max-width:' + width + ';' : ''}"><div class="modal-title">${title}</div><div class="modal-body">${contentHtml}</div><div class="modal-footer">${footerHtml}</div></div>`;
        overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
        document.body.appendChild(overlay);
        return overlay.querySelector('.modal');
    },

    // ── Confirm ──
    async confirm(title, message) {
        return new Promise((resolve) => {
            const m = this.modal(title, `<p>${message}</p>`,
                `<button class="btn btn-primary" onclick="this.closest('.modal-overlay').__res=1;this.closest('.modal-overlay').remove()">确认</button>
                 <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').__res=0;this.closest('.modal-overlay').remove()">取消</button>`);
            m.closest('.modal-overlay').__res = 0;
            const obs = new MutationObserver(() => { const r = m.closest('.modal-overlay'); if (!r) { resolve(false); obs.disconnect(); } });
            obs.observe(document.body, { childList: true });
            m.closest('.modal-overlay').addEventListener('remove', () => { resolve(m.closest('.modal-overlay').__res === 1); obs.disconnect(); });
            // simpler approach
            m.querySelector('.btn-primary').addEventListener('click', () => { resolve(true); });
            m.querySelector('.btn-secondary').addEventListener('click', () => { resolve(false); });
        });
    },

    // ── Markdown ──
    renderMarkdown(text) {
        if (!text) return '<em class="text-muted">(空)</em>';
        let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
        html = html.replace(/^---$/gm, '<hr>');
        html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');
        html = html.replace(/\n\n/g, '</p><p>');
        html = html.replace(/^(?!<[hul])/gm, '<p>');
        html = html.replace(/(?<![hul]>)$/gm, '</p>');
        return html;
    },

    _wordBadge(wc) {
        const cls = wc >= 2500 ? 'good' : wc >= 1500 ? 'warn' : 'low';
        return `<span class="word-badge ${cls}">📝 ${wc}字</span>`;
    },

    _updateSidebarStatus(cfg) {
        const dot = document.getElementById('configStatus');
        if (!dot) return;
        dot.innerHTML = cfg.deepseek_configured
            ? '<span class="status-dot green"></span> DeepSeek 已连接'
            : '<span class="status-dot orange"></span> 需配置 API Key';
    },

    // ═══════════════════════════════════════════════════════════════════
    //  DASHBOARD
    // ═══════════════════════════════════════════════════════════════════

    async _renderDashboard(mc) {
        const novelsResp = await API.listNovels();
        const novels = novelsResp.success ? novelsResp.novels : [];
        const totalCh = novels.reduce((s, n) => s + (n.total_chapters || 0), 0);
        const totalW = novels.reduce((s, n) => s + (n.total_words || 0), 0);
        const totalR = novels.reduce((s, n) => s + (n.review_count || 0), 0);

        let novelCards = '';
        novels.forEach(n => {
            const last = n.last_chapter ? `<div style="font-size:11px;color:var(--text-tertiary)">最近: ${n.last_chapter} ${n.last_chapter_words ? '· ' + n.last_chapter_words + '字' : ''}</div>` : '';
            const wPct = n.word_goal ? Math.min(100, Math.round((n.total_words || 0) / (parseInt(n.word_goal) * 10000) * 100)) : 0;
            novelCards += `
                <div class="novel-card" onclick="App._openNovelQuick('${n.name}')">
                    <div class="novel-card-title">${n.title || n.name}</div>
                    <div class="novel-card-meta">
                        <span>📖 ${n.total_chapters}章</span>
                        <span>📝 ${(n.total_words / 10000).toFixed(1)}万字</span>
                        <span>🔍 ${n.review_count}审稿</span>
                    </div>
                    ${n.summary ? '<div class="novel-card-summary">' + n.summary + '</div>' : ''}
                    ${last}
                    ${wPct > 0 ? `<div class="mt-8"><div class="progress-label"><span>进度</span><span>${wPct}%</span></div><div class="progress-bar"><div class="progress-bar-fill accent" style="width:${wPct}%"></div></div></div>` : ''}
                </div>`;
        });

        mc.innerHTML = `
            <div class="page-header">
                <div><h1 class="page-title">📊 写作控制台</h1><p class="page-subtitle">AI 驱动的长篇网文写作工作台</p></div>
                <button class="btn btn-primary" onclick="App.navigate('new-book')">✨ 创建新书</button>
            </div>
            <div class="stats-grid">
                <div class="stat-card"><div class="stat-value">${novels.length}</div><div class="stat-label">项目</div></div>
                <div class="stat-card"><div class="stat-value">${totalCh}</div><div class="stat-label">总章节</div></div>
                <div class="stat-card"><div class="stat-value">${(totalW / 10000).toFixed(1)}万</div><div class="stat-label">总字数</div></div>
                <div class="stat-card"><div class="stat-value">${this.config.deepseek_configured ? '✅' : '❌'}</div><div class="stat-label">AI状态</div></div>
            </div>
            ${novels.length > 0 ? `<div class="quick-actions mb-4">
                <div class="quick-action" onclick="App.navigate('writing')"><div class="qa-icon">✍️</div><div class="qa-label">写作台</div><div class="qa-desc">生成新章节</div></div>
                <div class="quick-action" onclick="App.navigate('chapters')"><div class="qa-icon">📖</div><div class="qa-label">章节浏览</div><div class="qa-desc">阅读和编辑</div></div>
                <div class="quick-action" onclick="App.navigate('outlines')"><div class="qa-icon">📐</div><div class="qa-label">大纲管理</div><div class="qa-desc">规划和编辑</div></div>
                <div class="quick-action" onclick="App.navigate('settings')"><div class="qa-icon">⚙️</div><div class="qa-label">模型配置</div><div class="qa-desc">DeepSeek设置</div></div>
            </div>` : ''}
            <div class="card">
                <div class="card-header"><h2 class="card-title">📚 项目</h2><span class="text-sm text-secondary">${novels.length} 个项目</span></div>
                <div class="novel-grid">${novelCards || '<div class="empty-state"><div class="empty-state-icon">📖</div><div class="empty-state-title">还没有小说项目</div><div class="empty-state-desc">点击"创建新书"开始你的第一部作品</div></div>'}</div>
            </div>
        `;
    },

    async _openNovelQuick(name) {
        const resp = await API.getNovel(name);
        if (!resp.success) { this.toast(resp.error, 'error'); return; }
        const n = resp.novel;
        const vols = n.volumes ? n.volumes.map(v => `<div class="volume-header">📁 ${v.name} · ${v.chapter_count}章 · ${(v.total_words / 10000).toFixed(1)}万字</div>` + v.chapters.map(ch => {
            const wb = ch.words >= 2500 ? 'good' : ch.words >= 1500 ? 'warn' : 'low';
            return `<div class="chapter-item"><span class="ch-num">${ch.name}</span><span class="ch-meta"><span class="word-badge ${wb}">${ch.words}字</span></span><div class="ch-actions"><button class="btn btn-sm btn-primary" onclick="App._readChapter('${name}','${v.name}/${ch.name}')">📖</button><button class="btn btn-sm btn-secondary" onclick="App.navigate('writing',{novel:'${name}',chapter:'${v.name}/${ch.name}'})">✍️</button></div></div>`;
        }).join('')).join('') : '<div class="empty-state"><div class="empty-state-icon">📄</div><div class="empty-state-title">暂无章节</div></div>';
        const wPct = n.word_goal ? Math.min(100, Math.round((n.total_words || 0) / (parseInt(n.word_goal) * 10000) * 100)) : 0;

        const body = `
            <div class="tab-bar"><span class="tab-item active" data-t="overview" onclick="App._switchQTab(this,'overview')">概览</span><span class="tab-item" data-t="chapters" onclick="App._switchQTab(this,'chapters')">章节 (${n.total_chapters})</span><span class="tab-item" data-t="files" onclick="App._switchQTab(this,'files')">文件</span></div>
            <div id="qkTabContent">
                <div class="stats-grid" style="grid-template-columns:repeat(4,1fr)">
                    <div class="stat-card"><div class="stat-value">${n.total_chapters}</div><div class="stat-label">章节</div></div>
                    <div class="stat-card"><div class="stat-value">${(n.total_words/10000).toFixed(1)}万</div><div class="stat-label">字数</div></div>
                    <div class="stat-card"><div class="stat-value">${n.volumes ? n.volumes.length : 0}</div><div class="stat-label">卷数</div></div>
                    <div class="stat-card"><div class="stat-value">${n.review_count}</div><div class="stat-label">审稿</div></div>
                </div>
                ${wPct > 0 ? `<div class="mt-12"><div class="progress-label"><span>写作进度</span><span>${wPct}%</span></div><div class="progress-bar"><div class="progress-bar-fill accent" style="width:${wPct}%"></div></div></div>` : ''}
                <div class="markdown-content mt-16">${this.renderMarkdown((n.project_content || '').substring(0, 1000))}</div>
            </div>
        `;
        const footer = `<button class="btn btn-primary" onclick="App.navigate('writing',{novel:'${n.name}'})">✍️ 开始写作</button><button class="btn btn-success" onclick="App.navigate('chapters',{novel:'${n.name}'})">📖 浏览章节</button><button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">关闭</button>`;

        const modalEl = this.modal(`📚 ${n.title || n.name}`, body, footer, '800px');
        modalEl._novel = n;
        modalEl._origOverview = document.getElementById('qkTabContent').innerHTML;
        modalEl._chaptersHtml = '<div class="chapter-list">' + vols + '</div>';
    },

    _switchQTab(tab, t) {
        const modal = tab.closest('.modal');
        modal.querySelectorAll('.tab-item').forEach(x => x.classList.remove('active'));
        tab.classList.add('active');
        const content = modal.querySelector('#qkTabContent');
        if (t === 'overview') content.innerHTML = modal._origOverview;
        else if (t === 'chapters') content.innerHTML = modal._chaptersHtml;
        else if (t === 'files') {
            const n = modal._novel;
            const files = ['project.md', 'genre_bible.md', 'world_bible.md', 'characters.md', 'alias_registry.md', 'full_story_arc.md', 'state/current_status.md'];
            content.innerHTML = files.map(f => {
                const hasFile = n[f.replace('.md', '_content')] || n[`${f.replace('/', '_')}_content`];
                return `<div class="chapter-item" onclick="App._openFileModal('${n.name}','${f}')"><span class="ch-num">📄</span><span class="ch-title">${f}</span><span class="ch-meta">${hasFile ? '已存在' : '未创建'}</span></div>`;
            }).join('');
        }
    },

    async _openFileModal(novel, path) {
        const resp = await API.readFile(novel, path);
        if (!resp.success) { this.toast(resp.error, 'error'); return; }
        const body = `<textarea class="form-textarea" id="fileEdit" style="min-height:400px;font-family:var(--font-mono);font-size:12px;">${resp.content.replace(/</g, '&lt;')}</textarea>`;
        const footer = `<button class="btn btn-primary" onclick="App._saveFile('${novel}','${path}')">💾 保存</button><button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">关闭</button>`;
        this.modal(`📄 ${path}`, body, footer, '700px');
    },

    async _saveFile(novel, path) {
        const content = document.getElementById('fileEdit').value;
        const resp = await API.writeFile(novel, path, content);
        resp.success ? this.toast('✅ 已保存', 'success') : this.toast(resp.error, 'error');
        // close all modals
        document.querySelectorAll('.modal-overlay').forEach(m => m.remove());
    },

    async _readChapter(novel, ref) { await this._openChapterReader(novel, ref); },

    async _openChapterReader(novel, ref) {
        const resp = await API.readChapter(novel, ref);
        if (!resp.success) { this.toast(resp.error, 'error'); return; }
        const wc = resp.word_count || 0;
        const body = `<div class="reader-panel"><div class="reader-toolbar"><span><strong>${ref}</strong> ${this._wordBadge(wc)}</span><div class="flex gap-8"><button class="btn btn-sm btn-secondary" onclick="App._editChapterModal('${novel}','${ref}')">✏️ 编辑</button><button class="btn btn-sm btn-secondary" onclick="App.navigate('review',{novel:'${novel}',chapter:'${ref}'})">🔍 审稿</button></div></div><div class="reader-content">${this.renderMarkdown(resp.content)}</div></div>`;
        this.modal(`📖 ${ref}`, body, '<button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">关闭</button>', '800px');
    },

    async _editChapterModal(novel, ref) {
        const resp = await API.readChapter(novel, ref);
        if (!resp.success) { this.toast(resp.error, 'error'); return; }
        const wc = resp.word_count || 0;
        const body = `<div class="editor-container"><div class="editor-panel"><div class="editor-panel-header">📝 编辑 ${ref} <span>${this._wordBadge(wc)}</span></div><textarea class="editor-textarea" id="editorText">${resp.content.replace(/</g, '&lt;')}</textarea></div><div class="preview-panel"><div class="preview-panel-header">👁 预览 <span class="text-xs text-muted" id="editorWC">${wc}字</span></div><div class="preview-content" id="editorPreview">${this.renderMarkdown(resp.content)}</div></div></div>`;
        const footer = `<button class="btn btn-primary" onclick="App._saveChapterEdit('${novel}','${ref}')">💾 保存</button><button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">取消</button>`;
        this.modal(`✏️ 编辑章节`, body, footer, '90vw');

        const textarea = document.getElementById('editorText');
        const preview = document.getElementById('editorPreview');
        const wcEl = document.getElementById('editorWC');
        textarea.addEventListener('input', () => {
            const text = textarea.value;
            preview.innerHTML = this.renderMarkdown(text);
            const c = (text.match(/[\u4e00-\u9fff]/g) || []).length + (text.match(/[a-zA-Z]+/g) || []).length;
            wcEl.textContent = c + '字';
        });
    },

    async _saveChapterEdit(novel, ref) {
        const content = document.getElementById('editorText').value;
        const resp = await API.editChapter(novel, ref, content);
        resp.success ? this.toast(`✅ 已保存 (${resp.word_count}字)`, 'success') : this.toast(resp.error, 'error');
        document.querySelectorAll('.modal-overlay').forEach(m => m.remove());
    },

    // ═══════════════════════════════════════════════════════════════════
    //  NOVELS
    // ═══════════════════════════════════════════════════════════════════

    async _renderNovels(mc) {
        mc.innerHTML = `<div class="page-header"><div><h1 class="page-title">📚 小说管理</h1><p class="page-subtitle">查看和管理所有小说项目</p></div><button class="btn btn-primary" onclick="App.navigate('new-book')">✨ 创建新书</button></div><div id="novelsList"><div class="loading"><div class="spinner"></div></div></div>`;
        const resp = await API.listNovels();
        if (!resp.success) { document.getElementById('novelsList').innerHTML = '<div class="empty-state"><div class="empty-state-icon">💥</div><div class="empty-state-title">加载失败</div></div>'; return; }
        const novels = resp.novels;
        if (novels.length === 0) { document.getElementById('novelsList').innerHTML = '<div class="empty-state"><div class="empty-state-icon">📖</div><div class="empty-state-title">还没有小说项目</div></div>'; return; }
        document.getElementById('novelsList').innerHTML = novels.map(n => {
            const wPct = n.word_goal ? Math.min(100, Math.round((n.total_words || 0) / (parseInt(n.word_goal) * 10000) * 100)) : 0;
            return `<div class="novel-card" onclick="App._openNovelQuick('${n.name}')"><div class="novel-card-title">${n.title || n.name}</div><div class="novel-card-meta"><span>📖 ${n.total_chapters}章</span><span>📝 ${(n.total_words/10000).toFixed(1)}万字</span><span>🔍 ${n.review_count}审稿</span></div>${n.summary ? '<div class="novel-card-summary">'+n.summary+'</div>' : ''}${wPct>0?`<div class="mt-8"><div class="progress-bar"><div class="progress-bar-fill accent" style="width:${wPct}%"></div></div><div class="text-xs text-muted mt-2">${wPct}%</div></div>`:''}</div>`;
        }).join('');
    },

    // ═══════════════════════════════════════════════════════════════════
    //  NEW BOOK
    // ═══════════════════════════════════════════════════════════════════

    async _renderNewBook(mc) {
        const ok = this.config.deepseek_configured;
        mc.innerHTML = `
            <div class="page-header"><div><h1 class="page-title">✨ 创建新书</h1><p class="page-subtitle">AI 自动生成小说基础资料</p></div></div>
            ${!ok ? '<div class="card" style="border-color:var(--warning);"><div class="flex items-center gap-3"><span style="font-size:24px">⚠️</span><div><strong style="color:var(--warning)">API Key 未配置</strong><p class="text-secondary mt-2">请先在 <a href="#" onclick="App.navigate(\'settings\')" style="color:var(--accent)">⚙️ 设置</a> 填入 DeepSeek API Key</p></div></div></div>' : ''}
            <div class="card">
                <div class="form-group"><label class="form-label">书名 *</label><input class="form-input" id="nbName" placeholder="例：九天剑帝"></div>
                <div class="form-row"><div class="form-group"><label class="form-label">题材 *</label><input class="form-input" id="nbGenre" placeholder="玄幻 / 都市 / 修仙..."></div><div class="form-group"><label class="form-label">篇幅目标</label><select class="form-select" id="nbWordGoal"><option value="50万">50万字</option><option value="100万" selected>100万字</option><option value="200万">200万字</option><option value="300万">300万字</option></select></div></div>
                <div class="form-group"><label class="form-label">主角设定 *</label><textarea class="form-textarea" id="nbProtagonist" rows="3" placeholder="主角姓名、性格、背景、金手指等"></textarea></div>
                <div class="form-group"><label class="form-label">作品卖点</label><textarea class="form-textarea" id="nbSellingPoint" rows="2" placeholder="这本书最吸引读者的地方"></textarea></div>
                <div class="form-row"><div class="form-group"><label class="form-label">叙事视角</label><select class="form-select" id="nbPerspective"><option value="第三人称" selected>第三人称</option><option value="第一人称">第一人称</option><option value="多视角">多视角</option></select></div><div class="form-group"><label class="form-label">参考作品</label><input class="form-input" id="nbReferences" placeholder="可选，如：凡人修仙传"></div></div>
                <button class="btn btn-primary btn-lg" onclick="App._createNovel()" id="nbBtn">🚀 AI 自动创建</button>
                <div id="nbResult" class="mt-16"></div>
            </div>
        `;
    },

    async _createNovel() {
        const name = document.getElementById('nbName').value.trim();
        if (!name) { this.toast('请填写书名', 'warning'); return; }
        const data = {
            name, genre: document.getElementById('nbGenre').value.trim(),
            protagonist: document.getElementById('nbProtagonist').value.trim(),
            selling_point: document.getElementById('nbSellingPoint').value.trim(),
            word_goal: document.getElementById('nbWordGoal').value,
            perspective: document.getElementById('nbPerspective').value,
            references: document.getElementById('nbReferences').value.trim(),
        };
        if (!data.genre) { this.toast('请选择题材', 'warning'); return; }
        if (!data.protagonist) { this.toast('请填写主角设定', 'warning'); return; }
        const btn = document.getElementById('nbBtn'); btn.disabled = true; btn.textContent = '⏳ AI 生成中...';
        const resp = await API.createNovel(data);
        btn.disabled = false; btn.textContent = '🚀 AI 自动创建';
        const rd = document.getElementById('nbResult');
        if (resp.success) {
            this.toast(`🎉 小说「${resp.novel_name}」创建成功！`, 'success');
            rd.innerHTML = `<div class="card" style="border-color:var(--success)"><h3>✅ 创建成功</h3><p class="text-secondary mt-8">已创建文件：</p><div class="code-block success mt-8">${resp.created_files.join('\\n')}</div><div class="mt-16 flex gap-8"><button class="btn btn-primary" onclick="App.navigate('novels')">📚 查看项目</button><button class="btn btn-success" onclick="App.navigate('writing',{novel:'${resp.novel_name}'})">✍️ 开始写作</button></div></div>`;
        } else { this.toast(`创建失败: ${resp.error}`, 'error'); rd.innerHTML = `<div class="code-block error">${resp.error}</div>`; }
    },

    // ═══════════════════════════════════════════════════════════════════
    //  WRITING
    // ═══════════════════════════════════════════════════════════════════

    async _renderWriting(mc, params) {
        mc.innerHTML = `
            <div class="page-header"><div><h1 class="page-title">✍️ 写作台</h1><p class="page-subtitle">AI 辅助创作 + 实时流式输出</p></div></div>
            <div class="grid-2">
                <div class="card">
                    <h3 class="card-title">📋 创作设置</h3>
                    <div class="form-row mt-12"><div class="form-group"><label class="form-label">选择小说 *</label><select class="form-select" id="wNovel" onchange="App._loadWritingCtx()"><option value="">-- 请选择 --</option></select></div><div class="form-group"><label class="form-label">卷号</label><select class="form-select" id="wVolume">${[...Array(10)].map((_,i) => `<option value="vol-${String(i+1).padStart(2,'0')}">vol-${String(i+1).padStart(2,'0')}</option>`).join('')}</select></div></div>
                    <div class="form-row mt-12"><div class="form-group"><label class="form-label">章节编号</label><input class="form-input" id="wChapterNum" placeholder="如：1, 2... 留空自动推断"></div><div class="form-group"><label class="form-label">风格</label><input class="form-input" id="wStyle" placeholder="默认 / 金庸 / 古龙 / 余华..."></div></div>
                    <div class="form-group mt-12"><label class="form-label">写作指示（可选）</label><textarea class="form-textarea" id="wInstructions" rows="2" placeholder="对本章的特殊要求..."></textarea></div>
                    <div class="form-row mt-12">
                        <div class="form-group"><label class="form-label">温度 <span class="text-muted" style="font-size:11px" id="wTempVal">${this.config.deepseek_temperature || 0.8}</span></label><div class="param-slider-group"><input type="range" id="wTemperature" min="0" max="1.5" step="0.05" value="${this.config.deepseek_temperature || 0.8}" oninput="document.getElementById('wTempVal').textContent=this.value"><span class="param-value">${this.config.deepseek_temperature || 0.8}</span></div></div>
                        <div class="form-group"><label class="form-label">最大Token <span class="text-muted" style="font-size:11px" id="wMaxTokVal">${this.config.deepseek_max_tokens || 8192}</span></label><div class="param-slider-group"><input type="range" id="wMaxTokens" min="1024" max="16384" step="1024" value="${this.config.deepseek_max_tokens || 8192}" oninput="document.getElementById('wMaxTokVal').textContent=this.value"><span class="param-value">${this.config.deepseek_max_tokens || 8192}</span></div></div>
                    </div>
                    <div class="flex gap-8 mt-16">
                        <button class="btn btn-primary btn-lg" onclick="App._genChapter(false)">✍️ 生成单章</button>
                        <button class="btn btn-success btn-lg" onclick="App._genChapter(true)">⚡ 流式生成</button>
                        <button class="btn btn-secondary btn-lg" onclick="App._openBatchModal()">📦 批量续写</button>
                    </div>
                </div>
                <div class="card"><h3 class="card-title">📊 项目上下文</h3><div id="wContext"><p class="text-muted">请先选择小说</p></div></div>
            </div>
            <div id="wResult" class="mt-16"></div>
        `;
        const resp = await API.listNovels();
        if (resp.success) {
            const sel = document.getElementById('wNovel');
            resp.novels.forEach(n => { const o = document.createElement('option'); o.value = n.name; o.textContent = `${n.title||n.name} (${n.total_chapters}章)`; sel.appendChild(o); });
            if (params.novel) { sel.value = params.novel; this._loadWritingCtx(); }
            if (params.chapter) { document.getElementById('wChapterNum').value = params.chapter.split('/').pop().replace('ch-', ''); document.getElementById('wVolume').value = params.chapter.split('/')[0]; }
        }
    },

    async _loadWritingCtx() {
        const name = document.getElementById('wNovel').value;
        if (!name) return;
        const ctx = document.getElementById('wContext');
        const resp = await API.getNovel(name);
        if (resp.success && resp.novel) {
            const n = resp.novel;
            if (n.total_chapters > 0 && !document.getElementById('wChapterNum').value) document.getElementById('wChapterNum').value = n.total_chapters + 1;
            else if (n.total_chapters === 0) document.getElementById('wChapterNum').value = '1';
            const statusResp = await API.getStatus(name);
            const last = n.last_chapter ? `<div class="mt-8"><strong>最新章节:</strong> ${n.last_chapter} (${n.last_chapter_words||0}字)</div>` : '';
            ctx.innerHTML = `
                <div class="stats-grid" style="grid-template-columns:repeat(2,1fr)"><div class="stat-card"><div class="stat-value">${n.total_chapters}</div><div class="stat-label">章节</div></div><div class="stat-card"><div class="stat-value">${(n.total_words/10000).toFixed(1)}万</div><div class="stat-label">字数</div></div></div>
                ${last}
                <div class="code-block info mt-8" style="max-height:200px;overflow-y:auto">${statusResp.success ? this.renderMarkdown(statusResp.content.substring(0, 1500)) : '暂无状态信息'}</div>
            `;
        }
    },

    async _genChapter(stream = false) {
        const novel = document.getElementById('wNovel').value;
        if (!novel) { this.toast('请选择小说', 'warning'); return; }
        const data = {
            volume: document.getElementById('wVolume').value,
            chapter_num: document.getElementById('wChapterNum').value,
            style: document.getElementById('wStyle').value,
            instructions: document.getElementById('wInstructions').value,
            temperature: parseFloat(document.getElementById('wTemperature').value),
            max_tokens: parseInt(document.getElementById('wMaxTokens').value),
        };
        if (!data.chapter_num) { this.toast('请填写章节编号', 'warning'); return; }

        const rd = document.getElementById('wResult');
        rd.innerHTML = `<div class="loading"><div class="spinner"></div><span>AI 正在创作第 ${data.chapter_num} 章...</span></div>`;

        if (stream) {
            await this._streamChapter(novel, data, rd);
        } else {
            const resp = await API.generateChapter(novel, data);
            if (resp.success) {
                this.toast(`✅ 第 ${data.chapter_num} 章完成 (${resp.word_count}字)`, 'success');
                rd.innerHTML = `<div class="card" style="border-color:var(--success)"><div class="flex justify-between items-center"><h3>✅ 生成完成</h3><span class="badge badge-success">${resp.chapter_file}</span></div><div class="reader-panel mt-16" style="max-height:500px"><div class="reader-content">${this.renderMarkdown(resp.content)}</div></div><div class="flex gap-8 mt-16"><button class="btn btn-primary" onclick="App.navigate('review',{novel:'${novel}',chapter:'${resp.chapter_file}'})">🔍 审稿</button><button class="btn btn-secondary" onclick="document.getElementById('wChapterNum').value=parseInt(document.getElementById('wChapterNum').value)+1;document.getElementById('wInstructions').value='';App._genChapter(false)">➡️ 下一章</button></div></div>`;
            } else {
                this.toast(`生成失败: ${resp.error}`, 'error');
                rd.innerHTML = `<div class="code-block error">${resp.error}</div>`;
            }
        }
    },

    async _streamChapter(novel, data, rd) {
        rd.innerHTML = `<div class="card"><h3>⚡ 流式生成中...</h3><div class="stream-indicator mt-8"><div class="stream-dot"></div><span id="streamStatus">已连接 DeepSeek...</span></div><div class="stream-output mt-12" id="streamOut"><span class="streaming-cursor"></span></div></div>`;
        const out = document.getElementById('streamOut');
        let full = '';
        const abortCtrl = new AbortController();
        this.streamAbort = abortCtrl;

        try {
            const resp = await fetch('/api/ai/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages: [{"role": "user", "content": `请创作 ${data.volume} 第 ${data.chapter_num} 章`}],
                    system: this._buildSystemPrompt(novel, data),
                    temperature: data.temperature,
                    max_tokens: data.max_tokens,
                }),
                signal: abortCtrl.signal,
            });

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buf = '';
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buf += decoder.decode(value, { stream: true });
                const lines = buf.split('\n');
                buf = lines.pop() || '';
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const d = JSON.parse(line.slice(6));
                            if (d.type === 'token') { full += d.content; out.innerHTML = this.renderMarkdown(full) + '<span class="streaming-cursor"></span>'; out.scrollTop = out.scrollHeight; }
                            else if (d.type === 'done') {
                                const wc = (full.match(/[\u4e00-\u9fff]/g) || []).length + (full.match(/[a-zA-Z]+/g) || []).length;
                                rd.insertAdjacentHTML('beforeend', `<div id="streamSave" class="mt-8 flex gap-8"><button class="btn btn-primary" onclick="App._saveStreamedChapter('${novel}','${data.volume}','${data.chapter_num}')">💾 保存章节</button><button class="btn btn-secondary" onclick="this.closest('.card').remove()">关闭</button></div>`);
                                App._streamedContent = full;
                                rd.querySelector('#streamStatus').textContent = `✅ 完成 (${wc}字)`;
                                out.querySelector('.streaming-cursor')?.remove();
                            }
                            else if (d.type === 'error') { rd.querySelector('#streamStatus').textContent = '❌ ' + d.error; out.innerHTML = `<div class="code-block error">${d.error}</div>`; }
                        } catch (e) { /* skip */ }
                    }
                }
            }
        } catch (e) {
            if (e.name === 'AbortError') { rd.innerHTML = '<div class="card"><h3>⏹️ 已停止</h3><p class="text-muted mt-8">流式生成已中断</p></div>'; }
            else { rd.innerHTML = `<div class="code-block error">流式错误: ${e.message}</div>`; }
        }
        this.streamAbort = null;
    },

    _buildSystemPrompt(novel, data) {
        return `你是一个专业的长篇网文写作Agent。请输出完整的章节正文，以"# 章节标题"开头。\n\n写作约束：每章不少于2500字，不使用真实地名人名，有明确的章节功能和结尾牵引。\n卷：${data.volume}\n章节：第 ${data.chapter_num} 章\n${data.style ? '风格：' + data.style : ''}\n${data.instructions ? '指示：' + data.instructions : ''}`;
    },

    async _saveStreamedChapter(novel, volume, chNum) {
        const content = App._streamedContent;
        if (!content) { this.toast('无内容可保存', 'warning'); return; }
        const padded = chNum.padStart(4, '0');
        const resp = await API.editChapter(novel, `${volume}/ch-${padded}`, content);
        resp.success ? this.toast(`✅ 第 ${chNum} 章已保存`, 'success') : this.toast(resp.error, 'error');
    },

    _openBatchModal() {
        const novel = document.getElementById('wNovel').value;
        if (!novel) { this.toast('请先选择小说', 'warning'); return; }
        const start = document.getElementById('wChapterNum').value || 1;
        const vol = document.getElementById('wVolume').value;
        const body = `<div class="form-group"><label class="form-label">起始章节</label><input class="form-input" id="bStart" type="number" value="${start}"></div><div class="form-group"><label class="form-label">结束章节</label><input class="form-input" id="bEnd" type="number" value="${parseInt(start)+5}"></div><div class="form-group"><label class="form-label">卷号</label><input class="form-input" id="bVol" value="${vol}"></div><div id="bResult"></div>`;
        const footer = `<button class="btn btn-success" onclick="App._runBatch('${novel}')">🚀 开始批量写作</button><button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">取消</button>`;
        this.modal('📦 批量续写', body, footer);
    },

    async _runBatch(novel) {
        const start = parseInt(document.getElementById('bStart').value);
        const end = parseInt(document.getElementById('bEnd').value);
        const volume = document.getElementById('bVol').value;
        if (!start || !end || end < start) { this.toast('章节范围无效', 'warning'); return; }
        const total = end - start + 1;
        const rd = document.getElementById('bResult');
        rd.innerHTML = `<div class="loading"><div class="spinner"></div><span>批量写作 0/${total}...</span></div>`;
        let completed = 0, results = [];
        const btn = rd.closest('.modal-footer')?.querySelector('.btn-success'); if (btn) btn.disabled = true;

        for (let i = start; i <= end; i++) {
            rd.innerHTML = `<div class="loading"><div class="spinner"></div><span>正在写第 ${i} 章 (${completed+1}/${total})...</span></div>`;
            const resp = await API.generateChapter(novel, {
                volume, chapter_num: String(i),
                style: document.getElementById('wStyle')?.value || '',
                instructions: `批量写作第 ${i} 章`,
            });
            completed += resp.success ? 1 : 0;
            results.push(`${resp.success ? '✅' : '❌'} 第${i}章 ${resp.word_count||''}字`);
        }
        if (btn) btn.disabled = false;
        rd.innerHTML = `<div class="card" style="border-color:${completed===total?'var(--success)':'var(--warning)'}"><h3>${completed===total?'✅ 全部完成':'⚠️ 部分完成'}</h3><p>${completed}/${total} 章已生成</p><div class="code-block mt-8">${results.join('\\n')}</div></div>`;
        this.toast(`批量完成 ${completed}/${total}`, completed === total ? 'success' : 'warning');
    },

    // ═══════════════════════════════════════════════════════════════════
    //  REVIEW
    // ═══════════════════════════════════════════════════════════════════

    async _renderReview(mc, params) {
        mc.innerHTML = `<div class="page-header"><div><h1 class="page-title">🔍 审稿台</h1><p class="page-subtitle">AI + 脚本双重审稿</p></div></div><div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="rNovel" onchange="App._loadReviewChs()"><option value="">-- 请选择 --</option></select></div><div class="form-group"><label class="form-label">选择章节</label><select class="form-select" id="rChapter"><option value="">-- 请先选小说 --</option></select></div></div><button class="btn btn-primary btn-lg mt-12" onclick="App._runReview()">🔍 开始审稿</button><div id="rResult" class="mt-16"></div></div>`;
        const resp = await API.listNovels();
        if (resp.success) {
            const sel = document.getElementById('rNovel');
            resp.novels.forEach(n => { const o = document.createElement('option'); o.value = n.name; o.textContent = `${n.title||n.name} (${n.total_chapters}章)`; sel.appendChild(o); });
            if (params.novel) { sel.value = params.novel; await this._loadReviewChs(); if (params.chapter) { document.getElementById('rChapter').value = params.chapter; this._runReview(); } }
        }
    },

    async _loadReviewChs() {
        const name = document.getElementById('rNovel').value;
        const sel = document.getElementById('rChapter'); sel.innerHTML = name ? '<option value="">加载中...</option>' : '<option value="">-- 请先选小说 --</option>';
        if (!name) return;
        const resp = await API.getNovel(name);
        if (!resp.success) return;
        sel.innerHTML = '<option value="">-- 选择章节 --</option>';
        (resp.novel.volumes || []).forEach(v => v.chapters.forEach(ch => { const o = document.createElement('option'); o.value = `${v.name}/${ch.name}`; o.textContent = `${v.name}/${ch.name}`; sel.appendChild(o); }));
    },

    async _runReview() {
        const novel = document.getElementById('rNovel').value;
        const chRef = document.getElementById('rChapter').value;
        if (!novel || !chRef) { this.toast('请选择小说和章节', 'warning'); return; }
        const rd = document.getElementById('rResult');
        rd.innerHTML = '<div class="loading"><div class="spinner"></div><span>审稿中...</span></div>';
        const parts = chRef.split('/');
        const resp = await API.reviewChapter(novel, { chapter_ref: chRef.replace('.md',''), volume: parts[0], chapter_num: parts[1].replace('ch-','') });
        if (resp.success) {
            rd.innerHTML = `<div class="card" style="border-color:var(--info)"><h3>📋 审稿结果 <span class="text-sm text-muted">${resp.word_count||0}字</span></h3><div class="code-block info mt-8">${resp.ai_review}</div><h4 class="mt-16">📊 脚本检查</h4><div class="grid-3 mt-8"><div class="stat-card"><div class="stat-value" style="font-size:16px">${resp.script_results.analyze.success?'✅':'❌'}</div><div class="stat-label">字数/结构</div></div><div class="stat-card"><div class="stat-value" style="font-size:16px">${resp.script_results.compliance.success?'✅':'❌'}</div><div class="stat-label">合规检查</div></div><div class="stat-card"><div class="stat-value" style="font-size:16px">${resp.script_results.forbidden.success?'✅':'❌'}</div><div class="stat-label">禁用模式</div></div></div><details class="mt-8"><summary style="cursor:pointer;color:var(--accent)">查看详细输出</summary><div class="code-block mt-8">${['analyze','compliance','forbidden'].map(k=>'=== '+k+' ===\\n'+resp.script_results[k].stdout).join('\\n\\n')}</div></details></div>`;
            this.toast('✅ 审稿完成', 'success');
        } else { this.toast(resp.error, 'error'); rd.innerHTML = `<div class="code-block error">${resp.error}</div>`; }
    },

    // ═══════════════════════════════════════════════════════════════════
    //  CHAPTER BROWSER
    // ═══════════════════════════════════════════════════════════════════

    async _renderChapters(mc, params) {
        mc.innerHTML = `<div class="page-header"><div><h1 class="page-title">📖 章节浏览</h1><p class="page-subtitle">阅读、编辑、审稿</p></div></div><div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="cNovel" onchange="App._loadChapters()"><option value="">-- 请选择 --</option></select></div></div><div id="cList" class="mt-16"></div></div>`;
        const resp = await API.listNovels();
        if (resp.success) {
            const sel = document.getElementById('cNovel');
            resp.novels.forEach(n => { const o = document.createElement('option'); o.value = n.name; o.textContent = `${n.title||n.name} (${n.total_chapters}章)`; sel.appendChild(o); });
            if (params.novel) { sel.value = params.novel; this._loadChapters(); }
        }
    },

    async _loadChapters() {
        const name = document.getElementById('cNovel').value;
        const list = document.getElementById('cList');
        if (!name) { list.innerHTML = ''; return; }
        list.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
        const resp = await API.getNovel(name);
        if (!resp.success) return;
        const n = resp.novel;
        list.innerHTML = (n.volumes || []).map(v => {
            return `<div class="volume-header">📁 ${v.name} · ${v.chapter_count}章 · ${(v.total_words/10000).toFixed(1)}万字</div>` +
                v.chapters.map(ch => {
                    const wb = ch.words >= 2500 ? 'good' : ch.words >= 1500 ? 'warn' : 'low';
                    return `<div class="chapter-item"><span class="ch-num">${ch.name}</span><span class="ch-meta"><span class="word-badge ${wb}">${ch.words}字</span></span><div class="ch-actions"><button class="btn btn-sm btn-primary" onclick="App._openChapterReader('${name}','${v.name}/${ch.name}')">📖 阅读</button><button class="btn btn-sm btn-secondary" onclick="App._editChapterModal('${name}','${v.name}/${ch.name}')">✏️ 编辑</button><button class="btn btn-sm btn-secondary" onclick="App.navigate('review',{novel:'${name}',chapter:'${v.name}/${ch.name}'})">🔍 审稿</button></div></div>`;
                }).join('');
        }).join('') || '<div class="empty-state"><div class="empty-state-icon">📄</div><div class="empty-state-title">暂无章节</div></div>';
    },

    // ═══════════════════════════════════════════════════════════════════
    //  OUTLINES
    // ═══════════════════════════════════════════════════════════════════

    async _renderOutlines(mc) {
        mc.innerHTML = `<div class="page-header"><div><h1 class="page-title">📐 大纲管理</h1><p class="page-subtitle">查看和编辑各卷大纲</p></div></div><div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="oNovel" onchange="App._loadOutlines()"><option value="">-- 请选择 --</option></select></div></div><div id="oList" class="mt-16"></div></div>`;
        const resp = await API.listNovels();
        if (resp.success) {
            const sel = document.getElementById('oNovel');
            resp.novels.forEach(n => { const o = document.createElement('option'); o.value = n.name; o.textContent = n.title || n.name; sel.appendChild(o); });
        }
    },

    async _loadOutlines() {
        const name = document.getElementById('oNovel').value;
        const list = document.getElementById('oList');
        if (!name) { list.innerHTML = ''; return; }
        list.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
        const resp = await API.getNovel(name);
        if (!resp.success) return;
        const n = resp.novel;
        list.innerHTML = `<div class="outline-grid">${(n.outline_files||[]).map(f => `\n            <div class="outline-card" onclick="App._openOutlineEdit('${name}','${f.replace('-chapters.md','')}')"><div class="outline-vol">📐 ${f.replace('-chapters.md','')}</div><div class="outline-preview">点击查看和编辑</div></div>`).join('')}</div>`;
    },

    async _openOutlineEdit(novel, vol) {
        const resp = await API.readOutline(novel, vol);
        const content = resp.success ? resp.content : '# ' + vol + ' 大纲\n\n(新大纲)\n';
        const body = `
            <div id="outlineViewer">
                <div class="reader-toolbar">
                    <span><strong>📐 ${vol}</strong></span>
                    <button class="btn btn-sm btn-secondary" onclick="App._toggleOutlineEdit('${novel}','${vol}')">✏️ 编辑</button>
                </div>
                <div class="reader-content" style="max-height:55vh">${this.renderMarkdown(content)}</div>
            </div>
            <div id="outlineEditor" style="display:none">
                <div class="editor-panel-header">
                    <span>✏️ 编辑: ${vol}</span>
                    <button class="btn btn-sm btn-secondary" onclick="App._toggleOutlineEdit('${novel}','${vol}')">👁 预览</button>
                </div>
                <textarea class="form-textarea" id="outlineEdit" style="min-height:400px;font-family:var(--font-mono);font-size:13px;">${content.replace(/</g, '&lt;')}</textarea>
            </div>
        `;
        const footer = `<button class="btn btn-primary" onclick="App._saveOutline('${novel}','${vol}')">💾 保存</button><button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">取消</button>`;
        const modal = this.modal(`📐 ${vol}`, body, footer, '800px');
        modal._novel = novel;
        modal._vol = vol;
        modal._content = content;
    },

    _toggleOutlineEdit(novel, vol) {
        const viewer = document.getElementById('outlineViewer');
        const editor = document.getElementById('outlineEditor');
        const textarea = document.getElementById('outlineEdit');
        if (editor.style.display === 'none') {
            viewer.style.display = 'none';
            editor.style.display = 'block';
            textarea.focus();
        } else {
            // Update preview from textarea
            const previewContent = textarea.value;
            viewer.querySelector('.reader-content').innerHTML = this.renderMarkdown(previewContent);
            viewer.style.display = 'block';
            editor.style.display = 'none';
        }
    },

    async _saveOutline(novel, vol) {
        const content = document.getElementById('outlineEdit').value;
        const resp = await API.editOutline(novel, vol, content);
        resp.success ? (this.toast('✅ 大纲已保存', 'success'), document.querySelectorAll('.modal-overlay').forEach(m => m.remove()), this._loadOutlines()) : this.toast(resp.error, 'error');
    },

    // ═══════════════════════════════════════════════════════════════════
    //  SETTINGS
    // ═══════════════════════════════════════════════════════════════════

    async _renderSettings(mc) {
        const cfgResp = await API.getConfig();
        if (cfgResp.success) { this.config = cfgResp; this._updateSidebarStatus(cfgResp); }
        const cfg = this.config;

        mc.innerHTML = `
            <div class="page-header"><div><h1 class="page-title">⚙️ 设置</h1><p class="page-subtitle">DeepSeek API 配置 · 模型参数</p></div></div>
            <div class="grid-2">
                <div class="card with-accent">
                    <h3 class="card-title">🤖 DeepSeek API 配置</h3>
                    <p class="text-secondary mt-8" style="font-size:12px">在此页直接配置，即时生效。无需修改环境变量。</p>
                    <div class="form-group mt-16"><label class="form-label">API Key *</label><div class="password-wrapper"><input class="form-input" id="sApiKey" type="password" placeholder="sk-..." value="${cfg.deepseek_key_set_via_ui||''}"><button class="password-toggle" onclick="App._togglePw('sApiKey',this)">👁</button></div><div class="text-muted" style="font-size:11px;margin-top:4px">${cfg.deepseek_configured ? '当前: <code>'+cfg.deepseek_key_masked+'</code>' : '首次使用请填入 DeepSeek API Key'}</div></div>
                    <div class="form-group mt-12"><label class="form-label">API Base URL</label><input class="form-input" id="sApiBase" placeholder="${cfg.deepseek_api_base || 'https://api.deepseek.com'}" value="${cfg.deepseek_api_base && cfg.deepseek_api_base!=='https://api.deepseek.com' ? cfg.deepseek_api_base : ''}"><div class="text-muted" style="font-size:11px;margin-top:4px">留空=默认 <code>https://api.deepseek.com</code></div></div>
                    <div class="form-group mt-12"><label class="form-label">模型</label><div class="form-row" style="grid-template-columns:1fr auto"><input class="form-input" id="sModel" placeholder="${cfg.deepseek_model||'deepseek-chat'}" value="${cfg.deepseek_model&&cfg.deepseek_model!=='deepseek-chat'?cfg.deepseek_model:''}"><select class="form-select" onchange="document.getElementById('sModel').value=this.value" style="width:auto"><option value="">常用</option><option value="deepseek-chat">deepseek-chat (V3)</option><option value="deepseek-reasoner">deepseek-reasoner (R1)</option><option value="deepseek-v4-pro">deepseek-v4-pro</option><option value="deepseek-v4-flash">deepseek-v4-flash</option></select></div></div>
                    <div class="flex gap-8 mt-16"><button class="btn btn-primary" onclick="App._saveSettings()">💾 保存</button><button class="btn btn-success" id="sTestBtn" onclick="App._testCfg()" ${cfg.deepseek_configured?'':'disabled'}>🔌 测试连接</button></div>
                    <div id="sResult" class="mt-12"></div>
                </div>

                <div class="card">
                    <h3 class="card-title">🎛️ 生成参数</h3>
                    <div class="form-group mt-16"><label class="form-label">温度 (Temperature) <span class="text-muted" style="font-size:11px" id="sTempVal">${cfg.deepseek_temperature||0.7}</span></label><div class="param-slider-group"><input type="range" id="sTemperature" min="0" max="1.5" step="0.05" value="${cfg.deepseek_temperature||0.7}" oninput="document.getElementById('sTempVal').textContent=this.value"><span class="param-value">${cfg.deepseek_temperature||0.7}</span></div><p class="text-muted" style="font-size:11px;margin-top:6px">低=更稳定一致，高=更有创造力</p></div>
                    <div class="form-group mt-16"><label class="form-label">最大Token (Max Tokens) <span class="text-muted" style="font-size:11px" id="sMaxTokVal">${cfg.deepseek_max_tokens||8192}</span></label><div class="param-slider-group"><input type="range" id="sMaxTokens" min="1024" max="16384" step="1024" value="${cfg.deepseek_max_tokens||8192}" oninput="document.getElementById('sMaxTokVal').textContent=this.value"><span class="param-value">${cfg.deepseek_max_tokens||8192}</span></div><p class="text-muted" style="font-size:11px;margin-top:6px">单次生成的最大输出长度</p></div>
                    <div class="form-group mt-16"><label class="form-label">Top P <span class="text-muted" style="font-size:11px" id="sTopPVal">${cfg.deepseek_top_p||0.9}</span></label><div class="param-slider-group"><input type="range" id="sTopP" min="0.1" max="1" step="0.05" value="${cfg.deepseek_top_p||0.9}" oninput="document.getElementById('sTopPVal').textContent=this.value"><span class="param-value">${cfg.deepseek_top_p||0.9}</span></div><p class="text-muted" style="font-size:11px;margin-top:6px">核采样，1=考虑所有词汇，越低越聚焦</p></div>
                </div>

                <div class="card"><h3 class="card-title">📂 系统信息</h3><div class="mt-8"><div class="info-row"><span class="info-label">状态</span><span class="badge ${cfg.deepseek_configured?'badge-success':'badge-warning'}">${cfg.deepseek_configured?'已配置':'未配置'}</span></div><div class="info-row"><span class="info-label">模型</span><span class="text-mono">${cfg.deepseek_model||'deepseek-chat'}</span></div><div class="info-row"><span class="info-label">温度</span><span class="text-mono">${cfg.deepseek_temperature||0.7}</span></div><div class="info-row"><span class="info-label">Max Tokens</span><span class="text-mono">${cfg.deepseek_max_tokens||8192}</span></div><div class="info-row"><span class="info-label">Top P</span><span class="text-mono">${cfg.deepseek_top_p||0.9}</span></div><div class="info-row"><span class="info-label">项目</span><span class="text-mono">${cfg.agent_root||'N/A'}</span></div><div class="info-row"><span class="info-label">小说</span><span class="text-mono">${cfg.novels_root||'N/A'}</span></div></div></div>

                <div class="card"><h3 class="card-title">📊 使用统计</h3><div class="mt-8"><button class="btn btn-secondary" onclick="App._refreshStats(this)">🔄 刷新统计</button><div id="statsDisplay" class="mt-8"></div></div></div>
            </div>
        `;
    },

    _togglePw(inputId, btn) {
        const input = document.getElementById(inputId);
        input.type = input.type === 'password' ? 'text' : 'password';
        btn.textContent = input.type === 'password' ? '👁' : '🙈';
    },

    async _saveSettings() {
        const data = {
            api_key: document.getElementById('sApiKey').value.trim(),
            api_base: document.getElementById('sApiBase').value.trim(),
            model: document.getElementById('sModel').value.trim(),
            temperature: document.getElementById('sTemperature').value,
            max_tokens: document.getElementById('sMaxTokens').value,
            top_p: document.getElementById('sTopP').value,
        };
        if (!data.api_key) { this.toast('请输入 API Key', 'warning'); return; }
        const resp = await API.saveConfig(data);
        if (resp.success) {
            this.toast('✅ 配置已保存', 'success');
            this.config = { ...this.config, ...resp };
            this._updateSidebarStatus(resp);
            document.getElementById('sResult').innerHTML = `<div class="code-block success">✅ 已保存\n模型: ${resp.deepseek_model}\n温度: ${resp.deepseek_temperature}\nMaxTokens: ${resp.deepseek_max_tokens}</div>`;
            document.getElementById('sTestBtn').disabled = false;
        } else {
            this.toast(resp.error, 'error');
            document.getElementById('sResult').innerHTML = `<div class="code-block error">${resp.error}</div>`;
        }
    },

    async _testCfg() {
        const btn = document.getElementById('sTestBtn'), rd = document.getElementById('sResult');
        btn.disabled = true; btn.textContent = '⏳ 测试中...';
        rd.innerHTML = '<div class="loading"><div class="spinner"></div><span>连接中...</span></div>';
        const resp = await API.testConfig();
        btn.disabled = false; btn.textContent = '🔌 测试连接';
        if (resp.success) { this.toast('✅ 连接成功', 'success'); rd.innerHTML = `<div class="code-block success">${resp.message}\n模型: ${resp.model}</div>`; }
        else { this.toast(resp.error, 'error'); rd.innerHTML = `<div class="code-block error">${resp.error}</div>`; }
    },

    async _refreshStats(btn) {
        btn.disabled = true; btn.textContent = '⏳ 刷新中...';
        const resp = await API.listNovels();
        if (resp.success) {
            const total = resp.novels.length;
            const ch = resp.novels.reduce((s,n)=>s+(n.total_chapters||0),0);
            const w = resp.novels.reduce((s,n)=>s+(n.total_words||0),0);
            const r = resp.novels.reduce((s,n)=>s+(n.review_count||0),0);
            document.getElementById('statsDisplay').innerHTML = `<div class="stats-grid" style="grid-template-columns:repeat(4,1fr)"><div class="stat-card"><div class="stat-value">${total}</div><div class="stat-label">小说</div></div><div class="stat-card"><div class="stat-value">${ch}</div><div class="stat-label">章节</div></div><div class="stat-card"><div class="stat-value">${(w/10000).toFixed(1)}万</div><div class="stat-label">字数</div></div><div class="stat-card"><div class="stat-value">${r}</div><div class="stat-label">审稿</div></div></div>`;
        }
        btn.disabled = false; btn.textContent = '🔄 刷新';
    },
};

document.addEventListener('DOMContentLoaded', () => App.init());
