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
        // Wizard option delegation
        document.getElementById('mainContent').addEventListener('click', (e) => {
            const option = e.target.closest('.wizard-option');
            if (option) {
                const idx = parseInt(option.dataset.idx);
                const label = option.dataset.label;
                const desc = option.dataset.desc || '';
                this._wizardSelect(idx, label, desc);
            }
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
                case 'quality': await this._renderQuality(mc); break;
                case 'search': await this._renderSearch(mc); break;
                case 'config': await this._renderConfig(mc); break;
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
        let html = text
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            // Headers
            .replace(/^### (.+)$/gm, '<h3>$1</h3>')
            .replace(/^## (.+)$/gm, '<h2>$1</h2>')
            .replace(/^# (.+)$/gm, '<h1>$1</h1>')
            // Bold/italic
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            // Code blocks
            .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            // HR
            .replace(/^---$/gm, '<hr>')
            // Blockquote
            .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
            // Unordered lists
            .replace(/^[*-] (.+)$/gm, '<li>$1</li>')
            // Ordered lists
            .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
            // Table rows
            .replace(/^\|(.+)\|$/gm, (m) => '<tr>' + m.slice(1, -1).split('|').map(c => /^[-:\s]+$/.test(c.trim()) ? '<th></th>' : '<td>' + c.trim() + '</td>').join('') + '</tr>')
            // Wrap lists
            .replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')
            // Wrap paragraphs: split by double newline, wrap non-tag blocks
            .replace(/\n{2,}/g, '\n</p><p>\n')
            .replace(/^(?!<)/gm, '<p>')
            .replace(/(?<!>)$/gm, '</p>')
            // Clean empty <p></p>
            .replace(/<p>\s*<\/p>/g, '');
        return html;
    },

    _wordBadge(wc) {
        const cls = wc >= 2500 ? 'good' : wc >= 1500 ? 'warn' : 'low';
        return `<span class="word-badge ${cls}">📝 ${wc}字</span>`;
    },

    _escapeHtml(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    },

    _escapeAttr(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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
        // Find most chaptered novel for continue label
        var bestNovel = novels[0];
        novels.forEach(function(n) { if ((n.total_chapters||0) > (bestNovel?.total_chapters||0)) bestNovel = n; });
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
                <div class="quick-action" onclick="App._continueWriting()"><div class="qa-icon">▶️</div><div class="qa-label">继续写作</div><div class="qa-desc" id="qaContinueDesc">${bestNovel ? (bestNovel.last_chapter||'无章节') : '无项目'}</div></div>
                <div class="quick-action" onclick="App.navigate('writing')"><div class="qa-icon">✍️</div><div class="qa-label">写作台</div><div class="qa-desc">生成新章节</div></div>
                <div class="quick-action" onclick="App.navigate('chapters')"><div class="qa-icon">📖</div><div class="qa-label">章节浏览</div><div class="qa-desc">阅读和编辑</div></div>
                <div class="quick-action" onclick="App.navigate('outlines')"><div class="qa-icon">📐</div><div class="qa-label">大纲管理</div><div class="qa-desc">规划和编辑</div></div>
                <div class="quick-action" onclick="App.navigate('settings')"><div class="qa-icon">⚙️</div><div class="qa-label">模型配置</div><div class="qa-desc">DeepSeek设置</div></div>
            </div>` : ''}
            ${qualityCards}
            <div class="card mt-16">
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
                <div class="reader-content" style="max-height:45vh">${this.renderMarkdown((n.project_content || '').substring(0, 5000))}</div>
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
                var hasFile = n[f.replace('.md', '_content')] || n[`${f.replace('/', '_')}_content`];
                var info = n[f.replace('.md', '_info')];
                var meta = hasFile ? '已存在' : '未创建';
                if (info) {
                    var kb = Math.round(info.size/1024);
                    var d = new Date(info.mtime*1000);
                    meta = kb + 'KB · ' + (d.getMonth()+1) + '/' + d.getDate();
                }
                return '<div class="chapter-item" onclick="App._openFileModal(\'' + n.name + '\',\'' + f + '\')"><span class="ch-num">📄</span><span class="ch-title">' + f + '</span><span class="ch-meta">' + meta + '</span></div>';
            }).join('');
        }
    },

    async _openFileModal(novel, path) {
        const resp = await API.readFile(novel, path);
        if (!resp.success) { this.toast(resp.error, 'error'); return; }
        var escapedContent = resp.content.replace(/</g, '&lt;').replace(/&/g, '&amp;');
        var body = '' +
            '<div class="editor-container">' +
            '<div class="editor-panel"><div class="editor-panel-header">📝 编辑 ' + path + '</div><textarea class="editor-textarea" id="fileEdit" style="font-size:12px">' + escapedContent + '</textarea></div>' +
            '<div class="preview-panel"><div class="preview-panel-header">👁 预览</div><div class="preview-content" id="filePreview">' + this.renderMarkdown(resp.content) + '</div></div>' +
            '</div>';
        var footer = '<button class="btn btn-primary" onclick="App._saveFile(\'' + novel + '\',\'' + path + '\')">💾 保存</button><button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">取消</button>';
        var modal = this.modal('📄 ' + path, body, footer, '90vw');
        // Live preview
        setTimeout(function() {
            var ta = document.getElementById('fileEdit');
            var pv = document.getElementById('filePreview');
            if (ta && pv) ta.addEventListener('input', function() {
                pv.innerHTML = App.renderMarkdown(ta.value.replace(/&lt;/g, '<').replace(/&amp;/g, '&').replace(/&gt;/g, '>').replace(/&quot;/g, '"'));
            });
        }, 100);
    },

    _saveFile(novel, path) {
        var content = document.getElementById('fileEdit').value;
        var decoded = content.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').replace(/&quot;/g, '"');
        API.writeFile(novel, path, decoded).then(function(wr) {
            wr.success ? App.toast('✅ 已保存', 'success') : App.toast(wr.error||'保存失败', 'error');
            document.querySelectorAll('.modal-overlay').forEach(function(m) { m.remove(); });
        });
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
    //  NEW BOOK (AI Wizard v2 — fixed dropdowns first, then AI)
    // ═══════════════════════════════════════════════════════════════════

    STEP_IDS: ['name', 'genre', 'subgenre', 'word_goal', 'protagonist', 'selling_point', 'world_setting', 'style'],

    async _renderNewBook(mc) {
        const ok = this.config.deepseek_configured;
        if (!ok) {
            mc.innerHTML = `<div class="page-header"><div><h1 class="page-title">✨ 创建新书</h1><p class="page-subtitle">交互式创作向导</p></div></div><div class="card" style="border-color:var(--warning)"><div class="flex items-center gap-3"><span style="font-size:24px">⚠️</span><div><strong style="color:var(--warning)">API Key 未配置</strong><p class="text-secondary mt-2">请先在 <a href="#" onclick="App.navigate('settings')" style="color:var(--accent)">⚙️ 设置</a> 填入 DeepSeek API Key</p></div></div></div>`;
            return;
        }
        this._wizard = { step: 0, selections: {}, loading: false };
        mc.innerHTML = `<div class="page-header"><div><h1 class="page-title">✨ 创建新书</h1><p class="page-subtitle">4 步人工选择 + 4 步 AI 推荐</p></div></div>
            <div class="wizard-flow-hint">
                <span class="wiz-flow-step manual">✏️ 书名</span> →
                <span class="wiz-flow-step manual">📋 题材</span> →
                <span class="wiz-flow-step manual">📋 细分</span> →
                <span class="wiz-flow-step manual">📋 篇幅</span> →
                <span class="wiz-flow-step ai">🤖 主角</span> →
                <span class="wiz-flow-step ai">🤖 卖点</span> →
                <span class="wiz-flow-step ai">🤖 世界观</span> →
                <span class="wiz-flow-step ai">🎨 风格</span>
            </div>
            <div id="wizardStep"></div>`;
        await this._loadWizardStep(0);
    },

    async _loadWizardStep(index) {
        const w = this._wizard;
        w.step = index;
        w.loading = true;
        const container = document.getElementById('wizardStep');
        if (!container) return;

        const total = this.STEP_IDS.length;
        const stepLabel = this.STEP_IDS[index] ? (['书名','题材','细分','篇幅','主角','卖点','世界观','风格'][index]) : '';

        // Show brief loading state (crucial for AI steps, instant for select)
        var loadMsg = index >= 4 ? '🤖 AI 正在生成推荐...' : '加载选项...';
        container.innerHTML = '<div class="wizard-progress"><div class="wizard-progress-bar"><div class="wizard-progress-fill" style="width:' + ((index+1)/total*100) + '%"></div></div><span class="wizard-progress-text">' + (index+1) + ' / ' + total + ' · ' + stepLabel + '</span></div><div class="card"><div class="loading" style="padding:30px"><div class="spinner"></div><span>' + loadMsg + '</span></div></div>';
        // Call API first to know step type
        const resp = await API.wizardStep({ step_index: index, selections: w.selections });
        w.loading = false;

        if (!resp.success) {
            container.innerHTML = `<div class="card"><div class="code-block error">${resp.error}<br><button class="btn btn-secondary mt-8" onclick="App._loadWizardStep(${index})">🔄 重试</button></div></div>`;
            return;
        }

        const step = resp.step;
        const stepType = resp.step_type;
        const options = resp.options || [];
        const isAiStep = stepType === 'ai';

        // Summary tags
        let summaryHtml = '';
        const entries = Object.entries(w.selections);
        if (entries.length > 0) {
            summaryHtml = `<div class="wizard-summary">${entries.map(([k, v]) => `<span class="wizard-tag" title="${k}">${v}</span>`).join('')}</div>`;
        }

        // --- INPUT STEP ---
        if (stepType === 'input') {
            container.innerHTML = `
                <div class="wizard-progress"><div class="wizard-progress-bar"><div class="wizard-progress-fill" style="width:${((index+1)/total*100)}%"></div></div><span class="wizard-progress-text">${index+1} / ${total} · ${stepLabel}</span></div>
                <div class="wizard-question-card">
                    <div class="wizard-question">${step.question}</div>
                    ${summaryHtml}
                    <div class="wizard-input-area">
                        <input class="form-input wizard-input-lg" id="wizInput" placeholder="${step.placeholder || ''}" value="${w.selections.name || ''}" autofocus>
                        <button class="btn btn-primary btn-lg" onclick="App._wizardInputNext(${index})">→ 下一步</button>
                    </div>
                </div>
            `;
            document.getElementById('wizInput')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') App._wizardInputNext(index); });
            return;
        }

        // --- SELECT / AI / MULTI STEP ---

        const isMulti = resp.multi === true;
        const aiBadge = isAiStep ? ' <span class="wizard-ai-badge">🤖 AI</span>' : '';
        const backBtn = index > 0 ? '<button class="btn btn-secondary" onclick="App._wizardBack(' + index + ')">← 上一步</button>' : '';
        const refreshBtn = isAiStep ? '<button class="btn btn-secondary" onclick="App._loadWizardStep(' + index + ')">🔄 换一批</button>' : '';

        // Build options HTML
        let optionsHtml;
        const isStyle = stepType === 'style_select';
        if (isAiStep && !options.length && w.loading) {
            optionsHtml = '<div class="loading" style="padding:40px"><div class="spinner"></div><span>AI 正在生成推荐...</span></div>';
        } else if (isStyle) {
            // Style select with percentage sliders
            if (!w._stylePcts) w._stylePcts = {};
            var sp = w._stylePcts;
            optionsHtml = '<div class="wizard-options wizard-options-multi">' + options.map(function(opt) {
                var s = !!sp[opt.label], el = App._escapeAttr(opt.label), eh = App._escapeHtml(opt.label);
                var pct = sp[opt.label] || 0;
                var sliderHtml = s ? '<div class="wizard-pct-row"><input type="range" class="wizard-pct-slider" min="5" max="100" value="' + pct + '" data-slbl="' + el + '" oninput="App._stylePctChange(this)" onclick="event.stopPropagation()"><span class="wizard-pct-val">' + pct + '%</span></div>' : '';
                return '<div class="wizard-option wizard-multi-opt' + (s ? ' selected' : '') + '" data-mlabel="' + el + '" onclick="App._toggleStyle(this,\'' + el + '\')"><div class="wizard-option-check">' + (s ? '☑' : '☐') + '</div><div class="wizard-option-label">' + eh + '</div>' + sliderHtml + '</div>';
            }).join('') + '</div>';
        } else if (isMulti) {
            if (!w._multiSelected) w._multiSelected = new Set();
            var msel = w._multiSelected;
            optionsHtml = '<div class="wizard-options wizard-options-multi">' + options.map(function(opt) {
                var s = msel.has(opt.label), el = App._escapeAttr(opt.label), eh = App._escapeHtml(opt.label);
                return '<div class="wizard-option wizard-multi-opt' + (s ? ' selected' : '') + '" data-mlabel="' + el + '" onclick="App._toggleMulti(this,\'' + el + '\')"><div class="wizard-option-check">' + (s ? '☑' : '☐') + '</div><div class="wizard-option-label">' + eh + '</div></div>';
            }).join('') + '</div>';
        } else {
            optionsHtml = '<div class="wizard-options">' + options.map(function(opt) {
                var el = App._escapeAttr(opt.label), ed = App._escapeAttr(opt.desc || ''), eh = App._escapeHtml(opt.label);
                var descHtml = opt.desc ? '<div class="wizard-option-desc">' + App._escapeHtml(opt.desc) + '</div>' : '';
                return '<div class="wizard-option" data-idx="' + index + '" data-label="' + el + '" data-desc="' + ed + '"><div class="wizard-option-label">' + eh + '</div>' + descHtml + '<div class="wizard-option-pick">选择 →</div></div>';
            }).join('') + '</div>';
        }

        // Footer
        var footerHtml;
        if (isStyle) {
            var totalPct = Object.values(w._stylePcts || {}).reduce(function(a,b){return a+b;}, 0);
            footerHtml = '<div class="wizard-multi-footer"><span class="text-secondary">风格占比: <strong id="pctTotal" style="color:' + (totalPct === 100 ? 'var(--success)' : 'var(--warning)') + '">' + totalPct + '%</strong></span><button class="btn btn-primary btn-lg" id="styleConfirmBtn" onclick="App._confirmStyle(' + index + ')"' + (totalPct !== 100 ? ' disabled' : '') + '>✓ 确认' + (totalPct !== 100 ? '（需凑满100%）' : '') + '</button>' + backBtn + '</div>';
        } else if (isMulti) {
            var cnt = w._multiSelected ? w._multiSelected.size : 0;
            footerHtml = '<div class="wizard-multi-footer"><span class="text-secondary" style="font-size:13px">已选 <strong style="color:var(--accent)" id="multiCount">' + cnt + '</strong> 项</span><button class="btn btn-primary btn-lg" id="multiConfirmBtn" onclick="App._confirmMulti(' + index + ')"' + (cnt === 0 ? ' disabled' : '') + '>✓ 确认选择</button>' + backBtn + '</div>';
        } else if (resp.allow_custom) {
            footerHtml = '<div class="wizard-custom"><span class="text-muted">或自定义：</span><div class="form-row" style="grid-template-columns:1fr auto"><input class="form-input" id="wizCustom" placeholder="输入自定义内容..."><button class="btn btn-secondary" onclick="App._wizardCustom(' + index + ')">✓ 使用</button></div></div><div class="wizard-actions mt-16">' + backBtn + refreshBtn + '</div>';
        } else {
            footerHtml = '<div class="wizard-actions mt-16">' + backBtn + refreshBtn + '</div>';
        }

        container.innerHTML =
            '<div class="wizard-progress"><div class="wizard-progress-bar"><div class="wizard-progress-fill' + (isAiStep ? ' ai-glow' : '') + '" style="width:' + ((index + 1) / total * 100) + '%"></div></div><span class="wizard-progress-text">' + (index + 1) + ' / ' + total + ' · ' + stepLabel + aiBadge + '</span></div>' +
            '<div class="wizard-question-card"><div class="wizard-question">' + step.question + '</div>' + summaryHtml + optionsHtml + footerHtml + '</div>';
    },

    _toggleMulti(el, label) {
        const w = this._wizard;
        if (!w._multiSelected) w._multiSelected = new Set();
        const sel = w._multiSelected;
        if (sel.has(label)) sel.delete(label); else sel.add(label);
        el.classList.toggle('selected', sel.has(label));
        el.querySelector('.wizard-option-check').textContent = sel.has(label) ? '☑' : '☐';
        // Update count
        const cnt = document.getElementById('multiCount');
        if (cnt) cnt.textContent = sel.size;
        const btn = document.getElementById('multiConfirmBtn');
        if (btn) btn.disabled = sel.size === 0;
    },

    _confirmMulti(index) {
        const w = this._wizard;
        const labels = [...(w._multiSelected || [])];
        if (labels.length === 0) { this.toast('请至少选择一项', 'warning'); return; }
        const stepId = this.STEP_IDS[index];
        w.selections[stepId] = labels.join(', ');
        w._multiSelected = new Set();
        this._loadWizardStep(index + 1);
    },

    _toggleStyle(el, label) {
        const w = this._wizard;
        if (!w._stylePcts) w._stylePcts = {};
        if (w._stylePcts[label]) {
            delete w._stylePcts[label];
        } else {
            // Distribute evenly among selected
            var keys = Object.keys(w._stylePcts);
            keys.push(label);
            var each = Math.floor(100 / keys.length);
            var rem = 100 - each * keys.length;
            keys.forEach(function(k, i) { w._stylePcts[k] = each + (i < rem ? 1 : 0); });
        }
        // Re-render this step
        this._loadWizardStep(this._wizard.step);
    },

    _stylePctChange(slider) {
        const w = this._wizard;
        if (!w._stylePcts) return;
        var label = slider.dataset.slbl;
        var val = parseInt(slider.value);
        w._stylePcts[label] = val;
        // Update display
        var row = slider.closest('.wizard-pct-row');
        if (row) row.querySelector('.wizard-pct-val').textContent = val + '%';
        // Update total
        var total = Object.values(w._stylePcts).reduce(function(a,b){return a+b;}, 0);
        var totalEl = document.getElementById('pctTotal');
        if (totalEl) {
            totalEl.textContent = total + '%';
            totalEl.style.color = total === 100 ? 'var(--success)' : 'var(--warning)';
        }
        var btn = document.getElementById('styleConfirmBtn');
        if (btn) {
            btn.disabled = total !== 100;
            btn.textContent = total === 100 ? '✓ 确认' : '✓ 确认（需凑满100%）';
        }
    },

    _confirmStyle(index) {
        const w = this._wizard;
        var parts = [];
        var sp = w._stylePcts || {};
        Object.keys(sp).forEach(function(k) { parts.push(k + ' ' + sp[k] + '%'); });
        if (parts.length === 0) { this.toast('请至少选择一种风格', 'warning'); return; }
        w.selections.style = parts.join(', ');
        w._stylePcts = {};
        this._loadWizardStep(index + 1);
    },

    _wizardInputNext(index) {
        const val = document.getElementById('wizInput')?.value.trim();
        if (!val) { this.toast('请输入内容', 'warning'); return; }
        this._wizard.selections.name = val;
        this._loadWizardStep(index + 1);
    },

    async _wizardSelect(index, label, desc) {
        const w = this._wizard;
        const stepId = this.STEP_IDS[index];
        if (!stepId) return;
        w.selections[stepId] = label;

        if (index >= this.STEP_IDS.length - 1) {
            await this._wizardConfirm();
        } else {
            await this._loadWizardStep(index + 1);
        }
    },

    async _wizardCustom(index) {
        const input = document.getElementById('wizCustom');
        const val = input?.value.trim();
        if (!val) { this.toast('请输入内容', 'warning'); return; }
        await this._wizardSelect(index, val, '自定义');
    },

    async _wizardBack(index) {
        const keys = Object.keys(this._wizard.selections);
        const prevKey = this.STEP_IDS[index - 1];
        if (prevKey && this._wizard.selections[prevKey]) {
            delete this._wizard.selections[prevKey];
        }
        await this._loadWizardStep(index - 1);
    },

    async _wizardConfirm() {
        const w = this._wizard;
        const container = document.getElementById('wizardStep');
        const s = w.selections;

        const labels = {name:'书名',genre:'题材',subgenre:'细分',word_goal:'篇幅',protagonist:'主角',selling_point:'卖点',world_setting:'世界观',style:'风格'};
        const items = Object.entries(labels).map(([k, lbl]) => {
            const val = s[k] || '未设置';
            return `<div class="wizard-confirm-item"><div class="wizard-confirm-label">${lbl}</div><div class="wizard-confirm-value">${val}</div></div>`;
        }).join('');

        container.innerHTML = `
            <div class="wizard-progress"><div class="wizard-progress-bar"><div class="wizard-progress-fill" style="width:100%"></div></div><span class="wizard-progress-text">✅ 确认</span></div>
            <div class="wizard-question-card">
                <div class="wizard-question">📋 确认设定 · AI 将根据以下信息创建小说</div>
                <div class="wizard-confirm-grid">${items}</div>
                <div class="wizard-actions mt-16">
                    <button class="btn btn-secondary" onclick="App._wizardBack(${App.STEP_IDS.length - 1})">← 修改</button>
                    <button class="btn btn-primary btn-lg" id="wizCreateBtn" onclick="App._wizardCreate()">🚀 AI 创建小说 + 生成大纲</button>
                </div>
                <div id="wizCreateResult" class="mt-16"></div>
            </div>
        `;
    },

    async _wizardCreate() {
        const btn = document.getElementById('wizCreateBtn');
        btn.disabled = true; btn.textContent = '⏳ AI 生成中...';
        const rd = document.getElementById('wizCreateResult');

        const s = this._wizard.selections;
        const resp = await API.createNovel({
            name: s.name,
            genre: s.genre,
            protagonist: s.protagonist,
            selling_point: s.selling_point,
            word_goal: s.word_goal || '100万',
            perspective: '第三人称',
            references: `细分: ${s.subgenre || '无'} | 世界观: ${s.world_setting || '无'} | 风格: ${s.style || '默认'}`,
        });

        btn.disabled = false; btn.textContent = '🚀 AI 创建小说 + 生成大纲';
        if (resp.success) {
            this.toast(`🎉 小说「${resp.novel_name}」创建成功！`, 'success');
            rd.innerHTML = `<div class="card" style="border-color:var(--success)"><h3>✅ 创建成功</h3><p class="text-secondary mt-8">已创建文件：</p><div class="code-block success mt-8">${resp.created_files.join('\\n')}</div><div class="mt-16 flex gap-8"><button class="btn btn-primary" onclick="App.navigate('novels')">📚 查看项目</button><button class="btn btn-success" onclick="App.navigate('writing',{novel:'${resp.novel_name}'})">✍️ 开始写作</button><button class="btn btn-secondary" onclick="App.navigate('outlines')">📐 管理大纲</button></div></div>`;
        } else {
            this.toast(`创建失败: ${resp.error}`, 'error');
            rd.innerHTML = `<div class="code-block error">${resp.error}</div>`;
        }
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
                    <div class="form-row mt-12"><div class="form-group"><label class="form-label">章节编号</label><input class="form-input" id="wChapterNum" placeholder="如：1, 2... 留空自动推断"></div><div class="form-group"><label class="form-label">风格</label><div id="wStyleArea"><button class="btn btn-secondary" onclick="App._toggleStylePicker()" style="width:100%" id="wStyleBtn">🎨 选择风格</button><div id="wStylePicker" style="display:none;margin-top:8px"></div><div id="wStyleTags" class="wizard-summary" style="margin-top:6px"></div></div></div></div>
                    <div class="form-group mt-12"><label class="form-label">写作指示（可选）</label><textarea class="form-textarea" id="wInstructions" rows="2" placeholder="对本章的特殊要求..."></textarea></div>
                    <div class="form-group mt-8" style="display:flex;align-items:center;gap:8px"><input type="checkbox" id="wAutoReview" style="accent-color:var(--accent)"><label for="wAutoReview" style="font-size:13px;color:var(--text-secondary);cursor:pointer">✅ 生成后自动审稿优化</label></div>
                    <div class="form-row mt-12">
                        <div class="form-group"><label class="form-label">温度 <span class="text-muted" style="font-size:11px" id="wTempVal">${this.config.deepseek_temperature || 0.8}</span></label><div class="param-slider-group"><input type="range" id="wTemperature" min="0" max="1.5" step="0.05" value="${this.config.deepseek_temperature || 0.8}" oninput="document.getElementById('wTempVal').textContent=this.value"><span class="param-value">${this.config.deepseek_temperature || 0.8}</span></div></div>
                        <div class="form-group"><label class="form-label">最大Token <span class="text-muted" style="font-size:11px" id="wMaxTokVal">${this.config.deepseek_max_tokens || 8192}</span></label><div class="param-slider-group"><input type="range" id="wMaxTokens" min="1024" max="16384" step="1024" value="${this.config.deepseek_max_tokens || 8192}" oninput="document.getElementById('wMaxTokVal').textContent=this.value"><span class="param-value">${this.config.deepseek_max_tokens || 8192}</span></div></div>
                    </div>
                    <div class="flex gap-8 mt-16">
                        <button class="btn btn-primary btn-lg" onclick="App._genChapter(false)">✍️ 生成单章（自动保存）</button>
                        <button class="btn btn-success btn-lg" onclick="App._genChapter(true)">⚡ 流式预览（手动保存）</button>
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

    STYLE_OPTIONS: [
        {label:'金庸风',desc:'传统武侠，典雅大气'},{label:'古龙风',desc:'简洁凌厉，意境留白'},
        {label:'番茄风',desc:'爽文直白，快节奏'},{label:'辰东风',desc:'宏大叙事，设定丰富'},
        {label:'宅猪风',desc:'东方神话，厚重底蕴'},{label:'猫腻风',desc:'文艺心机，伏笔深远'},
        {label:'烽火风',desc:'华丽辞藻，情感浓烈'},{label:'土豆风',desc:'热血升级，打脸爽快'},
        {label:'老鹰风',desc:'搞笑玩梗，轻松愉快'},{label:'乌贼风',desc:'诡秘设定，逻辑严密'},
        {label:'三少风',desc:'升级打怪，稳定更新'},{label:'江南风',desc:'青春忧伤，文笔细腻'},
    ],

    _toggleStylePicker() {
        var picker = document.getElementById('wStylePicker');
        if (!picker) return;
        if (picker.style.display === 'none') {
            this._renderStylePicker();
            picker.style.display = 'block';
        } else {
            picker.style.display = 'none';
        }
    },

    _renderStylePicker() {
        if (!this._writingStyles) this._writingStyles = {};
        var ws = this._writingStyles;
        var picker = document.getElementById('wStylePicker');
        var self = this;
        picker.innerHTML = '<div class="wizard-options wizard-options-multi" style="grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:6px">' +
            this.STYLE_OPTIONS.map(function(opt) {
                var sel = !!ws[opt.label], el = self._escapeAttr(opt.label), eh = self._escapeHtml(opt.label);
                var pct = ws[opt.label] || 0;
                var slider = sel ? '<div class="wizard-pct-row" style="margin-top:4px;padding-top:4px"><input type="range" class="wizard-pct-slider" min="5" max="100" value="' + pct + '" data-slbl="' + el + '" oninput="App._writeStylePct(this)" onclick="event.stopPropagation()"><span class="wizard-pct-val">' + pct + '%</span></div>' : '';
                return '<div class="wizard-option wizard-multi-opt' + (sel ? ' selected' : '') + '" style="padding:6px 8px !important" data-mlabel="' + el + '" onclick="App._toggleWriteStyle(this,\'' + el + '\')"><div class="wizard-option-check" style="font-size:14px">' + (sel ? '☑' : '☐') + '</div><div class="wizard-option-label" style="font-size:12px">' + eh + '</div>' + slider + '</div>';
            }).join('') + '</div>';
        this._updateStyleTags();
    },

    _toggleWriteStyle(el, label) {
        if (!this._writingStyles) this._writingStyles = {};
        var ws = this._writingStyles;
        if (ws[label]) { delete ws[label]; }
        else {
            var keys = Object.keys(ws); keys.push(label);
            var each = Math.floor(100 / keys.length), rem = 100 - each * keys.length;
            keys.forEach(function(k, i) { ws[k] = each + (i < rem ? 1 : 0); });
        }
        this._renderStylePicker();
    },

    _writeStylePct(slider) {
        if (!this._writingStyles) return;
        var label = slider.dataset.slbl;
        this._writingStyles[label] = parseInt(slider.value);
        var row = slider.closest('.wizard-pct-row');
        if (row) row.querySelector('.wizard-pct-val').textContent = slider.value + '%';
        this._updateStyleTags();
    },

    _continueWriting() {
        // Find novel with most chapters
        API.listNovels().then(function(r) {
            if (!r.success || !r.novels.length) { App.toast('没有小说项目', 'warning'); return; }
            var best = r.novels[0];
            r.novels.forEach(function(n) { if ((n.total_chapters||0) > (best.total_chapters||0)) best = n; });
            if (best.last_chapter) {
                App.navigate('writing', {novel: best.name, chapter: best.last_chapter});
            } else {
                App.navigate('writing', {novel: best.name});
            }
        });
    },

    _updateStyleTags() {
        var tags = document.getElementById('wStyleTags');
        if (!tags) return;
        var ws = this._writingStyles || {};
        var parts = [];
        Object.keys(ws).forEach(function(k) { parts.push(k + ' ' + ws[k] + '%'); });
        var btn = document.getElementById('wStyleBtn');
        if (btn) btn.textContent = parts.length > 0 ? '🎨 已选 ' + parts.length + ' 种风格' : '🎨 选择风格';
        tags.innerHTML = parts.length > 0
            ? parts.map(function(p) { return '<span class="wizard-tag">' + p + '</span>'; }).join('')
            : '';
    },

    _getWritingStyleStr() {
        var ws = this._writingStyles || {};
        var parts = [];
        Object.keys(ws).forEach(function(k) { parts.push(k + ' ' + ws[k] + '%'); });
        return parts.join(', ');
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
            style: App._getWritingStyleStr(),
            instructions: document.getElementById('wInstructions').value,
            temperature: parseFloat(document.getElementById('wTemperature').value),
            max_tokens: parseInt(document.getElementById('wMaxTokens').value),
        };
        if (!data.chapter_num) { this.toast('请填写章节编号', 'warning'); return; }

        const rd = document.getElementById('wResult');
        const novelName = document.querySelector('#wNovel option:checked')?.textContent || novel;

        // Always show rich progress card
        rd.innerHTML = '<div class="card"><h3>✍️ 正在生成 ' + data.volume + ' 第' + data.chapter_num + '章</h3>' +
            '<div class="text-secondary mt-8" style="font-size:12px">📖 ' + novelName + '</div>' +
            (data.style ? '<div class="text-muted mt-4" style="font-size:11px">🎨 ' + data.style + '</div>' : '') +
            '<div class="stream-indicator mt-12"><div class="stream-dot"></div><span id="streamStatus">准备中...</span></div>' +
            '<div class="stream-output mt-12" id="streamOut"></div></div>';

        // Always use streaming for live progress, auto-save when done
        await this._streamChapter(novel, data, rd, true); // true = auto save
    },

    async _streamChapter(novel, data, rd, autoSave) {
        const out = document.getElementById('streamOut');
        if (!out) { rd.innerHTML = '<div class="code-block error">渲染失败，请重试</div>'; return; }
        out.innerHTML = '<span class="streaming-cursor"></span>';
        const statusEl = document.getElementById('streamStatus');
        let full = '', wordCount = 0, startTime = Date.now();
        const abortCtrl = new AbortController();
        this.streamAbort = abortCtrl;

        // Elapsed time updater
        var timerInterval = setInterval(function() {
            var elapsed = Math.floor((Date.now() - startTime) / 1000);
            var mins = Math.floor(elapsed / 60), secs = elapsed % 60;
            if (statusEl && !statusEl.textContent.startsWith('✅') && !statusEl.textContent.startsWith('❌')) {
                statusEl.textContent = '生成中 · ' + mins + '分' + (secs < 10 ? '0' : '') + secs + '秒 · ' + wordCount + '字';
            }
        }, 1000);

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
                            if (d.type === 'token') {
                                full += d.content;
                                wordCount = (full.match(/[\u4e00-\u9fff]/g) || []).length + (full.match(/[a-zA-Z]+/g) || []).length;
                                out.innerHTML = this.renderMarkdown(full) + '<span class="streaming-cursor"></span>';
                                out.scrollTop = out.scrollHeight;
                            }
                            else if (d.type === 'done') {
                                clearInterval(timerInterval);
                                out.querySelector('.streaming-cursor')?.remove();
                                if (statusEl) statusEl.textContent = '✅ 完成 · ' + wordCount + '字';
                                if (autoSave) {
                                    const padded = data.chapter_num.padStart(4, '0');
                                    const chRef = data.volume + '/ch-' + padded;
                                    API.editChapter(novel, chRef, full).then(function(saveResp) {
                                        if (saveResp.success) App.toast('✅ 第 ' + data.chapter_num + ' 章已保存 (' + wordCount + '字)', 'success');
                                    });
                                    // Auto-advance chapter number for next generation
                                    var chInput = document.getElementById('wChapterNum');
                                    if (chInput) chInput.value = parseInt(data.chapter_num) + 1;
                                    var instrInput = document.getElementById('wInstructions');
                                    if (instrInput) instrInput.value = '';
                                    rd.insertAdjacentHTML('beforeend',
                                        '<div class="mt-16 flex gap-8">' +
                                        '<button class="btn btn-primary" onclick="App.navigate(\'review\',{novel:\'' + novel + '\',chapter:\'' + data.volume + '/ch-' + padded + '\'})">🔍 审稿</button>' +
                                        '<button class="btn btn-secondary" onclick="App._genChapter(false)">➡️ 继续写下一章</button>' +
                                        '</div>');
                                    // Auto-review if checkbox checked
                                    if (document.getElementById('wAutoReview')?.checked) {
                                        setTimeout(function() { App._autoReviewOptimize(novel, data.volume, data.chapter_num, chRef); }, 1500);
                                    }
                                } else {
                                    rd.insertAdjacentHTML('beforeend',
                                        '<div id="streamSave" class="mt-8 flex gap-8">' +
                                        '<button class="btn btn-primary" onclick="App._saveStreamedChapter(\'' + novel + '\',\'' + data.volume + '\',\'' + data.chapter_num + '\')">💾 保存章节</button>' +
                                        '<button class="btn btn-secondary" onclick="this.closest(\'.card\').remove()">关闭</button></div>');
                                }
                                App._streamedContent = full;
                            }
                            else if (d.type === 'error') {
                                clearInterval(timerInterval);
                                if (statusEl) statusEl.textContent = '❌ ' + d.error;
                                out.innerHTML = '<div class="code-block error">' + d.error + '</div>';
                            }
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
        return `你是一个专业的长篇网文写作Agent。请输出完整的章节正文，以"# 章节标题"开头。\\n\\n写作约束：\\n- 每章不少于2500字，不使用真实地名人名\\n- **禁止**"不是...而是..."句式（≤1次）、禁止连续简单判断句\\n- 对话用动作自然衔接，禁止"XX说：+对话"的生硬格式\\n- show don't tell，关键情节用场景呈现\\n- 段落2-3句以上，对话占比30-50%\\n- 必须有悬念/钩子结尾\\n卷：${data.volume}\\n章节：第 ${data.chapter_num} 章\\n${data.style ? '风格：' + data.style : ''}\\n${data.instructions ? '指示：' + data.instructions : ''}`;
    },

    async _saveStreamedChapter(novel, volume, chNum) {
        const content = App._streamedContent;
        if (!content) { this.toast('无内容可保存', 'warning'); return; }
        const padded = chNum.padStart(4, '0');
        const resp = await API.editChapter(novel, `${volume}/ch-${padded}`, content);
        resp.success ? this.toast(`✅ 第 ${chNum} 章已保存`, 'success') : this.toast(resp.error, 'error');
    },

    _optimizeFromReviewStored() {
        var rc = App._reviewContext;
        if (!rc) { App.toast('审稿上下文丢失，请重新审稿', 'warning'); return; }
        App._optimizeFromReview(rc.novel, rc.chRef, rc.volume, rc.chNum);
    },

    _optimizeFromReview(novel, chRef, volume, chNum) {
        var rd = document.getElementById('rResult');
        var notice = document.createElement('div');
        notice.className = 'stream-indicator mt-12';
        notice.innerHTML = '<div class="stream-dot"></div><span>🛠️ 正在优化章节...</span>';
        rd.appendChild(notice);
        var aiReview = rd.querySelector('.reader-content')?.textContent || '';
        var scriptOut = '';
        ['analyze','compliance','forbidden'].forEach(function(k) {
            var el = rd.querySelector('details .code-block');
            if (el) scriptOut += el.textContent + '\n';
        });
        API.optimizeChapter(novel, {chapter_ref: chRef, volume: volume, chapter_num: chNum, review_text: aiReview, script_issues: scriptOut}).then(function(optResp) {
            if (optResp.success) {
                API.editChapter(novel, chRef, optResp.content).then(function() {
                    notice.innerHTML = '<span style="color:var(--success)">✅ 已保存 (' + (optResp.word_count||0) + '字)</span> · <span class="stream-dot"></span> 正在复审...';
                    // Auto re-review
                    API.reviewChapter(novel, {chapter_ref: chRef, volume: volume, chapter_num: chNum}).then(function(reRev) {
                        if (reRev.success) {
                            var issues = [];
                            if (!reRev.script_results.analyze.success) issues.push('字数/结构');
                            if (!reRev.script_results.compliance.success) issues.push('合规');
                            if (!reRev.script_results.forbidden.success) issues.push('禁用模式');
                            if (issues.length === 0) {
                                notice.innerHTML = '<span style="color:var(--success)">✅ 优化完成 · 复审全部通过</span>';
                            } else {
                                notice.innerHTML = '<span style="color:var(--warning)">⚠️ 优化完成 · 复审仍有问题: ' + issues.join(', ') + '</span>';
                            }
                        } else {
                            notice.innerHTML = '<span style="color:var(--warning)">⚠️ 优化完成 · 复审失败</span>';
                        }
                        App.toast('✅ 优化+复审完成', 'success');
                    });
                });
            } else {
                notice.innerHTML = '<span style="color:var(--danger)">❌ 优化失败: ' + (optResp.error||'') + '</span>';
            }
        });
    },

    _autoReviewOptimize(novel, volume, chNum, chRef) {
        var rd = document.getElementById('wResult');
        var notice = document.createElement('div');
        notice.className = 'card';
        notice.style.cssText = 'border-color:var(--info);margin-top:16px';
        notice.innerHTML = '<div class="stream-indicator"><div class="stream-dot"></div><span>🔍 自动审稿优化中...</span></div>';
        rd.appendChild(notice);

        var parts = chRef.split('/');
        var chapterNum = parts[1].replace('ch-', '');
        API.reviewChapter(novel, {chapter_ref: chRef.replace('.md',''), volume: volume, chapter_num: chapterNum}).then(function(revResp) {
            if (!revResp.success) { notice.innerHTML = '<div class="code-block error">审稿失败: ' + (revResp.error||'') + '</div>'; return; }
            notice.innerHTML = '<div class="stream-indicator"><div class="stream-dot"></div><span>🛠️ 根据审稿意见优化章节...</span></div>';
            var scriptIssues = (revResp.script_results?.analyze?.stdout||'') + '\\n' + (revResp.script_results?.compliance?.stdout||'') + '\\n' + (revResp.script_results?.forbidden?.stdout||'');
            API.optimizeChapter(novel, {chapter_ref: chRef.replace('.md',''), volume: volume, chapter_num: chapterNum, review_text: revResp.ai_review||'', script_issues: scriptIssues}).then(function(optResp) {
                if (optResp.success) {
                    API.editChapter(novel, chRef.replace('.md',''), optResp.content).then(function() {
                        var wc = optResp.word_count || 0;
                        // Auto re-review
                        API.reviewChapter(novel, {chapter_ref: chRef.replace('.md',''), volume: volume, chapter_num: chapterNum}).then(function(reRev) {
                            var allPass = reRev.success && reRev.script_results.analyze.success && reRev.script_results.compliance.success && reRev.script_results.forbidden.success;
                            notice.innerHTML = '<div style="color:' + (allPass ? 'var(--success)' : 'var(--warning)') + '"><strong>' + (allPass ? '✅' : '⚠️') + ' 已优化并复审</strong> (' + wc + '字)' + (allPass ? ' · 全部通过' : ' · 仍有问题') + '</div>' +
                                '<details class="mt-8"><summary style="cursor:pointer;color:var(--accent);font-size:12px">📋 查看详情</summary><div class="code-block info mt-4" style="max-height:200px;overflow-y:auto">' + (revResp.ai_review||'') + '</div></details>';
                        });
                    });
                } else {
                    notice.innerHTML = '<div class="code-block error">优化失败: ' + (optResp.error||'') + '</div>';
                }
            });
        });
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
                style: App._getWritingStyleStr(),
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
        const parts = chRef.split('/');
        const novelName = document.querySelector('#rNovel option:checked')?.textContent || novel;
        // Store context for optimize button
        App._reviewContext = {novel: novel, chRef: chRef, volume: parts[0], chNum: parts[1].replace('ch-', '')};
        const startTime = Date.now();

        // Rich progress card
        rd.innerHTML = '<div class="card">' +
            '<h3>🔍 正在审稿: ' + chRef + '</h3>' +
            '<div class="text-secondary mt-8" style="font-size:12px">📖 ' + novelName + '</div>' +
            '<div class="mt-12">' +
            '<div class="review-progress-item" id="rpScript"><div class="review-progress-dot"></div><span>📊 运行脚本检查（字数/结构 · 合规性 · 禁用模式）</span></div>' +
            '<div class="review-progress-item" id="rpAI" style="opacity:0.4"><div class="review-progress-dot idle"></div><span>🤖 AI 深度审稿分析</span></div>' +
            '</div>' +
            '<div class="stream-indicator mt-12"><div class="stream-dot"></div><span id="reviewStatus">已开始...</span></div>' +
            '<div id="reviewDetail" class="mt-12"></div>' +
            '</div>';

        // Elapsed timer
        var timerInterval = setInterval(function() {
            var elapsed = Math.floor((Date.now() - startTime) / 1000);
            var mins = Math.floor(elapsed / 60), secs = elapsed % 60;
            var el = document.getElementById('reviewStatus');
            if (el && !el.textContent.startsWith('✅') && !el.textContent.startsWith('❌')) {
                el.textContent = '审稿中 · ' + mins + '分' + (secs < 10 ? '0' : '') + secs + '秒';
            }
        }, 1000);

        // Show script stage as active after brief delay
        setTimeout(function() {
            var rp = document.getElementById('rpScript');
            if (rp) rp.querySelector('.review-progress-dot').classList.add('active');
        }, 500);

        const resp = await API.reviewChapter(novel, { chapter_ref: chRef.replace('.md',''), volume: parts[0], chapter_num: parts[1].replace('ch-','') });

        clearInterval(timerInterval);

        if (resp.success) {
            // Mark stages complete
            var rpS = document.getElementById('rpScript');
            if (rpS) { rpS.style.opacity = '1'; var d = rpS.querySelector('.review-progress-dot'); d.className = 'review-progress-dot done'; d.textContent = '✅'; }
            var rpA = document.getElementById('rpAI');
            if (rpA) { rpA.style.opacity = '1'; var d2 = rpA.querySelector('.review-progress-dot'); d2.className = 'review-progress-dot done'; d2.textContent = '✅'; }
            var st = document.getElementById('reviewStatus');
            if (st) st.textContent = '✅ 审稿完成 · ' + (resp.word_count || 0) + '字';

            // Script results summary
            var analyzeOk = resp.script_results.analyze.success;
            var compOk = resp.script_results.compliance.success;
            var forbidOk = resp.script_results.forbidden.success;
            var scriptSummary = '<div class="grid-3 mt-12" style="grid-template-columns:repeat(3,1fr)">' +
                '<div class="stat-card"><div class="stat-value">' + (analyzeOk ? '✅' : '❌') + '</div><div class="stat-label">字数/结构</div></div>' +
                '<div class="stat-card"><div class="stat-value">' + (compOk ? '✅' : '❌') + '</div><div class="stat-label">合规检查</div></div>' +
                '<div class="stat-card"><div class="stat-value">' + (forbidOk ? '✅' : '❌') + '</div><div class="stat-label">禁用模式</div></div></div>';

            // AI review in reader-content
            var aiReviewHtml = resp.ai_review
                ? '<div class="mt-16"><div class="reader-content" style="max-height:40vh;overflow-y:auto;padding:16px;background:var(--bg-elevated);border-radius:var(--radius-lg)">' + this.renderMarkdown(resp.ai_review) + '</div></div>'
                : '';

            // Script detail toggle
            var scriptDetailHtml = '<details class="mt-12"><summary style="cursor:pointer;color:var(--accent);font-size:13px">📊 查看脚本详细输出</summary>' +
                '<div class="code-block mt-8" style="max-height:300px;overflow-y:auto">' +
                ['analyze','compliance','forbidden'].map(function(k) {
                    return '<strong>=== ' + k + ' ===</strong>\n' + (resp.script_results[k].stdout || '(无输出)');
                }).join('\n\n') +
                '</div></details>';

            document.getElementById('reviewDetail').innerHTML = scriptSummary + aiReviewHtml + scriptDetailHtml +
                '<div class="mt-16 flex gap-8"><button class="btn btn-success" onclick="App._optimizeFromReviewStored()">🛠️ 一键优化并替换</button></div>';
            this.toast('✅ 审稿完成', 'success');
        } else {
            var st2 = document.getElementById('reviewStatus');
            if (st2) st2.textContent = '❌ 审稿失败';
            document.getElementById('reviewDetail').innerHTML = '<div class="code-block error mt-8">' + resp.error + '</div>';
            this.toast(resp.error, 'error');
        }
    },

    // ═══════════════════════════════════════════════════════════════════
    //  CHAPTER BROWSER
    // ═══════════════════════════════════════════════════════════════════

    async _renderChapters(mc, params) {
        mc.innerHTML = `<div class="page-header"><div><h1 class="page-title">📖 章节浏览</h1><p class="page-subtitle">阅读、编辑、审稿</p></div></div><div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="cNovel" onchange="App._loadChapters()"><option value="">-- 请选择 --</option></select></div><div class="form-group"><label class="form-label">搜索</label><input class="form-input" id="cSearch" placeholder="章节号或卷号..." oninput="App._filterChapters()"></div></div><div id="cList" class="mt-16"></div></div>`;
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

    _filterChapters() {
        var q = (document.getElementById('cSearch')?.value || '').toLowerCase();
        document.querySelectorAll('#cList .volume-header, #cList .chapter-item').forEach(function(el) {
            if (!q) { el.style.display = ''; return; }
            var txt = el.textContent.toLowerCase();
            if (el.classList.contains('volume-header')) {
                // Show volume header if any chapter inside matches
                var next = el.nextElementSibling;
                var found = false;
                while (next && !next.classList.contains('volume-header')) {
                    if (next.textContent.toLowerCase().includes(q)) found = true;
                    next = next.nextElementSibling;
                }
                el.style.display = found ? '' : 'none';
            } else {
                el.style.display = txt.includes(q) ? '' : 'none';
            }
        });
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
        // Load previews for outline cards
        var outlineCards = (n.outline_files||[]).map(function(f) {
            var vol = f.replace('-chapters.md','');
            return '<div class="outline-card" onclick="App._openOutlineEdit(\'' + name + '\',\'' + vol + '\')"><div class="outline-vol">📐 ' + vol + '</div><div class="outline-preview" id="ocPrev_' + vol + '">加载中...</div></div>';
        }).join('');
        list.innerHTML = '<div class="outline-grid">' + outlineCards + '</div>';
        // Load previews async
        (n.outline_files||[]).forEach(function(f) {
            var vol = f.replace('-chapters.md','');
            API.readOutline(name, vol).then(function(r) {
                var el = document.getElementById('ocPrev_' + vol);
                if (el && r.success) {
                    var lines = r.content.split('\n').filter(function(l) { return l.trim() && !l.startsWith('#'); });
                    el.textContent = lines.slice(0, 3).join(' · ').substring(0, 100) || '(空大纲)';
                } else if (el) { el.textContent = '(空大纲)'; }
            });
        });
    },

    async _openOutlineEdit(novel, vol) {
        const resp = await API.readOutline(novel, vol);
        const content = resp.success ? resp.content : '# ' + vol + ' 大纲\n\n(新大纲)\n';

        // Load novel for chapter list
        const novelResp = await API.getNovel(novel);
        var chapters = [];
        if (novelResp.success && novelResp.novel.volumes) {
            var v = novelResp.novel.volumes.find(function(x) { return x.name === vol; });
            if (v) chapters = v.chapters || [];
        }

        var nextChNum = chapters.length > 0 ? (parseInt(chapters[chapters.length-1].name.replace('ch-','')) + 1) : 1;
        var genBtn = '<div class="mt-12 flex gap-8"><button class="btn btn-sm btn-success" onclick="App._aiGenerateChapterOutlines(\'' + novel + '\',\'' + vol + '\', ' + nextChNum + ', 5)">🤖 生成后5章危机/关卡</button></div>';
        var chListHtml = chapters.length > 0
            ? '<div class="chapter-list" style="max-height:50vh">' + chapters.map(function(ch) {
                var wb = ch.words >= 2500 ? 'good' : ch.words >= 1500 ? 'warn' : 'low';
                return '<div class="chapter-item" onclick="App._openChapterReader(\'' + novel + '\',\'' + vol + '/' + ch.name + '\')\" style="cursor:pointer"><span class="ch-num">' + ch.name + '</span><span class="ch-meta"><span class="word-badge ' + wb + '">' + ch.words + '字</span></span><div class="ch-actions"><button class="btn btn-sm btn-primary" onclick="event.stopPropagation();App._editChapterModal(\'' + novel + '\',\'' + vol + '/' + ch.name + '\')\" style="font-size:11px;padding:2px 8px">✏️</button></div></div>';
            }).join('') + '</div>'
            : '<div class="empty-state"><div class="empty-state-icon">📄</div><div class="empty-state-title">暂无章节</div></div>';

        var volNum = vol.replace('vol-', '');
        var body = '' +
            '<div class="tab-bar" style="margin-bottom:12px">' +
            '<span class="tab-item active" data-t="outline" onclick="App._switchOulineTab(this,\'outline\')">📐 卷纲骨架</span>' +
            '<span class="tab-item" data-t="chapters" onclick="App._switchOulineTab(this,\'chapters\')">📖 章节列表 (' + chapters.length + ')</span>' +
            '<span class="tab-item" data-t="edit" onclick="App._switchOulineTab(this,\'edit\')">✏️ 编辑</span>' +
            '</div>' +
            '<div id="oultineTabContent">' +
            '<div class="reader-content" id="outlineViewer" style="max-height:55vh">' + this.renderMarkdown(content) + '</div>' +
            '<div id="outlineEditor" style="display:none"><textarea class="form-textarea" id="outlineEdit" style="min-height:400px;font-family:var(--font-mono);font-size:13px">' + content.replace(/</g, '&lt;').replace(/&/g, '&amp;') + '</textarea></div>' +
            '</div>';

        var nextVol = 'vol-' + String(parseInt(volNum) + 1).padStart(2, '0');
        var footer = '' +
            '<button class="btn btn-primary" onclick="App._saveOutline(\'' + novel + '\',\'' + vol + '\')">💾 保存</button>' +
            '<button class="btn btn-success" onclick="App._aiGenerateOutline(\'' + novel + '\',\'' + vol + '\')">🤖 AI 生成本卷大纲</button>' +
            '<button class="btn btn-secondary" onclick="App._aiGenerateOutline(\'' + novel + '\',\'' + nextVol + '\')">📐 AI 生成下一卷大纲</button>' +
            '<button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">关闭</button>';
        var modal = this.modal('📐 ' + vol, body, footer, '800px');
        modal._novel = novel; modal._vol = vol; modal._content = content;
        modal._chHtml = chListHtml;
        modal._renderedOutline = App.renderMarkdown(content);
    },

    _switchOulineTab(tab, t) {
        var modal = tab.closest('.modal');
        modal.querySelectorAll('.tab-item').forEach(function(x) { x.classList.remove('active'); });
        tab.classList.add('active');
        var container = modal.querySelector('#oultineTabContent');
        if (t === 'outline') {
            container.innerHTML = '<div class="reader-content" style="max-height:55vh">' + (modal._renderedOutline || App.renderMarkdown(modal._content || '')) + '</div>';
        } else if (t === 'chapters') {
            container.innerHTML = modal._chHtml;
        } else if (t === 'edit') {
            container.innerHTML = '<textarea class="form-textarea" id="outlineEdit" style="min-height:400px;font-family:var(--font-mono);font-size:13px">' + (modal._content||'').replace(/</g, '&lt;').replace(/&/g, '&amp;') + '</textarea>';
        }
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

    async _aiGenerateChapterOutlines(novel, vol, startCh, count) {
        var modal = document.querySelector('.modal');
        var notice = document.createElement('div');
        notice.className = 'stream-indicator mt-8';
        notice.innerHTML = '<div class="stream-dot"></div><span>🤖 AI 正在生成第 ' + startCh + '-' + (startCh+count-1) + ' 章坎/关卡...</span>';
        modal.querySelector('.modal-body').appendChild(notice);

        var novelResp = await API.getNovel(novel);
        var genre = novelResp.success ? (novelResp.novel.genre_bible_content || '') : '';
        var outlineResp = await API.readOutline(novel, vol);
        var outline = outlineResp.success ? outlineResp.content : '';
        var chapters = [];
        for (var i = startCh; i < startCh + count; i++) {
            var ch = 'ch-' + String(i).padStart(4, '0');
            try {
                var chResp = await API.readChapter(novel, vol + '/' + ch);
                if (chResp.success) chapters.push({num: i, content: chResp.content.substring(0, 500)});
            } catch(e) {}
        }

        var chContext = chapters.map(function(c){ return '第' + c.num + '章预览：' + c.content; }).join('\n');
        var resp = await fetch('/api/ai/chat', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                messages: [{role:'user', content: '请为后续 ' + count + ' 章生成危机关卡。\n卷纲：' + outline.substring(0, 2000) + '\n最近章节：' + chContext + '\n\n每章输出一个危机，格式：## ch-XXXX\n**危机描述**: ...\n**关键冲突**: ...\n**读者钩子**: ...'}],system: '你是一个网文编辑。为每章设计危机关卡。返回markdown格式。',
                temperature: 0.8, max_tokens: 2048,
            })
        }).then(function(r){return r.json();});

        if (resp.success) {
            // Save each chapter's danger_issue
            var lines = resp.content.split('\n');
            var currentCh = '', currentBody = [];
            for (var j = 0; j < lines.length; j++) {
                var m = lines[j].match(/^##\s*ch-(\d+)/i);
                if (m) {
                    if (currentCh && currentBody.length > 0) {
                        var chPadded = String(parseInt(currentCh)).padStart(4, '0');
                        API.writeFile(novel, 'outline/danger_issue_' + vol + '/danger_issue_' + chPadded + '.md', currentBody.join('\n'));
                    }
                    currentCh = m[1]; currentBody = [lines[j]];
                } else if (currentCh) {
                    currentBody.push(lines[j]);
                }
            }
            if (currentCh && currentBody.length > 0) {
                var chPadded = String(parseInt(currentCh)).padStart(4, '0');
                API.writeFile(novel, 'outline/danger_issue_' + vol + '/danger_issue_' + chPadded + '.md', currentBody.join('\n'));
            }
            notice.innerHTML = '<span style="color:var(--success)">✅ ' + count + ' 章坎已生成</span>';
            App.toast('✅ 危机关卡已生成', 'success');
        } else {
            notice.innerHTML = '<span style="color:var(--danger)">❌ ' + (resp.error||'失败') + '</span>';
        }
    },

    async _aiGenerateOutline(novel, vol) {
        var modal = document.querySelector('.modal');
        var notice = document.createElement('div');
        notice.className = 'stream-indicator mt-8';
        notice.innerHTML = '<div class="stream-dot"></div><span>🤖 AI 正在生成 ' + vol + ' 大纲...</span>';
        modal.querySelector('.modal-body').appendChild(notice);

        // Get novel context
        var novelResp = await API.getNovel(novel);
        var genre = novelResp.success ? (novelResp.novel.genre_bible_content || '') : '';
        var chars = novelResp.success ? (novelResp.novel.characters_content || '') : '';
        var prevOutlines = '';
        var volNum = parseInt(vol.replace('vol-', ''));
        // Load previous volume outline for context
        if (volNum > 1) {
            var prevVol = 'vol-' + String(volNum - 1).padStart(2, '0');
            try {
                var prevResp = await API.readOutline(novel, prevVol);
                if (prevResp.success) prevOutlines = prevResp.content;
            } catch(e) {}
        }

        var resp = await fetch('/api/ai/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                messages: [{role:'user', content: '请为小说生成 ' + vol + ' 的详细章纲。\\n\\n类型设定：' + genre.substring(0, 2000) + '\\n人物档案：' + chars.substring(0, 1000) + '\\n上一卷大纲：' + prevOutlines.substring(0, 1500) + '\\n\\n请生成完整的卷纲，包含每章的章纲标题和简要内容描述。格式为markdown。'}],
                system: '你是一个专业的网文编辑。请生成详细的卷纲，包含每章标题和简要内容描述。',
                temperature: 0.7, max_tokens: 4096,
            })
        }).then(function(r){return r.json();});

        if (resp.success) {
            // Save the outline
            await API.editOutline(novel, vol, resp.content);
            // Update modal content
            modal._content = resp.content;
            modal._renderedOutline = App.renderMarkdown(resp.content);
            notice.innerHTML = '<span style="color:var(--success)">✅ 大纲已生成并保存</span>';
            // Refresh the outline view
            var container = modal.querySelector('#oultineTabContent');
            if (container) container.innerHTML = '<div class="reader-content" style="max-height:55vh">' + modal._renderedOutline + '</div>';
            App.toast('✅ ' + vol + ' 大纲已生成', 'success');
        } else {
            notice.innerHTML = '<span style="color:var(--danger)">❌ 生成失败: ' + (resp.error||'') + '</span>';
        }
    },

    async _saveOutline(novel, vol) {
        const content = document.getElementById('outlineEdit').value;
        const resp = await API.editOutline(novel, vol, content);
        resp.success ? (this.toast('✅ 大纲已保存', 'success'), document.querySelectorAll('.modal-overlay').forEach(m => m.remove()), this._loadOutlines()) : this.toast(resp.error, 'error');
    },

    // ═══════════════════════════════════════════════════════════════════
    //  QUALITY REPORT
    // ═══════════════════════════════════════════════════════════════════

    async _renderQuality(mc) {
        mc.innerHTML = '<div class="page-header"><div><h1 class="page-title">📈 质量报告</h1><p class="page-subtitle">写作质量趋势 · 审稿通过率 · 问题分布</p></div></div>' +
            '<div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="qNovel" onchange="App._loadQuality()"><option value="">-- 请选择 --</option></select></div></div><div id="qContent" class="mt-16"></div></div>';
        var resp = await API.listNovels();
        if (resp.success) {
            var sel = document.getElementById('qNovel');
            resp.novels.forEach(function(n) { var o = document.createElement('option'); o.value = n.name; o.textContent = n.title||n.name; sel.appendChild(o); });
        }
    },

    async _loadQuality() {
        var novel = document.getElementById('qNovel')?.value;
        if (!novel) return;
        var ct = document.getElementById('qContent');
        ct.innerHTML = '<div class="loading"><div class="spinner"></div><span>加载报告...</span></div>';
        var resp = await fetch('/api/content/quality-report/' + encodeURIComponent(novel)).then(function(r){return r.json();});
        if (!resp.success) { ct.innerHTML = '<div class="code-block error">' + (resp.error||'') + '</div>'; return; }
        var r = resp.report;

        var html = '<div class="stats-grid">' +
            '<div class="stat-card"><div class="stat-value">' + r.total_chapters + '</div><div class="stat-label">总章节</div></div>' +
            '<div class="stat-card"><div class="stat-value">' + (r.total_words/10000).toFixed(1) + '万</div><div class="stat-label">总字数</div></div>' +
            '<div class="stat-card"><div class="stat-value">' + r.review_stats.total + '</div><div class="stat-label">审稿次数</div></div>' +
            '<div class="stat-card"><div class="stat-value">' + r.review_stats.wc_pass_rate + '%</div><div class="stat-label">字数达标率</div></div>' +
            '</div>';

        // Review pass rate bars
        html += '<div class="grid-2 mt-16"><div class="card"><h3 class="card-title">📊 审稿通过率</h3>' +
            '<div class="mt-8"><div class="progress-label"><span>字数达标</span><span>' + r.review_stats.wc_pass_rate + '%</span></div><div class="progress-bar"><div class="progress-bar-fill ' + (r.review_stats.wc_pass_rate>=80?'success':'warning') + '" style="width:' + r.review_stats.wc_pass_rate + '%"></div></div></div>' +
            '<div class="mt-8"><div class="progress-label"><span>合规检查</span><span>' + r.review_stats.compliance_pass_rate + '%</span></div><div class="progress-bar"><div class="progress-bar-fill ' + (r.review_stats.compliance_pass_rate>=80?'success':'warning') + '" style="width:' + r.review_stats.compliance_pass_rate + '%"></div></div></div>' +
            '<div class="mt-8"><div class="progress-label"><span>禁用模式</span><span>' + r.review_stats.forbidden_pass_rate + '%</span></div><div class="progress-bar"><div class="progress-bar-fill ' + (r.review_stats.forbidden_pass_rate>=80?'success':'warning') + '" style="width:' + r.review_stats.forbidden_pass_rate + '%"></div></div></div>' +
            '</div>';

        // Writing quality metrics
        html += '<div class="card"><h3 class="card-title">✍️ 写作质量</h3>' +
            '<div class="stats-grid mt-8" style="grid-template-columns:repeat(3,1fr)">' +
            '<div class="stat-card"><div class="stat-value">' + r.writing_quality.avg_binary_contrast + '</div><div class="stat-label">平均二元对照/章</div></div>' +
            '<div class="stat-card"><div class="stat-value">' + r.writing_quality.avg_tell_patterns + '</div><div class="stat-label">平均 XX说：/章</div></div>' +
            '<div class="stat-card"><div class="stat-value">' + r.writing_quality.total_judgment_groups + '</div><div class="stat-label">累计判断句组</div></div>' +
            '</div></div></div>';

        // Chapter word count trend (simple text list)
        if (r.chapter_trend && r.chapter_trend.length > 0) {
            html += '<div class="card mt-16"><h3 class="card-title">📈 最近章节字数趋势</h3><div class="mt-8" style="max-height:200px;overflow-y:auto">';
            r.chapter_trend.forEach(function(ch) {
                var wb = ch.wc >= 2500 ? 'success' : 'warning';
                var barW = Math.min(100, ch.wc / 40);
                html += '<div class="chapter-item"><span class="ch-num">' + ch.ref + '</span><div style="flex:1;margin:0 12px"><div class="progress-bar"><div class="progress-bar-fill ' + wb + '" style="width:' + barW + '%"></div></div></div><span class="ch-meta">' + ch.wc + '字</span></div>';
            });
            html += '</div></div>';
        }

        ct.innerHTML = html;
    },

    // ═══════════════════════════════════════════════════════════════════
    //  FULL-TEXT SEARCH
    // ═══════════════════════════════════════════════════════════════════

    async _renderSearch(mc) {
        mc.innerHTML = '<div class="page-header"><div><h1 class="page-title">🔎 全文搜索</h1><p class="page-subtitle">搜索章节、大纲、审稿记录 · FTS5 全文索引</p></div></div>' +
            '<div class="card"><div class="form-row"><div class="form-group" style="flex:1"><input class="form-input wizard-input-lg" id="sQuery" placeholder="输入关键词搜索...（如：李闲 突破 元婴）" onkeydown="if(event.key===\'Enter\')App._doSearch()"></div>' +
            '<div class="form-group"><select class="form-select" id="sNovel"><option value="">全部小说</option></select></div>' +
            '<button class="btn btn-primary btn-lg" onclick="App._doSearch()">🔍 搜索</button></div>' +
            '<div id="sResults" class="mt-16"></div></div>';

        // Load novels
        var resp = await API.listNovels();
        if (resp.success) {
            var sel = document.getElementById('sNovel');
            resp.novels.forEach(function(n) {
                var o = document.createElement('option'); o.value = n.name; o.textContent = n.title || n.name; sel.appendChild(o);
            });
        }
    },

    async _doSearch() {
        var q = document.getElementById('sQuery')?.value.trim();
        if (!q) { this.toast('请输入搜索关键词', 'warning'); return; }
        var novel = document.getElementById('sNovel')?.value || '';
        var rd = document.getElementById('sResults');
        rd.innerHTML = '<div class="loading"><div class="spinner"></div><span>搜索中...</span></div>';

        var params = 'q=' + encodeURIComponent(q) + '&limit=30';
        if (novel) params += '&novel=' + encodeURIComponent(novel);
        var resp = await fetch('/api/content/search?' + params).then(function(r){return r.json();});

        if (!resp.success) { rd.innerHTML = '<div class="code-block error">' + (resp.error||'') + '</div>'; return; }

        var r = resp.results;
        var total = (r.chapters||[]).length + (r.outlines||[]).length + (r.reviews||[]).length;
        var html = '<div class="text-secondary mb-12">找到 <strong>' + total + '</strong> 条结果</div>';

        // Chapters
        if (r.chapters && r.chapters.length > 0) {
            html += '<h3 class="mt-16 mb-8">📖 章节 (' + r.chapters.length + ')</h3>';
            r.chapters.forEach(function(ch) {
                html += '<div class="chapter-item" onclick="App._openChapterReader(\'' + ch.novel_name + '\',\'' + ch.chapter_ref + '\')" style="cursor:pointer"><span class="ch-num">' + ch.chapter_ref + '</span><span class="ch-title"><strong>' + (ch.title||'') + '</strong><br><span style="font-size:12px;color:var(--text-secondary)">' + (ch.snippet||'') + '</span></span><span class="ch-meta">' + (ch.word_count||0) + '字 · ' + ch.novel_name + '</span></div>';
            });
        }

        // Outlines
        if (r.outlines && r.outlines.length > 0) {
            html += '<h3 class="mt-16 mb-8">📐 大纲 (' + r.outlines.length + ')</h3>';
            r.outlines.forEach(function(o) {
                html += '<div class="chapter-item"><span class="ch-num">' + o.volume + '</span><span class="ch-title"><span style="font-size:12px;color:var(--text-secondary)">' + (o.snippet||'') + '</span></span><span class="ch-meta">' + o.novel_name + '</span></div>';
            });
        }

        // Reviews
        if (r.reviews && r.reviews.length > 0) {
            html += '<h3 class="mt-16 mb-8">🔍 审稿 (' + r.reviews.length + ')</h3>';
            r.reviews.forEach(function(rv) {
                html += '<div class="chapter-item"><span class="ch-num">' + rv.chapter_ref + '</span><span class="ch-title"><span style="font-size:12px;color:var(--text-secondary)">' + (rv.snippet||'') + '</span></span><span class="ch-meta">' + rv.novel_name + '</span></div>';
            });
        }

        if (total === 0) html += '<div class="empty-state"><div class="empty-state-icon">🔍</div><div class="empty-state-title">未找到结果</div></div>';
        rd.innerHTML = html;
    },
    // ═══════════════════════════════════════════════════════════════════
    //  CONFIG MANAGEMENT
    // ═══════════════════════════════════════════════════════════════════

    async _renderConfig(mc) {
        mc.innerHTML = '<div class="page-header"><div><h1 class="page-title">🛠️ 配置管理</h1><p class="page-subtitle">禁用词 · 合规规则 · 别名 · 风格预设</p></div></div>' +
            '<div class="tab-bar" id="cfgTabs">' +
            '<span class="tab-item active" data-t="banned" onclick="App._switchCfgTab(this,\'banned\')">🚫 禁用词</span>' +
            '<span class="tab-item" data-t="rules" onclick="App._switchCfgTab(this,\'rules\')">📋 合规规则</span>' +
            '<span class="tab-item" data-t="alias" onclick="App._switchCfgTab(this,\'alias\')">📝 别名表</span>' +
            '<span class="tab-item" data-t="styles" onclick="App._switchCfgTab(this,\'styles\')">🎨 风格预设</span>' +
            '</div>' +
            '<div id="cfgContent"></div>';
        this._loadCfgTab('banned');
    },

    async _switchCfgTab(el, tab) {
        document.querySelectorAll('#cfgTabs .tab-item').forEach(function(t) { t.classList.remove('active'); });
        el.classList.add('active');
        this._loadCfgTab(tab);
    },

    async _loadCfgTab(tab) {
        var tables = {banned:'banned_words', rules:'compliance_rules', alias:'alias_registry', styles:'style_presets'};
        var table = tables[tab];
        if (!table) return;
        var ct = document.getElementById('cfgContent');
        ct.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        var resp = await fetch('/api/config-db/' + table).then(function(r) { return r.json(); });
        if (!resp.success) { ct.innerHTML = '<div class="code-block error">' + (resp.error||'') + '</div>'; return; }

        var rows = resp.rows || [];
        var html = '';

        if (tab === 'banned') {
            html = '<div class="card"><div class="form-row mb-12"><input class="form-input" id="cfgNewWord" placeholder="禁用词"><input class="form-input" id="cfgNewCat" placeholder="分类（国家/城市/产品）"><input class="form-input" id="cfgNewRep" placeholder="替换词"><select class="form-select" id="cfgNewSev"><option value="error">error</option><option value="warn">warn</option></select><button class="btn btn-primary btn-sm" onclick="App._cfgAdd(\'banned\')">+ 添加</button></div>' +
                '<div>' + rows.map(function(r) {
                    return '<div class="chapter-item"><span class="ch-num">' + (r.severity==='error'?'🔴':'🟡') + '</span><span class="ch-title"><strong>' + r.word + '</strong> → ' + (r.replacement||'(无)') + '</span><span class="ch-meta">' + (r.category||'') + '</span><button class="btn btn-sm btn-secondary" onclick="App._cfgDel(\'banned\',' + r.id + ')" style="font-size:11px;padding:2px 8px">🗑</button></div>';
                }).join('') + '</div></div>';
        } else if (tab === 'rules') {
            html = '<div class="card"><div class="form-row mb-12"><input class="form-input" id="cfgNewKey" placeholder="规则键"><input class="form-input" id="cfgNewVal" placeholder="规则值"><input class="form-input" id="cfgNewCat" placeholder="分类"><button class="btn btn-primary btn-sm" onclick="App._cfgAdd(\'rules\')">+ 添加</button></div>' +
                '<div>' + rows.map(function(r) {
                    return '<div class="chapter-item"><span class="ch-num">📋</span><span class="ch-title"><strong>' + r.rule_key + '</strong>: ' + r.rule_value + '</span><span class="ch-meta">' + (r.category||'') + '</span><button class="btn btn-sm btn-secondary" onclick="App._cfgDel(\'rules\',' + r.id + ')" style="font-size:11px;padding:2px 8px">🗑</button></div>';
                }).join('') + '</div></div>';
        } else if (tab === 'alias') {
            html = '<div class="card"><div class="form-row mb-12"><input class="form-input" id="cfgNewReal" placeholder="真实名称"><input class="form-input" id="cfgNewAlias" placeholder="别名"><input class="form-input" id="cfgNewCat" placeholder="分类"><button class="btn btn-primary btn-sm" onclick="App._cfgAdd(\'alias\')">+ 添加</button></div>' +
                '<div>' + rows.map(function(r) {
                    return '<div class="chapter-item"><span class="ch-num">📝</span><span class="ch-title"><strong>' + r.real_name + '</strong> → ' + r.alias + '</span><span class="ch-meta">' + (r.category||'') + '</span><button class="btn btn-sm btn-secondary" onclick="App._cfgDel(\'alias\',' + r.id + ')" style="font-size:11px;padding:2px 8px">🗑</button></div>';
                }).join('') + '</div></div>';
        } else if (tab === 'styles') {
            html = '<div class="card"><div class="form-row mb-12"><input class="form-input" id="cfgNewName" placeholder="风格名称"><input class="form-input" id="cfgNewDesc" placeholder="描述"><textarea class="form-textarea mt-8" id="cfgNewPrompt" rows="3" placeholder="风格提示词"></textarea><button class="btn btn-primary btn-sm mt-8" onclick="App._cfgAdd(\'styles\')">+ 添加</button></div>' +
                '<div>' + rows.map(function(r) {
                    return '<div class="chapter-item"><span class="ch-num">' + (r.is_active?'✅':'⏸') + '</span><span class="ch-title"><strong>' + r.name + '</strong>: ' + (r.description||'') + '</span><button class="btn btn-sm btn-secondary" onclick="App._cfgDel(\'styles\',' + r.id + ')" style="font-size:11px;padding:2px 8px">🗑</button></div>';
                }).join('') + '</div></div>';
        }
        ct.innerHTML = html;
    },

    async _cfgAdd(tab) {
        var tables = {banned:'banned_words', rules:'compliance_rules', alias:'alias_registry', styles:'style_presets'};
        var table = tables[tab];
        var body = {};
        if (tab === 'banned') {
            body = {word:document.getElementById('cfgNewWord')?.value, category:document.getElementById('cfgNewCat')?.value, replacement:document.getElementById('cfgNewRep')?.value, severity:document.getElementById('cfgNewSev')?.value};
        } else if (tab === 'rules') {
            body = {rule_key:document.getElementById('cfgNewKey')?.value, rule_value:document.getElementById('cfgNewVal')?.value, category:document.getElementById('cfgNewCat')?.value};
        } else if (tab === 'alias') {
            body = {real_name:document.getElementById('cfgNewReal')?.value, alias:document.getElementById('cfgNewAlias')?.value, category:document.getElementById('cfgNewCat')?.value};
        } else if (tab === 'styles') {
            body = {name:document.getElementById('cfgNewName')?.value, description:document.getElementById('cfgNewDesc')?.value, prompt:document.getElementById('cfgNewPrompt')?.value};
        }
        var resp = await fetch('/api/config-db/' + table, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}).then(function(r){return r.json();});
        if (resp.success) { this.toast('✅ 已添加', 'success'); this._loadCfgTab(tab); }
        else { this.toast(resp.error||'添加失败', 'error'); }
    },

    async _cfgDel(tab, id) {
        var tables = {banned:'banned_words', rules:'compliance_rules', alias:'alias_registry', styles:'style_presets'};
        var table = tables[tab];
        var resp = await fetch('/api/config-db/' + table + '/' + id, {method:'DELETE'}).then(function(r){return r.json();});
        if (resp.success) { this.toast('✅ 已删除', 'success'); this._loadCfgTab(tab); }
        else { this.toast(resp.error||'删除失败', 'error'); }
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
