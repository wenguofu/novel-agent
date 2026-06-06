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
        // Load novels list
        const resp = await API.listNovels();
        if (resp.success) {
            this.novels = resp.novels || [];
        }
        this._initNovelPagesCollapse();
        await this.navigate('dashboard');
    },

    // ── Novel Context ──
    setNovelContext(novelName) {
        this.currentNovel = novelName || null;
        const np = document.getElementById('novelPages');
        const label = document.getElementById('novelPagesLabel');
        if (this.currentNovel) {
            if (np) np.style.display = 'block';
            if (label) {
                var n = this.novels.find(function(x) { return x.name === novelName; });
                label.innerHTML = '📖 ' + (n ? (n.title || n.name) : novelName);
                label.style.color = 'var(--text-primary)';
                label.style.opacity = '1';
            }
        } else {
            if (np) np.style.display = 'none';
            if (label) {
                label.innerHTML = '📖 小说管理';
                label.style.color = '';
                label.style.opacity = '';
            }
        }
        // If on a novel-specific page, reload it
        const novelViews = ['writing','chapters','review','outlines','init-wizard',
            'characters','foreshadowing','workflow',
            'world-building','plot-arcs','pacing','revelation',
            'genre-rules','story-volumes','volume-plans','alias-names','project-meta','quality'];
        if (novelViews.includes(this.currentView)) {
            this.navigate(this.currentView);
        }
    },

    // ── Novel Pages Collapse ──
    toggleNovelPages() {
        const np = document.getElementById('novelPages');
        const btn = document.getElementById('novelPagesToggle');
        if (!np || !btn) return;
        const collapsed = np.classList.toggle('collapsed');
        btn.classList.toggle('collapsed', collapsed);
        localStorage.setItem('novelPagesCollapsed', collapsed ? '1' : '0');
    },

    _initNovelPagesCollapse() {
        const collapsed = localStorage.getItem('novelPagesCollapsed') === '1';
        if (collapsed) {
            const np = document.getElementById('novelPages');
            const btn = document.getElementById('novelPagesToggle');
            if (np) np.classList.add('collapsed');
            if (btn) btn.classList.add('collapsed');
        }
    },

    // Novel-safe getter: use context novel as fallback
    _getNovel(id) {
        const el = document.getElementById(id);
        return (el && el.value) || this.currentNovel || '';
    },

    // Auto-select context novel in a <select> and optionally trigger onchange
    _initNovelSelector(selectId, loadFn) {
        const sel = document.getElementById(selectId);
        if (!sel) return;
        if (this.currentNovel && this.novels.length > 0) {
            // Ensure context novel exists in options
            var exists = Array.from(sel.options).some(function(o) { return o.value === this.currentNovel; }.bind(this));
            if (!exists) {
                var n = this.novels.find(function(n) { return n.name === this.currentNovel; }.bind(this));
                if (n) {
                    var o = document.createElement('option');
                    o.value = n.name; o.textContent = n.title || n.name;
                    sel.appendChild(o);
                }
            }
            sel.value = this.currentNovel;
            if (loadFn) loadFn();
        }
    },

    async navigate(view, params = {}) {
        this.currentView = view;
        document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.view === view));
        const mc = document.getElementById('mainContent');

        // Guard: novel-specific views require a selected novel
        const novelViews = ['writing','chapters','review','outlines','init-wizard',
            'characters','foreshadowing','workflow',
            'world-building','plot-arcs','pacing','revelation',
            'genre-rules','story-volumes','volume-plans','alias-names','project-meta','quality'];
        if (novelViews.includes(view) && !this.currentNovel) {
            mc.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📖</div><div class="empty-state-title">请先选择小说</div><div class="empty-state-desc">在左侧边栏选择一本小说后，即可使用此功能</div></div>';
            return;
        }

        mc.innerHTML = '<div class="loading"><div class="spinner"></div><span>加载中...</span></div>';
        try {
            switch (view) {
                case 'dashboard': await this._renderDashboard(mc); break;
                case 'novels': await this._renderNovels(mc); break;
                case 'new-book': await this._renderNewBook(mc); break;
                case 'writing': await this._renderWriting(mc, params); break;
                case 'review': await this._renderReview(mc, params); break;
                case 'chapters': await this._renderChapters(mc, params); break;
                case 'init-wizard': await this._renderInitWizard(mc); break;
                case 'characters': await this._renderCharacters(mc); break;
                case 'foreshadowing': await this._renderForeshadowing(mc); break;
                case 'workflow': await this._renderWorkflow(mc); break;
                case 'outlines': await this._renderOutlines(mc); break;
                case 'quality': await this._renderQuality(mc); break;
                case 'search': await this._renderSearch(mc); break;
                case 'config': await this._renderConfig(mc); break;
                case 'settings': await this._renderSettings(mc); break;
                case 'world-building': await this._renderWorldBuilding(mc); break;
                case 'plot-arcs': await this._renderPlotArcs(mc); break;
                case 'pacing': await this._renderPacing(mc); break;
                case 'revelation': await this._renderRevelation(mc); break;
                case 'genre-rules': await this._renderGenreRules(mc); break;
                case 'story-volumes': await this._renderStoryVolumes(mc); break;
                case 'volume-plans': await this._renderVolumePlans(mc); break;
                case 'alias-names': await this._renderAliasNames(mc); break;
                case 'project-meta': await this._renderProjectMeta(mc); break;
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
        this.novels = novels;

        // ── Fetch the 3 new aggregate metrics in parallel ──
        // 架构计划 4.1：待审章节数 / 待优化章节数 / 本周新增字数
        // 与 listNovels 并行，失败时降级为 0（不阻塞主面板）。
        let pendingReview = 0, pendingOptimize = 0, wordsThisWeek = 0;
        try {
            const statsResp = await API.dashboardStats();
            if (statsResp.success && statsResp.stats) {
                pendingReview = statsResp.stats.pending_review || 0;
                pendingOptimize = statsResp.stats.pending_optimize || 0;
                wordsThisWeek = statsResp.stats.words_this_week || 0;
            }
        } catch (e) { /* graceful degradation */ }

        // ── If a novel is selected, show its dedicated dashboard ──
        if (this.currentNovel) {
            const nResp = await API.getNovel(this.currentNovel);
            const n = nResp.success ? nResp.novel : null;
            if (n) {
                const wPct = n.word_goal ? Math.min(100, Math.round((n.total_words || 0) / (parseInt(n.word_goal) * 10000) * 100)) : 0;
                const last = n.last_chapter ? `<span>最近: ${n.last_chapter} ${n.last_chapter_words ? '· ' + n.last_chapter_words + '字' : ''}</span>` : '';
                const volumes = n.volumes || [];
                const volList = volumes.slice(0, 5).map(v =>
                    `<div class="novel-card" style="padding:8px 12px;margin-bottom:4px"><span>📁 ${v.name}</span> <span style="color:var(--text-tertiary);font-size:12px">${v.chapter_count}章 · ${(v.total_words/10000).toFixed(1)}万字</span></div>`
                ).join('');
                const quickBtns = n.total_chapters > 0
                    ? `<button class="btn btn-sm btn-primary" onclick="App.navigate('writing',{novel:'${n.name}'})">✍️ 继续写作</button>
                       <button class="btn btn-sm btn-outline" onclick="App.navigate('chapters',{novel:'${n.name}'})">📖 章节浏览</button>
                       <button class="btn btn-sm btn-outline" onclick="App.navigate('review',{novel:'${n.name}'})">🔍 审稿</button>
                       <button class="btn btn-sm btn-outline" onclick="App._exportNovel('${n.name}','epub')">📗 EPUB</button>`
                    : '';

                mc.innerHTML = `
                    <div class="page-header">
                        <div><h1 class="page-title">📊 ${n.title || n.name}</h1><p class="page-subtitle">${n.summary ? n.summary.substring(0, 80) : 'AI 驱动的长篇网文写作工作台'}</p></div>
                        <div style="display:flex;gap:8px;align-items:center">
                            <button class="btn btn-sm btn-outline" onclick="App.setNovelContext(null);App.navigate('dashboard')">← 全部项目</button>
                            <button class="btn btn-primary" onclick="App.navigate('new-book')">✨ 创建新书</button>
                        </div>
                    </div>
                    <div class="stats-grid">
                        <div class="stat-card"><div class="stat-value">${n.total_chapters}</div><div class="stat-label">章节</div></div>
                        <div class="stat-card"><div class="stat-value">${(n.total_words/10000).toFixed(1)}万</div><div class="stat-label">字数</div></div>
                        <div class="stat-card"><div class="stat-value">${volumes.length}</div><div class="stat-label">卷数</div></div>
                        <div class="stat-card"><div class="stat-value">${n.review_count}</div><div class="stat-label">审稿</div></div>
                    </div>
                    ${wPct > 0 ? `<div class="card mt-12"><div class="progress-label"><span>写作进度</span><span>${wPct}%</span></div><div class="progress-bar"><div class="progress-bar-fill accent" style="width:${wPct}%"></div></div></div>` : ''}
                    ${last ? `<div class="card mt-12" style="padding:8px 12px;font-size:13px;color:var(--text-secondary)">${last}</div>` : ''}
                    ${quickBtns ? `<div class="mt-12" style="display:flex;gap:8px;flex-wrap:wrap">${quickBtns}</div>` : ''}
                    ${volList ? `<div class="card mt-12"><h3 class="card-title">📁 卷结构</h3>${volList}${volumes.length > 5 ? `<div style="color:var(--text-tertiary);font-size:12px;padding:4px 12px">... 还有 ${volumes.length - 5} 卷</div>` : ''}</div>` : ''}
                    <div class="card mt-16" style="border-top:1px solid var(--border-default);padding-top:12px">
                        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
                            <span style="font-size:13px;color:var(--text-secondary)">📖 当前小说：<strong style="color:var(--text-primary)">${n.title || n.name}</strong></span>
                            <select class="form-select" id="dashboardNovelSelect" onchange="App.setNovelContext(this.value);App.navigate('dashboard')" style="width:auto;min-width:160px;font-size:13px">
                                <option value="${n.name}" selected>${n.title || n.name} (当前)</option>
                                ${novels.filter(x => x.name !== n.name).map(x => `<option value="${x.name}">${x.title || x.name}</option>`).join('')}
                            </select>
                        </div>
                    </div>
                `;
                return;
            }
            // Fallback: novel not found, clear context
            this.currentNovel = null;
        }

        // ── Aggregate dashboard (no novel selected) ──
        const totalCh = novels.reduce((s, n) => s + (n.total_chapters || 0), 0);
        const totalW = novels.reduce((s, n) => s + (n.total_words || 0), 0);
        var bestNovel = novels[0];
        novels.forEach(function(n) { if ((n.total_chapters||0) > (bestNovel?.total_chapters||0)) bestNovel = n; });
        const totalR = novels.reduce((s, n) => s + (n.review_count || 0), 0);

        // Quality summary cards for dashboard
        let qualityCards = '';
        if (novels.length > 0) {
            var avgWords = totalCh > 0 ? Math.round(totalW / totalCh) : 0;
            var projectsWithReviews = novels.filter(function(n) { return (n.review_count || 0) > 0; }).length;
            qualityCards = '<div class="card mt-12"><h3 class="card-title">📈 质量概览</h3>' +
                '<div class="stats-grid" style="grid-template-columns:repeat(4,1fr)">' +
                '<div class="stat-card" style="padding:8px 12px"><div class="stat-value" style="font-size:18px">' + totalR + '</div><div class="stat-label" style="font-size:10px">审稿次数</div></div>' +
                '<div class="stat-card" style="padding:8px 12px"><div class="stat-value" style="font-size:18px">' + avgWords + '</div><div class="stat-label" style="font-size:10px">平均每章字数</div></div>' +
                '<div class="stat-card" style="padding:8px 12px"><div class="stat-value" style="font-size:18px">' + projectsWithReviews + '/' + novels.length + '</div><div class="stat-label" style="font-size:10px">已审稿项目</div></div>' +
                '<div class="stat-card" style="padding:8px 12px"><div class="stat-value" style="font-size:18px">' + (avgWords >= 2500 ? '✅' : '⚠️') + '</div><div class="stat-label" style="font-size:10px">字数达标</div></div>' +
                '</div></div>';
        }

        let novelCards = '';
        novels.forEach(n => {
            const last = n.last_chapter ? `<div style="font-size:11px;color:var(--text-tertiary)">最近: ${n.last_chapter} ${n.last_chapter_words ? '· ' + n.last_chapter_words + '字' : ''}</div>` : '';
            const wPct = n.word_goal ? Math.min(100, Math.round((n.total_words || 0) / (parseInt(n.word_goal) * 10000) * 100)) : 0;
            novelCards += `
                <div class="novel-card">
                    <div class="novel-card-title" onclick="App.setNovelContext('${n.name}');App.navigate('writing')" style="cursor:pointer">${n.title || n.name}</div>
                    <div class="novel-card-meta">
                        <span>📖 ${n.total_chapters}章</span>
                        <span>📝 ${(n.total_words / 10000).toFixed(1)}万字</span>
                        <span>🔍 ${n.review_count}审稿</span>
                    </div>
                    ${n.summary ? '<div class="novel-card-summary">' + n.summary + '</div>' : ''}
                    ${last}
                    ${wPct > 0 ? `<div class="mt-8"><div class="progress-label"><span>进度</span><span>${wPct}%</span></div><div class="progress-bar"><div class="progress-bar-fill accent" style="width:${wPct}%"></div></div></div>` : ''}
                    ${n.total_chapters > 0 ? `<div class="novel-card-actions" style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap">
                        <button class="btn btn-sm btn-outline" onclick="event.stopPropagation();App._exportNovel('${n.name}','epub')" title="导出EPUB">📗 EPUB</button>
                        <button class="btn btn-sm btn-outline" onclick="event.stopPropagation();App._exportNovel('${n.name}','txt')" title="导出TXT">📄 TXT</button>
                        <button class="btn btn-sm btn-outline" onclick="event.stopPropagation();App._exportNovel('${n.name}','html')" title="导出HTML">🌐 HTML</button>
                    </div>` : ''}
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
                <div class="stat-card"><div class="stat-value" style="color:${pendingReview > 0 ? 'var(--color-warning,#f59e0b)' : 'inherit'}">${pendingReview}</div><div class="stat-label">待审章节</div></div>
                <div class="stat-card"><div class="stat-value" style="color:${pendingOptimize > 0 ? 'var(--color-warning,#f59e0b)' : 'inherit'}">${pendingOptimize}</div><div class="stat-label">待优化</div></div>
                <div class="stat-card"><div class="stat-value">${(wordsThisWeek / 10000).toFixed(1)}万</div><div class="stat-label">本周新增</div></div>
                <div class="stat-card"><div class="stat-value">${this.config.deepseek_configured ? '✅' : '❌'}</div><div class="stat-label">AI状态</div></div>
            </div>
            ${novels.length > 0 ? `<div class="card mt-12 novel-picker-bar">
                <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
                    <span style="font-size:13px;color:var(--text-secondary);white-space:nowrap">📖 选择小说</span>
                    <select class="form-select" id="dashboardNovelSelect" onchange="App._selectDashboardNovel(this.value)" style="flex:1;min-width:180px;font-size:14px">
                        <option value="">-- 选择小说开始工作 --</option>
                        ${novels.map(x => `<option value="${x.name}">${x.title || x.name}${x.last_chapter ? ' · ' + x.last_chapter : ''}</option>`).join('')}
                    </select>
                    <button class="btn btn-primary btn-sm" onclick="App._continueWriting()" title="打开进度最多的小说">▶️ 继续写作</button>
                    <button class="btn btn-outline btn-sm" onclick="var s=document.getElementById('dashboardNovelSelect');if(s.value)App.setNovelContext(s.value);App.navigate('writing')">✍️ 写作台</button>
                    <button class="btn btn-outline btn-sm" onclick="var s=document.getElementById('dashboardNovelSelect');if(s.value)App.setNovelContext(s.value);App.navigate('chapters')">📖 浏览</button>
                    <button class="btn btn-outline btn-sm" onclick="App.navigate('settings')">⚙️ 设置</button>
                </div>
            </div>` : ''}
            ${qualityCards}
            <div class="card mt-16">
                <div class="card-header"><h2 class="card-title">📚 项目</h2><span class="text-sm text-secondary">${novels.length} 个项目</span></div>
                <div class="novel-grid">${novelCards || '<div class="empty-state"><div class="empty-state-icon">📖</div><div class="empty-state-title">还没有小说项目</div><div class="empty-state-desc">点击"创建新书"开始你的第一部作品</div></div>'}</div>
            </div>`
        `;
    },

    // ── Dashboard novel selector handler ──
    _selectDashboardNovel(name) {
        if (!name) return;
        this.setNovelContext(name);
        // Don't auto-navigate — user picks action via buttons
    },

    async _openNovelQuick(name) {
        const resp = await API.getNovel(name);
        if (!resp.success) { this.toast(resp.error, 'error'); return; }
        const n = resp.novel;
        var volsHtml = '<div class="empty-state"><div class="empty-state-icon">📄</div><div class="empty-state-title">暂无章节</div></div>';
        // Flatten chapters for the history tab's chapter selector. Each
        // entry is ``{ ref, label }`` where ref is "vol-XX/ch-XXX" (the
        // canonical manuscript path) and label is the display name.
        var chapterOptions = [];
        if (n.volumes) {
            volsHtml = n.volumes.map(function(v) {
                var chItems = v.chapters.map(function(ch) {
                    var wb = ch.words >= 2500 ? 'good' : ch.words >= 1500 ? 'warn' : 'low';
                    chapterOptions.push({ ref: v.name + '/' + ch.name, label: v.name + ' / ' + ch.name });
                    return '<div class="chapter-item"><span class="ch-num">' + ch.name + '</span><span class="ch-meta"><span class="word-badge ' + wb + '">' + ch.words + '字</span></span><div class="ch-actions"><button class="btn btn-sm btn-primary" onclick="App._readChapter(\'' + name + '\',\'' + v.name + '/' + ch.name + '\')">📖</button><button class="btn btn-sm btn-secondary" onclick="App.navigate(\'writing\',{novel:\'' + name + '\',chapter:\'' + v.name + '/' + ch.name + '\'})">✍️</button></div></div>';
                }).join('');
                return '<div class="volume-header">📁 ' + v.name + ' · ' + v.chapter_count + '章 · ' + (v.total_words / 10000).toFixed(1) + '万字</div>' + chItems;
            }).join('');
        }
        const vols = volsHtml;
        const wPct = n.word_goal ? Math.min(100, Math.round((n.total_words || 0) / (parseInt(n.word_goal) * 10000) * 100)) : 0;

        const body = `
            <div class="tab-bar"><span class="tab-item active" data-t="overview" onclick="App._switchQTab(this,'overview')">概览</span><span class="tab-item" data-t="chapters" onclick="App._switchQTab(this,'chapters')">章节 (${n.total_chapters})</span><span class="tab-item" data-t="files" onclick="App._switchQTab(this,'files')">文件</span><span class="tab-item" data-t="history" onclick="App._switchQTab(this,'history')">📜 历史</span></div>
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
        var bakDir = n.name ? 'manuscript/.bak' : '';
        const exportBtns = n.total_chapters > 0
            ? `<button class="btn btn-sm btn-outline" onclick="App._exportNovel('${n.name}','epub')">📗 EPUB</button><button class="btn btn-sm btn-outline" onclick="App._exportNovel('${n.name}','txt')">📄 TXT</button><button class="btn btn-sm btn-outline" onclick="App._exportNovel('${n.name}','html')">🌐 HTML</button>`
            : '';
        const footer = `<button class="btn btn-primary" onclick="App.navigate('writing',{novel:'${n.name}'})">✍️ 开始写作</button><button class="btn btn-success" onclick="App.navigate('chapters',{novel:'${n.name}'})">📖 浏览章节</button>${exportBtns}<button class="btn btn-outline" onclick="App._cleanupBak('${n.name}')" style="color:var(--danger)">🗑 清理备份</button><button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">关闭</button>`;

        const modalEl = this.modal(`📚 ${n.title || n.name}`, body, footer, '800px');
        modalEl._novel = n;
        modalEl._origOverview = document.getElementById('qkTabContent').innerHTML;
        modalEl._chaptersHtml = '<div class="chapter-list">' + vols + '</div>';
        modalEl._chapterOptions = chapterOptions;
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
        else if (t === 'history') {
            // 架构计划 1.1: list .bak files for a chosen chapter.
            // The user picks a chapter from the dropdown; the list
            // re-renders on every change. The current selection is
            // stored on the modal element so the tab is restorable.
            const opts = modal._chapterOptions || [];
            var sel = '<option value="">-- 选择章节 --</option>';
            opts.forEach(function(o) {
                sel += '<option value="' + o.ref + '">' + o.label + '</option>';
            });
            var initial = modal._historyChRef || (opts[0] ? opts[0].ref : '');
            content.innerHTML = '' +
                '<div class="form-row" style="align-items:flex-end">' +
                '<div class="form-group" style="flex:1">' +
                '<label class="form-label">章节</label>' +
                '<select class="form-select" id="historyChSel" onchange="App._loadHistoryTab()">' + sel + '</select>' +
                '</div>' +
                '<div class="form-group">' +
                '<button class="btn btn-secondary" onclick="App._loadHistoryTab()">🔄 刷新</button>' +
                '</div>' +
                '</div>' +
                '<div id="historyList" class="mt-12"><div class="empty-state"><div class="empty-state-icon">📜</div><div class="empty-state-title">选择章节后查看历史版本</div></div></div>';
            var selEl = document.getElementById('historyChSel');
            if (selEl && initial) selEl.value = initial;
            this._loadHistoryTab();
        }
    },

    // ── History tab helpers (架构计划 1.1) ──
    async _loadHistoryTab() {
        const selEl = document.getElementById('historyChSel');
        const listEl = document.getElementById('historyList');
        if (!selEl || !listEl) return;
        const chRef = selEl.value;
        // Stash the selection on the surrounding modal so re-entering
        // the tab restores it.
        const modal = selEl.closest('.modal');
        if (modal) modal._historyChRef = chRef;
        if (!chRef) {
            listEl.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📜</div><div class="empty-state-title">请先选择章节</div></div>';
            return;
        }
        const novel = (modal && modal._novel) ? modal._novel.name : this.currentNovel;
        if (!novel) {
            listEl.innerHTML = '<div class="code-block error">无法确定当前小说</div>';
            return;
        }
        listEl.innerHTML = '<div class="loading"><div class="spinner"></div><span>加载历史版本...</span></div>';
        const resp = await API.listChapterBak(novel, chRef);
        if (!resp.success) {
            listEl.innerHTML = '<div class="code-block error">' + (resp.error || '加载失败') + '</div>';
            return;
        }
        const files = resp.files || [];
        if (files.length === 0) {
            listEl.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📜</div><div class="empty-state-title">该章节暂无历史版本</div><div class="empty-state-desc">优化章节时会自动生成 .bak 备份</div></div>';
            return;
        }
        listEl.innerHTML = files.map(function(f) {
            const sizeKb = (f.size / 1024).toFixed(1);
            // Escape backticks/quotes in the preview before inlining
            // into the onclick handler below.
            const escPreview = (f.preview || '').replace(/`/g, '\\`').replace(/\\/g, '\\\\').replace(/\n/g, ' ');
            return '' +
                '<div class="card mt-8" style="padding:12px">' +
                '<div class="flex gap-8" style="align-items:center;justify-content:space-between">' +
                '<div style="flex:1">' +
                '<div><strong>📜 rev' + f.rev + '</strong> · <span class="text-sm text-secondary">' + f.modified_at + ' · ' + sizeKb + ' KB</span></div>' +
                '<div class="text-sm text-secondary mt-4" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:60vw">' + escPreview + '</div>' +
                '</div>' +
                '<div class="flex gap-8">' +
                '<button class="btn btn-sm btn-secondary" onclick="App._viewHistoryEntry(\'' + novel + '\',\'' + chRef + '\',\'' + f.filename + '\')">查看</button>' +
                '<button class="btn btn-sm btn-primary" onclick="App._restoreHistoryEntry(\'' + novel + '\',\'' + chRef + '\',\'' + f.filename + '\')">恢复</button>' +
                '<button class="btn btn-sm btn-outline" style="color:var(--danger)" onclick="App._deleteHistoryEntry(\'' + novel + '\',\'' + chRef + '\',\'' + f.filename + '\')">删除</button>' +
                '</div>' +
                '</div>' +
                '</div>';
        }).join('');
    },

    async _viewHistoryEntry(novel, chRef, filename) {
        const resp = await API.getChapterBak(novel, chRef, filename);
        if (!resp.success) { this.toast(resp.error || '加载失败', 'error'); return; }
        const body = '<div class="editor-container"><div class="editor-panel"><div class="editor-panel-header">📜 ' + filename + '（只读）</div><textarea class="editor-textarea" id="histView" style="font-size:12px" readonly>' + (resp.content || '').replace(/</g, '&lt;') + '</textarea></div></div>';
        const footer = '<button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">关闭</button>';
        this.modal('📜 ' + filename, body, footer, '90vw');
    },

    async _restoreHistoryEntry(novel, chRef, filename) {
        if (!confirm('确认将「' + filename + '」恢复为当前章节「' + chRef + '」？\n当前章节内容将被覆盖，且本次操作不会自动生成新的 .bak 备份。')) return;
        const resp = await API.restoreChapterBak(novel, chRef, filename);
        if (!resp.success) { this.toast(resp.error || '恢复失败', 'error'); return; }
        this.toast('✅ 已从 ' + filename + ' 恢复', 'success');
        // Re-render the list (in case the user wants to keep browsing)
        // and update the modal's overview numbers in the background.
        await this._loadHistoryTab();
        // Refresh the underlying novel data so the "概览" tab's
        // total_chapters/total_words stay in sync after a restore.
        const modal = document.querySelector('.modal');
        if (modal && modal._novel) {
            const nr = await API.getNovel(novel);
            if (nr.success) modal._novel = nr.novel;
        }
    },

    async _deleteHistoryEntry(novel, chRef, filename) {
        if (!confirm('确认删除备份「' + filename + '」？此操作不可撤销。')) return;
        const resp = await API.deleteChapterBak(novel, chRef, filename);
        if (!resp.success) { this.toast(resp.error || '删除失败', 'error'); return; }
        this.toast('🗑 已删除 ' + filename, 'success');
        await this._loadHistoryTab();
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

    // ── Export ──
    _exportNovel(novel, format) {
        const url = API.exportNovelUrl(novel, format);
        this.toast(`⏳ 正在导出 ${format.toUpperCase()}...`, 'info');
        // Trigger download by navigating to the URL
        const a = document.createElement('a');
        a.href = url;
        a.download = '';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => this.toast(`✅ ${format.toUpperCase()} 导出完成`, 'success'), 500);
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
            return `<div class="novel-card"><div class="novel-card-title" onclick="App.setNovelContext('${n.name}');App.navigate('writing')" style="cursor:pointer">${n.title || n.name}</div><div class="novel-card-meta"><span>📖 ${n.total_chapters}章</span><span>📝 ${(n.total_words/10000).toFixed(1)}万字</span><span>🔍 ${n.review_count}审稿</span></div>${n.summary ? '<div class="novel-card-summary">'+n.summary+'</div>' : ''}${wPct>0?`<div class="mt-8"><div class="progress-bar"><div class="progress-bar-fill accent" style="width:${wPct}%"></div></div><div class="text-xs text-muted mt-2">${wPct}%</div></div>`:''}${n.total_chapters>0?`<div class="novel-card-actions" style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap"><button class="btn btn-sm btn-outline" onclick="event.stopPropagation();App._exportNovel('${n.name}','epub')" title="导出EPUB">📗 EPUB</button><button class="btn btn-sm btn-outline" onclick="event.stopPropagation();App._exportNovel('${n.name}','txt')" title="导出TXT">📄 TXT</button><button class="btn btn-sm btn-outline" onclick="event.stopPropagation();App._exportNovel('${n.name}','html')" title="导出HTML">🌐 HTML</button></div>`:''}</div>`;
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
                        <!-- Workflow Enforcement Checks -->
                        <div class="mt-12">
                            <button class="btn btn-secondary btn-sm" onclick="App._preflightCheck()" id="preflightBtn">⚙️ 工作流门控检查</button>
                            <div id="preflightResult" class="mt-8" style="display:none"></div>
                        </div>
                    <div class="flex gap-8 mt-16">
                        <button class="btn btn-primary btn-lg" onclick="App._genChapter(false)">✍️ 生成单章（自动保存）</button>
                        <button class="btn btn-success btn-lg" onclick="App._genChapter(true)">⚡ 流式预览（手动保存）</button>
                        <button class="btn btn-secondary btn-lg" onclick="App._openBatchModal()">📦 批量续写</button>
                        <button class="btn btn-warning btn-lg" onclick="App._rewriteChapter()" style="background:var(--warning);color:#000">🔄 一键重写</button>
                        <button class="btn btn-lg" onclick="App._autoLoop()" id="autoLoopBtn" style="background:var(--accent);color:#fff">🔁 自动续写</button>
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

    async _preflightCheck() {
        const novel = document.getElementById('wNovel')?.value;
        const volume = document.getElementById('wVolume')?.value || 'vol-01';
        const chNum = document.getElementById('wChapterNum')?.value || '1';
        if (!novel) { this.toast('请选择小说', 'warning'); return; }
        const rd = document.getElementById('preflightResult');
        rd.style.display = 'block';
        rd.innerHTML = '<div class="loading"><div class="spinner sm"></div><span>正在运行门控检查...</span></div>';
        const btn = document.getElementById('preflightBtn');
        btn.disabled = true; btn.textContent = '⏳ 检查中...';
        try {
            const resp = await API.preflightCheck(novel, {volume, chapter_num: chNum});
            if (!resp.success) { rd.innerHTML = '<div class="code-block error">检查失败</div>'; btn.disabled = false; btn.textContent = '⚙️ 工作流门控检查'; return; }
            let html = '<div class="card"><h4>' + (resp.all_ok ? '✅ 所有门控通过' : '⚠️ 部分检查未通过') + '</h4><div class="mt-8" style="display:grid;gap:4px">';
            for (const [key, r] of Object.entries(resp.results)) {
                html += `<div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:13px">${r.ok ? '✅' : '⚠️'} <strong>${r.name}</strong> <span class="text-muted">${r.detail||''}</span></div>`;
            }
            html += '</div></div>';
            rd.innerHTML = html;
            if (!resp.all_ok) this.toast('有门控未通过，请检查大纲和前置条件', 'warning');
            else this.toast('所有门控通过，可以生成', 'success');
        } catch (e) { rd.innerHTML = '<div class="code-block error">' + e.message + '</div>'; }
        btn.disabled = false; btn.textContent = '🔄 重新检查';
    },

    async _genChapter(stream = false) {
        const wNovelEl = document.getElementById('wNovel');
        if (!wNovelEl) { this.toast('页面元素缺失，请刷新', 'error'); return; }
        const novel = wNovelEl.value;
        if (!novel) { this.toast('请选择小说', 'warning'); return; }
        const getVal = function(id, def) { var el = document.getElementById(id); return el ? el.value : def; };
        const data = {
            volume: getVal('wVolume', 'vol-01'),
            chapter_num: getVal('wChapterNum', ''),
            style: App._getWritingStyleStr(),
            instructions: getVal('wInstructions', ''),
            temperature: parseFloat(getVal('wTemperature', '0.8')),
            max_tokens: parseInt(getVal('wMaxTokens', '8192')),
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
            const systemPrompt = await this._buildSystemPrompt(novel, data);
            const resp = await fetch('/api/ai/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages: [{"role": "user", "content": `请创作 ${data.volume} 第 ${data.chapter_num} 章`}],
                    system: systemPrompt,
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
                                // v3: Show context token usage if available
                                if (App._lastContextTokens) statusEl.textContent += ' · 上下文' + App._lastContextTokens + 'tok';
                                if (autoSave) {
                                    const padded = data.chapter_num.padStart(4, '0');
                                    const chRef = data.volume + '/ch-' + padded;
                                    API.editChapter(novel, chRef, full).then(function(saveResp) {
                                        if (saveResp.success) {
                                            App.toast('✅ 第 ' + data.chapter_num + ' 章已保存 (' + wordCount + '字)', 'success');
                                            // Post-flight enforcement
                                            API.postflightCheck(novel, {chapter_ref: chRef}).then(function(pf) {
                                                if (pf.success && !pf.all_ok) {
                                                    var issues = Object.values(pf.results).filter(function(r) { return !r.ok; });
                                                    if (issues.length) App.toast('⚠️ ' + issues.length + ' 项后置检查未通过', 'warning');
                                                }
                                            });
                                        }
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

    async _buildSystemPrompt(novel, data) {
        // v3: Use server-side context builder (replaces old file-loading approach)
        try {
            var volNum = data.volume ? parseInt(data.volume.replace('vol-', '')) : 1;
            var chNum = parseInt(data.chapter_num) || 1;
            var resp = await API.contextBuild({
                novel: novel,
                volume: volNum,
                chapter_num: chNum,
                style: App._getWritingStyleStr(),
                instructions: document.getElementById('wInstructions')?.value || data.instructions || '',
                max_tokens: 10000,
            });
            if (resp.success) {
                App._lastContextTokens = resp.total_tokens || 0;
                return resp.system_prompt || '';
            }
        } catch(e) {
            console.warn('Context builder failed, using fallback:', e);
        }
        // Fallback: minimal prompt
        return '你是一个专业的长篇网文写作Agent。请输出章节正文，以\"# 章节标题\"开头。\\n\\n当前卷：' + data.volume + ' 第 ' + data.chapter_num + ' 章\\n';
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
        // M5.2 T5: the server now saves the optimized content and runs
        // the post-review inline. The response carries pre_review /
        // post_review / diff (default mode), so we no longer call
        // API.editChapter or a second API.reviewChapter here.
        var rd = document.getElementById('rResult');
        var notice = document.createElement('div');
        notice.className = 'stream-indicator mt-12';
        notice.innerHTML = '<div class="stream-dot"></div><span>🛠️ 正在优化章节并复审...</span>';
        rd.appendChild(notice);
        var aiReview = rd.querySelector('.reader-content')?.textContent || '';
        var scriptOut = '';
        ['analyze','compliance','forbidden'].forEach(function(k) {
            var el = rd.querySelector('details .code-block');
            if (el) scriptOut += el.textContent + '\n';
        });
        API.optimizeChapter(novel, {chapter_ref: chRef, volume: volume, chapter_num: chNum, review_text: aiReview, script_issues: scriptOut}).then(function(optResp) {
            if (!optResp.success) {
                // post-review failed but optimize succeeded → 200 with success:false + pre_review only
                if (optResp.pre_review || optResp.post_review_ref) {
                    notice.innerHTML = '<span style="color:var(--warning)">⚠️ 优化完成 · 复审失败: ' + (optResp.error||'') + '</span>';
                } else {
                    notice.innerHTML = '<span style="color:var(--danger)">❌ 优化失败: ' + (optResp.error||'') + '</span>';
                }
                return;
            }
            var wc = optResp.word_count || 0;
            // Preview mode: the server did not save and did not re-review.
            if (optResp.preview) {
                notice.innerHTML = '<span style="color:var(--info)">👁️ 预览模式 (' + wc + '字) · 文件未保存，未执行复审</span>';
                App.toast('✅ 预览生成完成', 'success');
                return;
            }
            // Default mode: consume optResp.diff / optResp.post_review.
            // The server has already saved the file and persisted both
            // the pre-review and post-rev{N} rows.
            if (!optResp.post_review || optResp.post_review.success === false) {
                notice.innerHTML = '<span style="color:var(--warning)">⚠️ 优化完成 (' + wc + '字) · 复审未执行</span>';
                App.toast('优化已保存，但复审未完成', 'warning');
                return;
            }
            var diff = optResp.diff || {};
            var allPass = !!diff.all_pass;
            var verdictHtml = '<span style="color:' + (allPass ? 'var(--success)' : 'var(--warning)') + '">' +
                (allPass ? '✅' : '⚠️') + ' 优化完成 (' + wc + '字) · ' +
                (allPass ? '复审全部通过' : '复审仍有问题: ' + App._summarizeDiffIssues(diff)) + '</span>' +
                App._renderDiffPanel(diff);
            if (!allPass) {
                verdictHtml += '<div class="mt-8"><button class="btn btn-sm btn-primary" onclick="App._reOptimize()">🔧 继续优化</button><button class="btn btn-sm btn-success" onclick="App.toast(\'已接受当前版本\', \'success\')">✔️ 接受</button></div>';
                App._reOptimizeCtx = {novel:novel, chRef:chRef, volume:volume, chNum:chNum};
            }
            notice.innerHTML = verdictHtml;
            App.toast('✅ 优化+复审完成', 'success');
        });
    },

    _autoReviewOptimize(novel, volume, chNum, chRef) {
        // M5.2 T5: the first reviewChapter call stays — its output is
        // fed into the optimize prompt as review_text / script_issues.
        // After optimizeChapter the server has already saved the file
        // and persisted the post-review row, so we drop the redundant
        // API.editChapter and the second API.reviewChapter calls.
        var rd = document.getElementById('wResult');
        var notice = document.createElement('div');
        notice.className = 'card';
        notice.style.cssText = 'border-color:var(--info);margin-top:16px';
        notice.innerHTML = '<div class="stream-indicator"><div class="stream-dot"></div><span>🔍 自动审稿优化中...</span></div>';
        rd.appendChild(notice);

        var parts = chRef.split('/');
        var chapterNum = parts[1].replace('ch-', '');
        var refClean = chRef.replace('.md','');
        API.reviewChapter(novel, {chapter_ref: refClean, volume: volume, chapter_num: chapterNum}).then(function(revResp) {
            if (!revResp.success) { notice.innerHTML = '<div class="code-block error">审稿失败: ' + (revResp.error||'') + '</div>'; return; }
            notice.innerHTML = '<div class="stream-indicator"><div class="stream-dot"></div><span>🛠️ 根据审稿意见优化并复审中...</span></div>';
            var scriptIssues = (revResp.script_results?.analyze?.stdout||'') + '\\n' + (revResp.script_results?.compliance?.stdout||'') + '\\n' + (revResp.script_results?.forbidden?.stdout||'');
            API.optimizeChapter(novel, {chapter_ref: refClean, volume: volume, chapter_num: chapterNum, review_text: revResp.ai_review||'', script_issues: scriptIssues}).then(function(optResp) {
                if (!optResp.success) {
                    // Server returned success:false. Could be optimize-fail or post-review-fail.
                    if (optResp.pre_review || optResp.post_review_ref) {
                        notice.innerHTML = '<div class="code-block warning">⚠️ 优化已保存，复审失败: ' + (optResp.error||'') + '</div>';
                    } else {
                        notice.innerHTML = '<div class="code-block error">优化失败: ' + (optResp.error||'') + '</div>';
                    }
                    return;
                }
                var wc = optResp.word_count || 0;
                App._autoReviewCtx = {novel:novel, volume:volume, chNum:chNum, chRef:chRef};
                if (optResp.preview) {
                    notice.innerHTML = '<div style="color:var(--info)"><strong>👁️ 预览生成完成</strong> (' + wc + '字) · 文件未保存，未执行复审</div>';
                    return;
                }
                if (!optResp.post_review || optResp.post_review.success === false) {
                    notice.innerHTML = '<div style="color:var(--warning)"><strong>⚠️ 已优化 (' + wc + '字) · 复审未执行</strong></div>' +
                        '<details class="mt-8"><summary style="cursor:pointer;color:var(--accent);font-size:12px">📋 查看初始审稿</summary><div class="code-block info mt-4" style="max-height:200px;overflow-y:auto">' + (revResp.ai_review||'') + '</div></details>';
                    return;
                }
                var diff = optResp.diff || {};
                var allPass = !!diff.all_pass;
                var issuesStr = allPass ? '' : ' · 仍有问题: ' + App._summarizeDiffIssues(diff);
                notice.innerHTML = '<div style="color:' + (allPass ? 'var(--success)' : 'var(--warning)') + '"><strong>' + (allPass ? '✅' : '⚠️') + ' 已优化并复审</strong> (' + wc + '字)' + (allPass ? ' · 全部通过' : issuesStr) + '</div>' +
                    App._renderDiffPanel(diff) +
                    (allPass ? '' : '<div class="mt-8 flex gap-8"><button class="btn btn-sm btn-primary" onclick="App._continueAutoOptimize()">🔧 继续优化</button><button class="btn btn-sm btn-success" onclick="App._acceptChapter()">✔️ 接受</button></div>') +
                    '<details class="mt-8"><summary style="cursor:pointer;color:var(--accent);font-size:12px">📋 查看详情</summary><div class="code-block info mt-4" style="max-height:200px;overflow-y:auto">' + (revResp.ai_review||'') + '</div></details>';
            });
        });
    },

    _continueAutoOptimize() {
        var rc = App._autoReviewCtx;
        if (!rc) { App.toast('上下文丢失，请重新生成', 'warning'); return; }
        App._autoReviewOptimize(rc.novel, rc.volume, rc.chNum, rc.chRef);
    },

    _acceptChapter() {
        App.toast('✔️ 已接受当前版本', 'success');
        var cards = document.querySelectorAll('#wResult .card');
        for (var i = cards.length-1; i >= 0; i--) { if (cards[i].style.borderColor === 'var(--info)') cards[i].style.display = 'none'; }
    },

    _reOptimize() {
        var rc = App._reOptimizeCtx;
        if (!rc) { App.toast('优化上下文丢失，请重新审稿', 'warning'); return; }
        App._optimizeFromReview(rc.novel, rc.chRef, rc.volume, rc.chNum);
    },

    // M5.2 T5: build a short comma-separated label of which post-review
    // checks are still failing. Used in the verdict line when
    // diff.all_pass is false.
    _summarizeDiffIssues(diff) {
        if (!diff) return '';
        var labels = [];
        var pair = function(k) { return Array.isArray(diff[k]) ? diff[k] : [null, null]; };
        if (pair('wc_ok')[1] === false) labels.push('字数/结构');
        if (pair('compliance_ok')[1] === false) labels.push('合规');
        if (pair('forbidden_ok')[1] === false) labels.push('禁用模式');
        return labels.join(', ') || '未知';
    },

    // M5.2 T5: render the pre→post diff as a compact table so the user
    // can see which checks flipped from ❌ to ✅ (or stayed put). The
    // diff block from the server has the shape:
    //   {wc_ok:[bool,bool], compliance_ok:[bool,bool],
    //    forbidden_ok:[bool,bool], bcontrast_count:[int,int],
    //    tell_count:[int,int], all_pass:bool}
    _renderDiffPanel(diff) {
        if (!diff) return '';
        var icon = function(v) {
            if (v === true) return '<span style="color:var(--success)">✅</span>';
            if (v === false) return '<span style="color:var(--danger)">❌</span>';
            return '<span style="color:var(--text-muted)">—</span>';
        };
        var arrow = function(pre, post) {
            if (pre === post) return '<span style="color:var(--text-muted)">→</span>';
            return '<span style="color:var(--accent)">→</span>';
        };
        var row = function(label, pair, render) {
            render = render || icon;
            var pre = pair ? pair[0] : null;
            var post = pair ? pair[1] : null;
            return '<tr><td style="padding:2px 8px">' + label + '</td>' +
                '<td style="padding:2px 8px;text-align:center">' + render(pre) + '</td>' +
                '<td style="padding:2px 8px;text-align:center">' + arrow(pre, post) + '</td>' +
                '<td style="padding:2px 8px;text-align:center">' + render(post) + '</td></tr>';
        };
        var num = function(v) { return typeof v === 'number' ? String(v) : '—'; };
        return '<details class="mt-8" open><summary style="cursor:pointer;color:var(--accent);font-size:12px">📊 复审对比 (pre → post)</summary>' +
            '<table class="mt-4" style="font-size:12px;border-collapse:collapse"><thead><tr style="color:var(--text-muted)">' +
            '<th style="padding:2px 8px;text-align:left">项</th><th style="padding:2px 8px">pre</th><th></th><th style="padding:2px 8px">post</th></tr></thead><tbody>' +
            row('字数/结构', diff.wc_ok) +
            row('合规', diff.compliance_ok) +
            row('禁用模式', diff.forbidden_ok) +
            row('binary_contrast', diff.bcontrast_count, num) +
            row('tell_count', diff.tell_count, num) +
            '</tbody></table></details>';
    },

    async _rewriteChapter() {
        const novel = document.getElementById('wNovel')?.value;
        const volume = document.getElementById('wVolume')?.value || 'vol-01';
        const chNum = document.getElementById('wChapterNum')?.value;
        if (!novel) { this.toast('请选择小说', 'warning'); return; }
        if (!chNum) { this.toast('请填写章节编号', 'warning'); return; }
        const padded = String(chNum).padStart(4, '0');
        const chRef = volume + '/ch-' + padded;

        // Read existing chapter first
        const rd = document.getElementById('wResult');
        rd.innerHTML = '<div class="card" style="border-color:var(--warning)"><h3>🔄 正在重写 ' + chRef + '</h3>' +
            '<div class="stream-indicator mt-8"><div class="stream-dot"></div><span>📖 读取原章节...</span></div></div>';

        const chResp = await API.readChapter(novel, chRef);
        if (!chResp.success || !chResp.content) {
            rd.innerHTML = '<div class="code-block error">无法读取章节: ' + (chResp.error||'章节为空') + '</div>';
            return;
        }
        var originalText = chResp.content;

        // Run review to get AI feedback
        var notice = document.querySelector('#wResult .stream-indicator span');
        if (notice) notice.textContent = '🔍 审稿分析中...';
        const revResp = await API.reviewChapter(novel, {chapter_ref: chRef, volume: volume, chapter_num: chNum});
        var reviewText = revResp.success ? (revResp.ai_review || '') : '';
        var scriptIssues = '';
        if (revResp.success && revResp.script_results) {
            var sr = revResp.script_results;
            if (!sr.analyze.success) scriptIssues += '字数/结构问题: ' + (sr.analyze.stdout||'').substring(0, 300) + '\n';
            if (!sr.compliance.success) scriptIssues += '合规问题: ' + (sr.compliance.stdout||'').substring(0, 300) + '\n';
            if (!sr.forbidden.success) scriptIssues += '禁用模式: ' + (sr.forbidden.stdout||'').substring(0, 300) + '\n';
        }

        // Show review summary then start rewrite
        var reviewSummary = '';
        if (reviewText) reviewSummary += '## AI审稿意见\n' + reviewText.substring(0, 1500) + '\n';
        if (scriptIssues) reviewSummary += '## 脚本检测问题\n' + scriptIssues + '\n';

        if (!reviewSummary) {
            rd.innerHTML = '<div class="code-block warning">未获取到审稿意见，使用通用优化指令重写</div>';
            reviewSummary = '请优化本章，提升文笔质量，确保字数达标，修复可能的写作问题。';
        }

        // Stream the rewrite
        rd.innerHTML = '<div class="card" style="border-color:var(--warning)"><h3>🔄 重写 ' + chRef + '</h3>' +
            '<div class="text-muted mt-4" style="font-size:12px">基于最新审稿建议重写</div>' +
            '<div class="stream-indicator mt-8"><div class="stream-dot"></div><span id="rwStatus">准备中...</span></div>' +
            '<div class="stream-output mt-8" id="rwOut"></div></div>';

        var out = document.getElementById('rwOut');
        var statusEl = document.getElementById('rwStatus');
        var full = '', wordCount = 0, startTime = Date.now();
        var timerInterval = setInterval(function() {
            var elapsed = Math.floor((Date.now()-startTime)/1000);
            var mins = Math.floor(elapsed/60), secs = elapsed%60;
            if (statusEl) statusEl.textContent = '重写中 · ' + mins + '分' + (secs<10?'0':'')+secs+'秒 · '+wordCount+'字';
        }, 1000);

        var systemPrompt = await this._buildSystemPrompt(novel, {volume:volume, chapter_num:chNum, style:App._getWritingStyleStr(), instructions:''});
        systemPrompt += '\n\n## 🔄 重写模式\n你正在重写章节 ' + chRef + '。请根据以下审稿意见彻底重写，解决所有问题，保持情节方向不变但质量更高。\n\n' +
            reviewSummary + '\n\n## 原文参考（保持情节但提升质量）\n' + originalText.substring(0, 2000) + '\n';

        try {
            var abortCtrl = new AbortController();
            this.streamAbort = abortCtrl;
            var resp = await fetch('/api/ai/stream', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({
                    messages: [{role:'user', content:'请重写' + chRef + '，基于审稿意见彻底改进'}],
                    system: systemPrompt, temperature: 0.7, max_tokens: 8192,
                }), signal: abortCtrl.signal,
            });
            var reader = resp.body.getReader();
            var decoder = new TextDecoder();
            var buf = '';
            while (true) {
                var r = await reader.read();
                if (r.done) break;
                buf += decoder.decode(r.value, {stream:true});
                var lines = buf.split('\n');
                buf = lines.pop()||'';
                for (var li=0; li<lines.length; li++) {
                    var line = lines[li];
                    if (line.startsWith('data: ')) {
                        try {
                            var d = JSON.parse(line.slice(6));
                            if (d.type === 'token') {
                                full += d.content;
                                wordCount = (full.match(/[\u4e00-\u9fff]/g)||[]).length;
                                out.innerHTML = App.renderMarkdown(full) + '<span class="streaming-cursor"></span>';
                                out.scrollTop = out.scrollHeight;
                            } else if (d.type === 'done') {
                                clearInterval(timerInterval);
                                out.querySelector('.streaming-cursor')?.remove();
                                if (statusEl) statusEl.textContent = '✅ 重写完成 · ' + wordCount + '字';
                                API.editChapter(novel, chRef, full).then(function(s) {
                                    if (s.success) App.toast('✅ 第' + chNum + '章已重写并保存 (' + wordCount + '字)', 'success');
                                });
                                rd.insertAdjacentHTML('beforeend',
                                    '<div class="mt-12 flex gap-8"><button class="btn btn-primary" onclick="App.navigate(\'review\',{novel:\''+novel+'\',chapter:\''+chRef+'\'})">🔍 审稿验证</button>'+
                                    '<button class="btn btn-secondary" onclick="App._rewriteChapter()">🔄 再次重写</button></div>');
                            } else if (d.type === 'error') {
                                clearInterval(timerInterval);
                                if (statusEl) statusEl.textContent = '❌ ' + d.error;
                                out.innerHTML = '<div class="code-block error">' + d.error + '</div>';
                            }
                        } catch(e2){}
                    }
                }
            }
        } catch(e3) {
            clearInterval(timerInterval);
            if (e3.name !== 'AbortError') rd.innerHTML = '<div class="code-block error">重写出错: ' + e3.message + '</div>';
        }
        this.streamAbort = null;
    },

    // ═══════════════════════════════════════════════════════════════════
    // AUTO-LOOP — continuous generation until killed
    // ═══════════════════════════════════════════════════════════════════

    _autoLoopRunning: false,
    _autoLoopAbort: null,

    async _autoLoop() {
        if (this._autoLoopRunning) { this.toast('已有自动续写任务在运行', 'warning'); return; }
        const novel = document.getElementById('wNovel')?.value;
        if (!novel) { this.toast('请选择小说', 'warning'); return; }
        const volume = document.getElementById('wVolume')?.value || 'vol-01';
        var chNum = parseInt(document.getElementById('wChapterNum')?.value) || 1;

        this._autoLoopRunning = true;
        this._autoLoopAbort = new AbortController();
        const rd = document.getElementById('wResult');
        rd.innerHTML = '<div class="card" id="loopCard" style="border-color:var(--accent)">' +
            '<h3>🔁 自动续写模式</h3>' +
            '<div class="text-muted mt-4" style="font-size:12px">' + novel + ' · ' + volume + ' · 从第' + chNum + '章开始</div>' +
            '<div id="loopStatus" class="mt-8" style="font-size:13px;color:var(--text-secondary)">准备中...</div>' +
            '<div id="loopLog" class="mt-8" style="max-height:300px;overflow-y:auto;font-size:12px;font-family:var(--font-mono)"></div>' +
            '<div class="mt-12"><button class="btn btn-lg" onclick="App._killAutoLoop()" style="background:var(--danger);color:#fff">⏹ 停止自动续写</button></div></div>';

        var statusEl = document.getElementById('loopStatus');
        var logEl = document.getElementById('loopLog');
        var btn = document.getElementById('autoLoopBtn');
        if (btn) { btn.textContent = '⏳ 运行中...'; btn.disabled = true; btn.style.opacity = '0.6'; }

        var stats = { generated: 0, failed: 0, totalWords: 0, startCh: chNum };
        var startTime = Date.now();

        function log(msg, color) {
            var t = new Date().toLocaleTimeString();
            logEl.innerHTML += '<div style="color:' + (color||'var(--text-secondary)') + '">[' + t + '] ' + msg + '</div>';
            logEl.scrollTop = logEl.scrollHeight;
        }

        async function doLoop() {
            while (App._autoLoopRunning) {
                var currentCh = chNum;
                statusEl.innerHTML = '✍️ 正在生成第 ' + currentCh + ' 章...';
                log('▶ 开始第 ' + currentCh + ' 章', 'var(--accent)');

                // Generate chapter
                try {
                    var padded = String(currentCh).padStart(4, '0');
                    var chRef = volume + '/ch-' + padded;
                    var data = {
                        volume: volume,
                        chapter_num: String(currentCh),
                        style: App._getWritingStyleStr(),
                        instructions: document.getElementById('wInstructions')?.value || '',
                    };

                    var systemPrompt = await App._buildSystemPrompt(novel, data);
                    systemPrompt += '\n\n## 🔁 自动续写模式\n这是第' + currentCh + '章。请严格按照大纲生成，确保与前章衔接。';

                    var resp = await fetch('/api/ai/stream', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            messages: [{role:'user', content: '请创作 ' + volume + ' 第 ' + currentCh + ' 章'}],
                            system: systemPrompt,
                            temperature: parseFloat(document.getElementById('wTemperature')?.value || '0.8'),
                            max_tokens: parseInt(document.getElementById('wMaxTokens')?.value || '8192'),
                        }),
                        signal: App._autoLoopAbort.signal,
                    });

                    var reader = resp.body.getReader();
                    var decoder = new TextDecoder();
                    var full = '', buf = '';

                    while (true) {
                        var r = await reader.read();
                        if (r.done) break;
                        buf += decoder.decode(r.value, {stream:true});
                        var lines = buf.split('\n');
                        buf = lines.pop()||'';
                        for (var li=0; li<lines.length; li++) {
                            var line = lines[li];
                            if (line.startsWith('data: ')) {
                                try {
                                    var d = JSON.parse(line.slice(6));
                                    if (d.type === 'token') { full += (d.content||''); }
                                    else if (d.type === 'done') {
                                        if (d.content && d.content.length > full.length) full = d.content;
                                    }
                                    else if (d.type === 'error') { throw new Error(d.error || 'stream error'); }
                                } catch(e2){}
                            }
                        }
                    }

                    if (!full) throw new Error('生成内容为空');

                    var wc = (full.match(/[\u4e00-\u9fff]/g)||[]).length;
                    stats.totalWords += wc;

                    // Save
                    await API.editChapter(novel, chRef, full);
                    stats.generated++;
                    var elapsed = Math.floor((Date.now()-startTime)/1000);
                    var mins = Math.floor(elapsed/60);
                    var rate = stats.generated > 0 ? Math.round(stats.totalWords/stats.generated) : 0;

                    statusEl.innerHTML = '✅ 第' + currentCh + '章完成 · ' + wc + '字 · 已生成' + stats.generated + '章共' + Math.round(stats.totalWords/10000*10)/10 + '万字 · ' + mins + '分' + (elapsed%60) + '秒';
                    log('✅ 第' + currentCh + '章 · ' + wc + '字 · 均' + rate + '字/章', 'var(--success)');

                    // Advance to next chapter
                    chNum++;
                    document.getElementById('wChapterNum').value = chNum;

                } catch(e) {
                    if (e.name === 'AbortError') {
                        log('⏹ 用户停止', 'var(--warning)');
                        break;
                    }
                    stats.failed++;
                    statusEl.innerHTML = '❌ 第' + currentCh + '章失败: ' + e.message;
                    log('❌ 第' + currentCh + '章失败: ' + e.message, 'var(--danger)');
                    chNum++; // skip failed chapter
                    if (stats.failed >= 3) {
                        log('⚠️ 连续失败3次，自动停止', 'var(--danger)');
                        break;
                    }
                }

                // Small delay between chapters
                await new Promise(function(r) { setTimeout(r, 2000); });
            }

            // Summary
            var totalTime = Math.floor((Date.now()-startTime)/1000);
            var tMins = Math.floor(totalTime/60);
            statusEl.innerHTML = '⏹ 自动续写已停止 · 生成' + stats.generated + '章 · ' + Math.round(stats.totalWords/10000*10)/10 + '万字 · 失败' + stats.failed + '章 · 耗时' + tMins + '分';
            App._autoLoopRunning = false;
            if (btn) { btn.textContent = '🔁 自动续写'; btn.disabled = false; btn.style.opacity = '1'; }
        }

        doLoop();
    },

    _killAutoLoop() {
        this._autoLoopRunning = false;
        if (this._autoLoopAbort) { this._autoLoopAbort.abort(); this._autoLoopAbort = null; }
        // Also abort any active stream
        if (this.streamAbort) { this.streamAbort.abort(); this.streamAbort = null; }
        this.toast('⏹ 自动续写已停止', 'warning');
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
            this._initNovelSelector('rNovel', function(){App._loadReviewChs();});
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
        mc.innerHTML = `<div class="page-header"><div><h1 class="page-title">📖 章节浏览</h1><p class="page-subtitle">阅读、编辑、审稿</p></div></div><div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="cNovel" onchange="App._loadChapters()"><option value="">-- 请选择 --</option></select></div><div class="form-group"><label class="form-label">搜索</label><input class="form-input" id="cSearch" placeholder="章节号或卷号..." oninput="App._filterChapters()"></div></div><div id="cExportBar" class="mt-8" style="display:none"></div><div id="cList" class="mt-16"></div></div>`;
        const resp = await API.listNovels();
        if (resp.success) {
            const sel = document.getElementById('cNovel');
            resp.novels.forEach(n => { const o = document.createElement('option'); o.value = n.name; o.textContent = `${n.title||n.name} (${n.total_chapters}章)`; sel.appendChild(o); });
            if (params.novel) { sel.value = params.novel; this._loadChapters(); }
            this._initNovelSelector('cNovel', function(){App._loadChapters();});
        }
    },

    async _loadChapters() {
        const name = document.getElementById('cNovel').value;
        const list = document.getElementById('cList');
        const exportBar = document.getElementById('cExportBar');
        if (!name) { list.innerHTML = ''; if (exportBar) exportBar.style.display = 'none'; return; }
        list.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
        // Show export bar
        if (exportBar) {
            exportBar.style.display = 'block';
            exportBar.innerHTML = `<span class="text-sm text-secondary">📦 导出:</span>
                <button class="btn btn-sm btn-primary" onclick="App._exportNovel('${name}','epub')">📗 EPUB</button>
                <button class="btn btn-sm btn-primary" onclick="App._exportNovel('${name}','txt')">📄 TXT</button>
                <button class="btn btn-sm btn-primary" onclick="App._exportNovel('${name}','html')">🌐 HTML</button>`;
        }
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
    async _renderInitWizard(mc) {
        mc.innerHTML = '<div class="page-header"><div><h1 class="page-title">🚀 初始化向导</h1><p class="page-subtitle">一键从文件初始化所有领域表：世界观 · 剧情弧线 · 节奏 · 信息释放 · 角色 · 伏笔</p></div></div>' +
            '<div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="iwNovel"><option value="">-- 请选择 --</option></select></div></div>' +
            '<div class="mt-12 flex gap-8"><button class="btn btn-primary btn-lg" onclick="App._runInitWizard()">🚀 一键初始化</button></div>' +
            '<div class="mt-8"><details><summary style="cursor:pointer;color:var(--text-secondary);font-size:12px">📋 初始化哪些内容？</summary><div class="card mt-4" style="font-size:12px;color:var(--text-secondary)">' +
            '<div>🌍 <strong>world_building</strong> — 从 world_bible.md 解析世界观条目</div>' +
            '<div>📜 <strong>plot_arcs</strong> — 从 full_story_arc.md 解析剧情弧线</div>' +
            '<div>🎵 <strong>pacing_control</strong> — 从大纲解析节奏/情感指引</div>' +
            '<div>🔓 <strong>revelation_schedule</strong> — 从大纲解析信息释放计划</div>' +
            '<div>👥 <strong>characters</strong> — 从 characters.md 解析角色档案</div>' +
            '<div>🔮 <strong>foreshadowing</strong> — 从大纲扫描伏笔标记</div>' +
            '</div></details></div>' +
            '<div id="iwResult" class="mt-16"></div></div>';
        const resp = await API.listNovels();
        if (resp.success) {
            const sel = document.getElementById('iwNovel');
            resp.novels.forEach(function(n) {
                const o = document.createElement('option'); o.value = n.name;
                o.textContent = (n.title||n.name) + ' (' + n.total_chapters + '章)';
                sel.appendChild(o);
            });
            this._initNovelSelector('iwNovel', null);
        }
    },

    async _runInitWizard() {
        const novel = document.getElementById('iwNovel').value;
        if (!novel) { this.toast('请选择小说', 'warning'); return; }
        const rd = document.getElementById('iwResult');
        rd.innerHTML = '<div class="card"><h3>⏳ 正在初始化...</h3><div class="loading mt-8"><div class="spinner"></div><span>正在解析文件并填充数据库，请稍候...</span></div></div>';
        const startTime = Date.now();
        try {
            const resp = await API.initFull(novel);
            const elapsed = ((Date.now()-startTime)/1000).toFixed(1);
            if (!resp.success) {
                rd.innerHTML = '<div class="code-block error">初始化失败: ' + (resp.error||'未知错误') + '</div>';
                return;
            }
            var html = '<div class="card" style="border-color:' + (resp.success?'var(--success)':'var(--warning)') + '">' +
                '<h3>' + (resp.success ? '✅' : '⚠️') + ' 初始化完成 (' + elapsed + 's)</h3>' +
                '<div class="mt-8" style="display:grid;gap:4px;font-size:13px">';
            var tables = resp.tables || {};
            var tableNames = {'world_building':'🌍 世界观条目','plot_arcs':'📜 剧情弧线','pacing_control':'🎵 节奏控制','revelation_schedule':'🔓 信息释放','characters':'👥 角色','foreshadowing':'🔮 伏笔'};
            var total = 0;
            for (var key in tableNames) {
                var count = tables[key] || 0;
                total += count;
                html += '<div>' + tableNames[key] + ': <strong>' + count + '</strong> 条</div>';
            }
            html += '<div class="mt-4" style="border-top:1px solid var(--border);padding-top:4px">共 <strong>' + total + '</strong> 条数据</div>';
            if (resp.errors && resp.errors.length) {
                html += '<div class="mt-8 code-block warning">' + resp.errors.join('\n') + '</div>';
            }
            html += '</div></div>';
            rd.innerHTML = html;
            this.toast('✅ 初始化完成，共 ' + total + ' 条数据', 'success');
        } catch(e) {
            rd.innerHTML = '<div class="code-block error">初始化出错: ' + e.message + '</div>';
        }
    },

    async _renderCharacters(mc) {
        mc.innerHTML = '<div class="page-header"><div><h1 class="page-title">👥 人物管理</h1><p class="page-subtitle">角色档案 · 状态追踪 · 生命线 · 剧本管理</p></div></div>' +
            '<div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="chNovel" onchange="App._loadCharacters()"><option value="">-- 请选择 --</option></select></div></div>' +
            '<div class="flex gap-8 mt-12"><button class="btn btn-primary" onclick="App._initCharacters()">🌱 从文件初始化</button><button class="btn btn-secondary" onclick="App._showAddCharacter()">+ 添加角色</button></div>' +
            '<div id="chList" class="mt-16"></div></div>';
        const resp = await API.listNovels();
        if (resp.success) { const sel = document.getElementById('chNovel'); resp.novels.forEach(function(n) { const o = document.createElement('option'); o.value = n.name; o.textContent = n.title||n.name; sel.appendChild(o); }); this._initNovelSelector('chNovel', function(){App._loadCharacters();}); }
    },

    async _loadCharacters() {
        const novel = document.getElementById('chNovel').value;
        if (!novel) return;
        const ct = document.getElementById('chList');
        ct.innerHTML = '<div class="loading"><div class="spinner sm"></div><span>加载中...</span></div>';
        const resp = await fetch('/api/characters/' + encodeURIComponent(novel)).then(function(r){return r.json();});
        if (!resp.success) { ct.innerHTML = '<div class="code-block error">' + (resp.error||'') + '</div>'; return; }
        if (!resp.items.length) { ct.innerHTML = '<div class="empty-state"><div class="empty-state-icon">👥</div><div class="empty-state-title">暂无角色</div><div class="empty-state-desc">点击"从文件初始化"从 characters.md 导入，或手动添加</div></div>'; return; }
        var roleColors = {'主角': 'var(--accent)', '女主': '#e91e63', '反派': 'var(--danger)', '配角': 'var(--text-secondary)'};
        var html = '<div style="display:grid;gap:8px">';
        resp.items.forEach(function(c) {
            var status = c.current_status || '未设置';
            var pos = c.current_vol ? '第' + c.current_vol + '卷' + (c.current_ch?'第'+c.current_ch+'章':'') : '初始';
            html += '<div class="card" style="border-left:3px solid ' + (roleColors[c.role]||'var(--text-secondary)') + '">' +
                '<div style="display:flex;justify-content:space-between;align-items:start;gap:12px">' +
                '<div style="flex:1">' +
                '<div style="display:flex;align-items:center;gap:8px"><strong style="font-size:16px">' + c.name + '</strong>' +
                '<span style="font-size:10px;padding:1px 6px;border-radius:8px;background:' + (roleColors[c.role]||'#888') + ';color:#fff">' + c.role + '</span></div>' +
                (c.identity ? '<div class="text-muted mt-2" style="font-size:12px">' + c.identity.substring(0, 100) + '</div>' : '') +
                (c.personality ? '<div class="mt-2" style="font-size:12px;color:var(--text-secondary)">🎭 ' + c.personality.substring(0, 120) + '</div>' : '') +
                '<div class="mt-4" style="font-size:11px;display:flex;gap:10px;flex-wrap:wrap">' +
                '<span>📍 ' + status.substring(0, 50) + '</span><span>📖 ' + pos + '</span>' +
                (c.arc ? '<span>📜 剧本: ' + c.arc.substring(0, 40) + '</span>' : '') +
                (c.ending ? '<span>🏁 结局: ' + c.ending.substring(0, 30) + '</span>' : '') +
                '</div></div>' +
                '<div class="flex gap-4" style="flex-shrink:0">' +
                '<button class="btn btn-sm btn-primary" onclick="App._viewCharacter(' + c.id + ')">📋</button>' +
                '<button class="btn btn-sm btn-info" onclick="App._aiGenerateCharacter(' + c.id + ')" style="background:var(--info);color:#fff">🤖</button>' +
                '<button class="btn btn-sm btn-secondary" onclick="App._editCharacter(' + c.id + ')">✏️</button>' +
                '<button class="btn btn-sm btn-success" onclick="App._addCharEvent(' + c.id + ')">📌</button>' +
                '<button class="btn btn-sm btn-outline" onclick="App._deleteCharacter(' + c.id + ')" style="color:var(--danger)">🗑</button>' +
                '</div></div></div>';
        });
        html += '<div class="text-muted mt-8" style="font-size:12px">共 ' + resp.total + ' 个角色</div></div>';
        ct.innerHTML = html;
    },

    async _initCharacters() {
        const novel = document.getElementById('chNovel').value;
        if (!novel) { this.toast('请选择小说', 'warning'); return; }
        const resp = await fetch('/api/characters/' + encodeURIComponent(novel) + '/init', {method:'POST'}).then(function(r){return r.json();});
        resp.success ? (this.toast('✅ ' + resp.message, 'success'), this._loadCharacters()) : this.toast(resp.error, 'error');
    },

    _showAddCharacter() {
        const novel = document.getElementById('chNovel').value;
        if (!novel) { this.toast('请选择小说', 'warning'); return; }
        const body = '<div class="form-group"><label class="form-label">姓名 *</label><input class="form-input" id="acName"></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">角色定位</label><select class="form-select" id="acRole"><option>配角</option><option>主角</option><option>女主</option><option>反派</option></select></div>' +
            '<div class="form-group"><label class="form-label">性别</label><select class="form-select" id="acGender"><option value="">未知</option><option>男</option><option>女</option></select></div></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">年龄</label><input class="form-input" id="acAge"></div>' +
            '<div class="form-group"><label class="form-label">身份</label><input class="form-input" id="acIdentity" placeholder="职业/地位"></div></div>' +
            '<div class="form-group mt-8"><label class="form-label">性格特质</label><textarea class="form-textarea" id="acPersonality" rows="2" placeholder="核心性格特征..."></textarea></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">当前状态</label><input class="form-input" id="acStatus" placeholder="例如：存活/第一卷"></div>' +
            '<div class="form-group"><label class="form-label">当前位置</label><input class="form-input" id="acPos" placeholder="卷/章" style="width:80px"></div></div>' +
            '<div class="form-group mt-8"><label class="form-label">外貌</label><textarea class="form-textarea" id="acAppear" rows="2"></textarea></div>' +
            '<div class="form-group mt-8"><label class="form-label">生命线/剧本</label><textarea class="form-textarea" id="acLifeline" rows="2" placeholder="角色发展轨迹..."></textarea></div>' +
            '<div class="form-group mt-8"><label class="form-label">结局</label><textarea class="form-textarea" id="acEnding" rows="2" placeholder="角色最终结局..."></textarea></div>';
        const footer = '<button class="btn btn-primary" onclick="App._addCharacter()">✔️ 添加</button><button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">取消</button>';
        this.modal('+ 添加角色', body, footer, '600px');
    },

    async _addCharacter() {
        const novel = document.getElementById('chNovel').value;
        const posParts = (document.getElementById('acPos').value||'').split('/');
        const data = {
            name: document.getElementById('acName').value,
            role: document.getElementById('acRole').value,
            gender: document.getElementById('acGender').value,
            age: document.getElementById('acAge').value,
            identity: document.getElementById('acIdentity').value,
            personality: document.getElementById('acPersonality').value,
            appearance: document.getElementById('acAppear').value,
            current_status: document.getElementById('acStatus').value,
            current_vol: parseInt(posParts[0])||0,
            current_ch: parseInt(posParts[1])||0,
            lifeline: document.getElementById('acLifeline').value,
            ending: document.getElementById('acEnding').value,
        };
        if (!data.name) { this.toast('请填写姓名', 'warning'); return; }
        const resp = await fetch('/api/characters/' + encodeURIComponent(novel), {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data)}).then(function(r){return r.json();});
        resp.success ? (this.toast('✅ 角色已添加', 'success'), document.querySelectorAll('.modal-overlay').forEach(function(m){m.remove()}), this._loadCharacters()) : this.toast(resp.error, 'error');
    },

    async _viewCharacter(cid) {
        const novel = document.getElementById('chNovel').value;
        const resp = await fetch('/api/characters/' + encodeURIComponent(novel) + '/' + cid).then(function(r){return r.json();});
        if (!resp.success) { this.toast(resp.error, 'error'); return; }
        const c = resp.character;
        const events = resp.events || [];
        var evHtml = events.length ? events.map(function(e) {
            return '<div class="card mb-4" style="padding:6px 10px;font-size:12px"><strong>' + (e.event_type||'') + '</strong> ' + e.description +
                (e.vol ? ' <span class="text-muted">第' + e.vol + '卷' + (e.ch?'第'+e.ch+'章':'') + '</span>' : '') + '</div>';
        }).join('') : '<div class="text-muted" style="font-size:12px">暂无事件记录</div>';
        var body = '<div class="card mb-8" style="border-left:3px solid var(--accent)"><h3>' + c.name + ' <span style="font-size:12px;color:var(--text-tertiary)">' + c.role + '</span></h3>' +
            '<div class="mt-8" style="display:grid;gap:4px;font-size:13px">' +
            (c.identity ? '<div><strong>身份:</strong> ' + c.identity + '</div>' : '') +
            (c.gender ? '<div><strong>性别:</strong> ' + c.gender + ' ' + (c.age||'') + '</div>' : '') +
            (c.personality ? '<div><strong>性格:</strong> ' + c.personality + '</div>' : '') +
            (c.appearance ? '<div><strong>外貌:</strong> ' + c.appearance + '</div>' : '') +
            (c.background ? '<div><strong>背景:</strong> ' + c.background.substring(0, 300) + '</div>' : '') +
            '<div><strong>当前状态:</strong> ' + (c.current_status||'未设置') + ' · 第' + (c.current_vol||'?') + '卷第' + (c.current_ch||'?') + '章</div>' +
            (c.lifeline ? '<div><strong>生命线:</strong> ' + c.lifeline + '</div>' : '') +
            (c.arc ? '<div><strong>剧本:</strong> ' + c.arc + '</div>' : '') +
            (c.ending ? '<div><strong>结局:</strong> ' + c.ending + '</div>' : '') +
            '</div></div>' +
            '<h4 class="mt-12">📌 事件/状态变更记录</h4>' + evHtml;
        const footer = '<button class="btn btn-secondary" onclick="App._editCharacter(' + cid + ')">✏️ 编辑</button>' +
            '<button class="btn btn-success" onclick="App._addCharEvent(' + cid + ')">📌 添加事件</button>' +
            '<button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">关闭</button>';
        this.modal('👤 ' + c.name, body, footer, '650px');
    },

    async _editCharacter(cid) {
        const novel = document.getElementById('chNovel').value;
        const resp = await fetch('/api/characters/' + encodeURIComponent(novel) + '/' + cid).then(function(r){return r.json();});
        if (!resp.success) return;
        const c = resp.character;
        // Escape helper
        function esc(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;').replace(/'/g,'&#39;'); }
        var body = '<div class="tab-bar" style="margin-bottom:12px">' +
            '<span class="tab-item active" data-t="core" onclick="App._switchCharTab(this,\'core\')">🎭 核心</span>' +
            '<span class="tab-item" data-t="arc" onclick="App._switchCharTab(this,\'arc\')">📈 成长</span>' +
            '<span class="tab-item" data-t="ability" onclick="App._switchCharTab(this,\'ability\')">⚡ 能力</span>' +
            '<span class="tab-item" data-t="emotion" onclick="App._switchCharTab(this,\'emotion\')">💭 情感</span>' +
            '<span class="tab-item" data-t="dilemma" onclick="App._switchCharTab(this,\'dilemma\')">⚖️ 困境</span>' +
            '<span class="tab-item" data-t="mirror" onclick="App._switchCharTab(this,\'mirror\')">🪞 镜像</span>' +
            '</div>' +
            '<div id="charTabContent">' +
            '<!-- Tab 1: Core -->' +
            '<div id="charTab-core">' +
            '<div class="form-row"><div class="form-group"><label class="form-label">姓名</label><input class="form-input" id="ecName" value="' + esc(c.name) + '"></div>' +
            '<div class="form-group"><label class="form-label">角色</label><select class="form-select" id="ecRole">' + ['主角','女主','反派','配角'].map(function(r){return '<option'+(r===c.role?' selected':'')+'>'+r+'</option>';}).join('') + '</select></div></div>' +
            '<div class="form-group mt-8"><label class="form-label">身份</label><input class="form-input" id="ecIdentity" value="' + esc(c.identity) + '"></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">当前状态 ⚠️</label><input class="form-input" id="ecStatus" value="' + esc(c.current_status||'') + '"></div>' +
            '<div class="form-group"><label class="form-label">位置(卷/章)</label><div class="flex gap-4"><input class="form-input" id="ecVol" type="number" value="' + (c.current_vol||0) + '" style="width:60px"><span style="line-height:36px">卷</span><input class="form-input" id="ecCh" type="number" value="' + (c.current_ch||0) + '" style="width:60px"><span style="line-height:36px">章</span></div></div></div>' +
            '<div class="form-group mt-8"><label class="form-label">🎯 核心欲望 (Desire)</label><textarea class="form-textarea" id="ecDesire" rows="2" placeholder="角色最深层想要什么？">' + esc(c.desire||'') + '</textarea></div>' +
            '<div class="form-group mt-8"><label class="form-label">😱 核心恐惧 (Fear)</label><textarea class="form-textarea" id="ecFear" rows="2" placeholder="角色最怕什么？">' + esc(c.fear||'') + '</textarea></div>' +
            '<div class="form-group mt-8"><label class="form-label">🤥 核心谎言 (Lie)</label><textarea class="form-textarea" id="ecLie" rows="2" placeholder="角色相信什么错误信念？">' + esc(c.lie||'') + '</textarea></div>' +
            '<div class="form-group mt-8"><label class="form-label">💡 核心真相 (Truth)</label><textarea class="form-textarea" id="ecTruth" rows="2" placeholder="故事最终要揭示什么？">' + esc(c.truth||'') + '</textarea></div>' +
            '<div class="form-group mt-8"><label class="form-label">🎭 性格特质</label><textarea class="form-textarea" id="ecPersonality" rows="3">' + esc(c.personality||'') + '</textarea></div>' +
            '</div>' +
            '<!-- Tab 2: Arc -->' +
            '<div id="charTab-arc" style="display:none">' +
            '<div class="form-group"><label class="form-label">📈 成长弧线 (Growth Arc)</label><textarea class="form-textarea" id="ecArc" rows="4" placeholder="起点状态 → 催化事件 → 第一次失败 → 领悟 → 蜕变 → 终局">' + esc(c.arc||'') + '</textarea></div>' +
            '<div class="form-group mt-8"><label class="form-label">🗺️ 生命线 (Lifeline)</label><textarea class="form-textarea" id="ecLifeline" rows="4" placeholder="卷1: ... → 卷2: ... → 卷3: ...">' + esc(c.lifeline||'') + '</textarea></div>' +
            '<div class="form-group mt-8"><label class="form-label">🏁 结局 (Ending)</label><textarea class="form-textarea" id="ecEnding" rows="3" placeholder="角色最终命运...">' + esc(c.ending||'') + '</textarea></div>' +
            '</div>' +
            '<!-- Tab 3: Ability -->' +
            '<div id="charTab-ability" style="display:none">' +
            '<div class="form-group"><label class="form-label">⚡ 能力等级 (Ability Level)</label><input class="form-input" id="ecAbility" value="' + esc(c.ability_level||'') + '" placeholder="当前能力等级/阶段"></div>' +
            '<div class="form-group mt-8"><label class="form-label">📊 能力曲线 (Ability Curve)</label><textarea class="form-textarea" id="ecAbilityCurve" rows="5" placeholder="卷1: 普通人\n卷2: 觉醒 - 获得XX能力\n卷3: 掌握 - 能熟练使用\n卷4: 突破 - 达到XX境界\n...\n卷7: 成神 - 最终形态">' + esc(c.ability_curve||'') + '</textarea></div>' +
            '<div class="form-group mt-8"><label class="form-label">💸 能力代价</label><textarea class="form-textarea" id="ecAbilityCost" rows="2" placeholder="每次能力升级付出的代价是什么？">' + esc(c.ability_cost||'') + '</textarea></div>' +
            '</div>' +
            '<!-- Tab 4: Emotion -->' +
            '<div id="charTab-emotion" style="display:none">' +
            '<div class="form-group"><label class="form-label">💭 情感状态 (Emotional State)</label><input class="form-input" id="ecEmotion" value="' + esc(c.emotional_state||'') + '" placeholder="当前情感: 坚定/动摇/绝望/愤怒/..."></div>' +
            '<div class="form-group mt-8"><label class="form-label">📈 情感曲线</label><textarea class="form-textarea" id="ecEmotionCurve" rows="5" placeholder="卷1: 迷茫 → 好奇\n卷2: 自信 → 挫折\n卷3: 质疑 → 愤怒\n卷4: 接受 → 坚定\n...">' + esc(c.emotion_curve||'') + '</textarea></div>' +
            '<div class="form-group mt-8"><label class="form-label">🔗 关系网络 (Relationship Map)</label><textarea class="form-textarea" id="ecRelations" rows="5" placeholder=' + JSON.stringify([{target:"叶微",type:"恋人",start:"陌生人",conflict:"信任危机",end:"永恒羁绊"}]) + '>' + esc(c.relationship_map||'') + '</textarea></div>' +
            '</div>' +
            '<!-- Tab 5: Dilemma -->' +
            '<div id="charTab-dilemma" style="display:none">' +
            '<div class="form-group"><label class="form-label">⚖️ 道德困境 (每卷/地图1-2次)</label><textarea class="form-textarea" id="ecDilemma" rows="8" placeholder=' + JSON.stringify([{vol:"卷1",dilemma:"两难选择描述",choice:"选择了什么",cost:"付出了什么代价",gained:"得到了什么"}]) + '>' + esc(c.dilemma||'') + '</textarea></div>' +
            '</div>' +
            '<!-- Tab 6: Mirror -->' +
            '<div id="charTab-mirror" style="display:none">' +
            '<div class="form-group"><label class="form-label">🪞 镜像角色 (对映关系)</label><textarea class="form-textarea" id="ecMirror" rows="6" placeholder=' + JSON.stringify([{character:"反派XX",mirrors:"主角的XX特质",contrast:"但选择了不同的路"},{character:"配角XX",complements:"补全主角缺失的XX"}]) + '>' + esc(c.mirror||'') + '</textarea></div>' +
            '<div class="form-group mt-8"><label class="form-label">📝 备注 (Notes)</label><textarea class="form-textarea" id="ecNotes" rows="2">' + esc(c.notes||'') + '</textarea></div>' +
            '</div>' +
            '</div>';
        var footer = '<button class="btn btn-primary" onclick="App._saveCharacter(' + cid + ')\">💾 保存</button>' +
            '<button class="btn btn-success" onclick="App._aiGenerateCharacter(' + cid + ')\">🤖 AI 生成角色档案</button>' +
            '<button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">取消</button>';
        this.modal('✏️ ' + c.name + ' · 角色剧本', body, footer, '800px');
    },

    _switchCharTab(tab, t) {
        var modal = tab.closest('.modal');
        modal.querySelectorAll('.tab-item').forEach(function(x) { x.classList.remove('active'); });
        tab.classList.add('active');
        for (var i=0; i<modal.querySelectorAll('#charTabContent > div').length; i++) {
            modal.querySelectorAll('#charTabContent > div')[i].style.display = 'none';
        }
        var target = modal.querySelector('#charTab-' + t);
        if (target) target.style.display = 'block';
    },

    async _aiGenerateCharacter(cid) {
        const novel = document.getElementById('chNovel').value;
        if (!confirm('AI 将基于已有信息生成完整的8维角色档案。继续？')) return;
        const resp = await fetch('/api/characters/' + encodeURIComponent(novel) + '/' + cid + '/ai-profile', {method:'POST'}).then(function(r){return r.json();});
        if (resp.success) {
            // Refill the form with AI data
            var fields = resp.profile || {};
            var fieldMap = {desire:'ecDesire', fear:'ecFear', lie:'ecLie', truth:'ecTruth',
                personality:'ecPersonality', arc:'ecArc', lifeline:'ecLifeline', ending:'ecEnding',
                ability_level:'ecAbility', ability_curve:'ecAbilityCurve', ability_cost:'ecAbilityCost',
                emotional_state:'ecEmotion', emotion_curve:'ecEmotionCurve', relationship_map:'ecRelations',
                dilemma:'ecDilemma', mirror:'ecMirror', notes:'ecNotes'};
            for (var key in fieldMap) {
                var el = document.getElementById(fieldMap[key]);
                if (el && fields[key]) el.value = fields[key];
            }
            this.toast('✅ AI 已生成角色档案，请检查并保存', 'success');
        } else {
            this.toast('AI 生成失败: ' + (resp.error||''), 'error');
        }
    },

    async _saveCharacter(cid) {
        const novel = document.getElementById('chNovel').value;
        var g = function(id) { var el = document.getElementById(id); return el ? el.value : ''; };
        var data = {
            name: g('ecName'), role: g('ecRole'), identity: g('ecIdentity'),
            personality: g('ecPersonality'), current_status: g('ecStatus'),
            current_vol: parseInt(g('ecVol'))||0, current_ch: parseInt(g('ecCh'))||0,
            lifeline: g('ecLifeline'), arc: g('ecArc'), ending: g('ecEnding'),
            desire: g('ecDesire'), fear: g('ecFear'), lie: g('ecLie'), truth: g('ecTruth'),
            ability_level: g('ecAbility'), ability_curve: g('ecAbilityCurve'), ability_cost: g('ecAbilityCost'),
            emotional_state: g('ecEmotion'), emotion_curve: g('ecEmotionCurve'), relationship_map: g('ecRelations'),
            dilemma: g('ecDilemma'), mirror: g('ecMirror'), notes: g('ecNotes'),
        };
        const resp = await fetch('/api/characters/' + encodeURIComponent(novel) + '/' + cid, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data)}).then(function(r){return r.json();});
        resp.success ? (this.toast('✅ 已更新', 'success'), document.querySelectorAll('.modal-overlay').forEach(function(m){m.remove()}), this._loadCharacters()) : this.toast(resp.error, 'error');
    },

    _addCharEvent(cid) {
        const novel = document.getElementById('chNovel').value;
        const body = '<div class="form-group"><label class="form-label">事件类型</label><select class="form-select" id="aeType"><option>状态变更</option><option>能力觉醒</option><option>关系变化</option><option>重大转折</option><option>死亡</option><option>复活</option></select></div>' +
            '<div class="form-group mt-8"><label class="form-label">描述 *</label><textarea class="form-textarea" id="aeDesc" rows="3" placeholder="发生了什么..."></textarea></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">卷第</label><input class="form-input" id="aeVol" type="number" value="1"></div>' +
            '<div class="form-group"><label class="form-label">章</label><input class="form-input" id="aeCh" type="number" value="1"></div></div>' +
            '<div class="form-group mt-8"><label class="form-label">章节引用</label><input class="form-input" id="aeRef" placeholder="如: vol-01/ch-0001"></div>';
        const footer = '<button class="btn btn-success" onclick="App._saveCharEvent(' + cid + ')">📌 记录事件</button><button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">取消</button>';
        this.modal('📌 添加事件', body, footer, '520px');
    },

    async _saveCharEvent(cid) {
        const novel = document.getElementById('chNovel').value;
        const data = {
            event_type: document.getElementById('aeType').value,
            description: document.getElementById('aeDesc').value,
            vol: parseInt(document.getElementById('aeVol').value)||0,
            ch: parseInt(document.getElementById('aeCh').value)||0,
            chapter_ref: document.getElementById('aeRef').value,
        };
        if (!data.description) { this.toast('请填写事件描述', 'warning'); return; }
        const resp = await fetch('/api/characters/' + encodeURIComponent(novel) + '/' + cid + '/event', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data)}).then(function(r){return r.json();});
        resp.success ? (this.toast('📌 事件已记录', 'success'), document.querySelectorAll('.modal-overlay').forEach(function(m){m.remove()})) : this.toast(resp.error, 'error');
    },

    async _deleteCharacter(cid) {
        if (!confirm('确认删除此角色？')) return;
        const novel = document.getElementById('chNovel').value;
        const resp = await fetch('/api/characters/' + encodeURIComponent(novel) + '/' + cid, {method:'DELETE'}).then(function(r){return r.json();});
        resp.success ? (this.toast('已删除', 'success'), this._loadCharacters()) : this.toast(resp.error, 'error');
    },

    async _renderForeshadowing(mc) {
        mc.innerHTML = '<div class="page-header"><div><h1 class="page-title">🔮 伏笔管理</h1><p class="page-subtitle">跟踪每一条伏笔，确保完美填坑</p></div></div>' +
            '<div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="fsNovel" onchange="App._loadForeshadowing()"><option value="">-- 请选择 --</option></select></div>' +
            '<div class="form-group"><label class="form-label">筛选</label><select class="form-select" id="fsFilter" onchange="App._loadForeshadowing()"><option value="">全部</option><option value="pending">待填坑</option><option value="resolved">已填坑</option><option value="abandoned">已废弃</option></select></div></div>' +
            '<div class="flex gap-8 mt-12"><button class="btn btn-primary" onclick="App._initForeshadowing()">🌱 从大纲初始化</button><button class="btn btn-secondary" onclick="App._showAddForeshadowing()">+ 手动添加</button></div>' +
            '<div id="fsList" class="mt-16"></div></div>';
        const resp = await API.listNovels();
        if (resp.success) { const sel = document.getElementById('fsNovel'); resp.novels.forEach(function(n) { const o = document.createElement('option'); o.value = n.name; o.textContent = n.title||n.name; sel.appendChild(o); }); this._initNovelSelector('fsNovel', function(){App._loadForeshadowing();}); }
    },

    async _loadForeshadowing() {
        const novel = document.getElementById('fsNovel').value;
        const filter = document.getElementById('fsFilter').value;
        if (!novel) return;
        const ct = document.getElementById('fsList');
        ct.innerHTML = '<div class="loading"><div class="spinner sm"></div><span>加载中...</span></div>';
        const params = filter ? '?status=' + filter : '';
        const resp = await fetch('/api/foreshadowing/' + encodeURIComponent(novel) + params).then(function(r){return r.json();});
        if (!resp.success) { ct.innerHTML = '<div class="code-block error">' + (resp.error||'') + '</div>'; return; }
        if (!resp.items.length) { ct.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔮</div><div class="empty-state-title">暂无伏笔</div><div class="empty-state-desc">点击"从大纲初始化"自动扫描，或手动添加</div></div>'; return; }
        var statusMap = {pending: '🟡 待填', resolved: '✅ 已填', abandoned: '⚪ 废弃'};
        var priorityMap = {high: '🔴 高', normal: '🟡 中', low: '🟢 低'};
        var html = '';
        resp.items.forEach(function(f) {
            html += '<div class="card mb-8" style="border-left:3px solid ' + (f.priority==='high'?'var(--danger)':f.priority==='low'?'var(--success)':'var(--accent)') + '">' +
                '<div style="display:flex;justify-content:space-between;align-items:start">' +
                '<div style="flex:1"><strong>' + f.name + '</strong>' +
                '<div class="mt-4" style="font-size:13px;color:var(--text-secondary)">' + f.description + '</div>' +
                '<div class="mt-8" style="font-size:11px;color:var(--text-tertiary);display:flex;gap:12px;flex-wrap:wrap">' +
                '<span>' + (priorityMap[f.priority]||f.priority) + '</span>' +
                '<span>📂 ' + (f.category||'') + '</span>' +
                '<span>' + statusMap[f.status] + '</span>' +
                (f.introduced_vol ? '<span>👍 第' + f.introduced_vol + '卷' + (f.introduced_ch ? '第' + f.introduced_ch + '章' : '') + '</span>' : '') +
                (f.target_vol ? '<span>🎯 目标第' + f.target_vol + '卷' + (f.target_ch ? '第' + f.target_ch + '章' : '') + '</span>' : '') +
                (f.resolved_vol ? '<span>✅ 填于第' + f.resolved_vol + '卷' + (f.resolved_ch ? '第' + f.resolved_ch + '章' : '') + '</span>' : '') +
                '</div></div>' +
                '<div class="flex gap-4" style="flex-shrink:0;margin-left:12px">' +
                '<button class="btn btn-sm btn-secondary" onclick="App._editForeshadowing(' + f.id + ')">✏️</button>' +
                (f.status === 'pending' ? '<button class="btn btn-sm btn-success" onclick="App._resolveForeshadowing(' + f.id + ')">✅</button>' : '') +
                '<button class="btn btn-sm btn-outline" onclick="App._deleteForeshadowing(' + f.id + ')" style="color:var(--danger)">🗑</button>' +
                '</div></div></div>';
        });
        html += '<div class="text-muted mt-8" style="font-size:12px">共 ' + resp.total + ' 条伏笔</div>';
        ct.innerHTML = html;
    },

    async _initForeshadowing() {
        const novel = document.getElementById('fsNovel').value;
        if (!novel) { this.toast('请选择小说', 'warning'); return; }
        this.toast('正在扫描大纲...', 'info');
        const resp = await fetch('/api/foreshadowing/' + encodeURIComponent(novel) + '/init', {method:'POST'}).then(function(r){return r.json();});
        resp.success ? (this.toast('✅ ' + resp.message, 'success'), this._loadForeshadowing()) : this.toast(resp.error, 'error');
    },

    _showAddForeshadowing() {
        const novel = document.getElementById('fsNovel').value;
        if (!novel) { this.toast('请选择小说', 'warning'); return; }
        const body = '<div class="form-group"><label class="form-label">伏笔名称 *</label><input class="form-input" id="fsName" placeholder="例如：叛神系统的真实身份"></div>' +
            '<div class="form-group mt-8"><label class="form-label">描述</label><textarea class="form-textarea" id="fsDesc" rows="3" placeholder="伏笔具体内容..."></textarea></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">类别</label><select class="form-select" id="fsCat"><option>剧情</option><option>角色</option><option>世界观</option><option>身份</option><option>女主</option><option>能力</option></select></div>' +
            '<div class="form-group"><label class="form-label">优先级</label><select class="form-select" id="fsPrio"><option value="normal">中</option><option value="high">高</option><option value="low">低</option></select></div></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">引入卷</label><input class="form-input" id="fsIVol" type="number" value="1"></div>' +
            '<div class="form-group"><label class="form-label">引入章</label><input class="form-input" id="fsICh" type="number" value="1"></div></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">填坑目标卷</label><input class="form-input" id="fsTVol" type="number" placeholder="0=未指定"></div>' +
            '<div class="form-group"><label class="form-label">填坑目标章</label><input class="form-input" id="fsTCh" type="number" placeholder="0=未指定"></div></div>';
        const footer = '<button class="btn btn-primary" onclick="App._addForeshadowing()">✔️ 添加</button><button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">取消</button>';
        this.modal('+ 添加伏笔', body, footer, '560px');
    },

    async _addForeshadowing() {
        const novel = document.getElementById('fsNovel').value;
        const data = {
            name: document.getElementById('fsName').value,
            description: document.getElementById('fsDesc').value,
            category: document.getElementById('fsCat').value,
            priority: document.getElementById('fsPrio').value,
            introduced_vol: parseInt(document.getElementById('fsIVol').value)||0,
            introduced_ch: parseInt(document.getElementById('fsICh').value)||0,
            target_vol: parseInt(document.getElementById('fsTVol').value)||0,
            target_ch: parseInt(document.getElementById('fsTCh').value)||0,
        };
        if (!data.name) { this.toast('请填写伏笔名称', 'warning'); return; }
        const resp = await fetch('/api/foreshadowing/' + encodeURIComponent(novel), {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data)}).then(function(r){return r.json();});
        resp.success ? (this.toast('✅ 伏笔已添加', 'success'), document.querySelectorAll('.modal-overlay').forEach(function(m){m.remove()}), this._loadForeshadowing()) : this.toast(resp.error, 'error');
    },

    async _editForeshadowing(fid) {
        const novel = document.getElementById('fsNovel').value;
        const resp = await fetch('/api/foreshadowing/' + encodeURIComponent(novel)).then(function(r){return r.json();});
        if (!resp.success) return;
        const f = resp.items.find(function(x){return x.id===fid});
        if (!f) return;
        const body = '<div class="form-group"><label class="form-label">伏笔名称</label><input class="form-input" id="efName" value="' + (f.name||'') + '"></div>' +
            '<div class="form-group mt-8"><label class="form-label">描述</label><textarea class="form-textarea" id="efDesc" rows="3">' + (f.description||'') + '</textarea></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">类别</label><select class="form-select" id="efCat">' + ['剧情','角色','世界观','身份','女主','能力'].map(function(c){return '<option'+(c===f.category?' selected':'')+'>'+c+'</option>';}).join('') + '</select></div>' +
            '<div class="form-group"><label class="form-label">状态</label><select class="form-select" id="efStatus">' + ['pending','resolved','abandoned'].map(function(s){return '<option'+(s===f.status?' selected':'')+'>'+s+'</option>';}).join('') + '</select></div></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">优先级</label><select class="form-select" id="efPrio">' + ['high','normal','low'].map(function(p){return '<option value="'+p+'"'+(p===f.priority?' selected':'')+'>'+(p==='high'?'高':p==='low'?'低':'中')+'</option>';}).join('') + '</select></div>' +
            '<div class="form-group"><label class="form-label">目标卷</label><input class="form-input" id="efTVol" type="number" value="' + (f.target_vol||0) + '"></div></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">目标章</label><input class="form-input" id="efTCh" type="number" value="' + (f.target_ch||0) + '"></div>' +
            '<div class="form-group"><label class="form-label">引入卷/章</label><input class="form-input" id="efIVolCh" value="' + (f.introduced_vol||'?') + '卷' + (f.introduced_ch||'?') + '章" readonly></div></div>' +
            '<div class="form-group mt-8"><label class="form-label">填坑说明</label><textarea class="form-textarea" id="efNote" rows="2">' + (f.resolution_note||'') + '</textarea></div>';
        const footer = '<button class="btn btn-primary" onclick="App._saveForeshadowing(' + fid + ')">💾 保存</button><button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">取消</button>';
        this.modal('✏️ 编辑伏笔', body, footer, '560px');
    },

    async _saveForeshadowing(fid) {
        const novel = document.getElementById('fsNovel').value;
        const data = {
            name: document.getElementById('efName').value,
            description: document.getElementById('efDesc').value,
            category: document.getElementById('efCat').value,
            status: document.getElementById('efStatus').value,
            priority: document.getElementById('efPrio').value,
            target_vol: parseInt(document.getElementById('efTVol').value)||0,
            target_ch: parseInt(document.getElementById('efTCh').value)||0,
            resolution_note: document.getElementById('efNote').value,
        };
        const resp = await fetch('/api/foreshadowing/' + encodeURIComponent(novel) + '/' + fid, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data)}).then(function(r){return r.json();});
        resp.success ? (this.toast('✅ 已更新', 'success'), document.querySelectorAll('.modal-overlay').forEach(function(m){m.remove()}), this._loadForeshadowing()) : this.toast(resp.error, 'error');
    },

    async _resolveForeshadowing(fid) {
        const novel = document.getElementById('fsNovel').value;
        const body = '<div class="form-group"><label class="form-label">在哪卷填坑</label><input class="form-input" id="rfVol" type="number" value="1"></div>' +
            '<div class="form-group mt-8"><label class="form-label">在哪章填坑</label><input class="form-input" id="rfCh" type="number" value="1"></div>' +
            '<div class="form-group mt-8"><label class="form-label">填坑说明</label><textarea class="form-textarea" id="rfNote" rows="2" placeholder="如何解释这个伏笔..."></textarea></div>';
        const footer = '<button class="btn btn-success" onclick="App._doResolve(' + fid + ')">✅ 标记已填</button><button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">取消</button>';
        this.modal('✅ 填坑确认', body, footer, '520px');
    },

    async _doResolve(fid) {
        const novel = document.getElementById('fsNovel').value;
        const data = {vol: parseInt(document.getElementById('rfVol').value)||0, ch: parseInt(document.getElementById('rfCh').value)||0, note: document.getElementById('rfNote').value};
        const resp = await fetch('/api/foreshadowing/' + encodeURIComponent(novel) + '/resolve/' + fid, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data)}).then(function(r){return r.json();});
        resp.success ? (this.toast('✅ 已标记填坑', 'success'), document.querySelectorAll('.modal-overlay').forEach(function(m){m.remove()}), this._loadForeshadowing()) : this.toast(resp.error, 'error');
    },

    async _deleteForeshadowing(fid) {
        if (!confirm('确认删除这条伏笔？')) return;
        const novel = document.getElementById('fsNovel').value;
        const resp = await fetch('/api/foreshadowing/' + encodeURIComponent(novel) + '/' + fid, {method:'DELETE'}).then(function(r){return r.json();});
        resp.success ? (this.toast('已删除', 'success'), this._loadForeshadowing()) : this.toast(resp.error, 'error');
    },

    async _renderWorkflow(mc) {
        mc.innerHTML = `<div class="page-header"><div><h1 class="page-title">🔗 工作流强制执行</h1><p class="page-subtitle">脚本化门控验证 · 阶段检查 · 管道执行</p></div></div>
        <div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="wfNovel" onchange="App._loadWfChapters()"><option value="">-- 请选择 --</option></select></div>
        <div class="form-group"><label class="form-label">选择章节</label><select class="form-select" id="wfChapter"><option value="">-- 请先选小说 --</option></select></div>
        <div class="form-group"><label class="form-label">卷号</label><input class="form-input" id="wfVolume" value="vol-01" style="width:80px"></div>
        </div>
        <div class="mt-12 flex gap-8">
            <button class="btn btn-primary" onclick="App._runPipeline()">▶️ 执行全管道</button>
            <button class="btn btn-secondary" onclick="App._runPreflightOnly()">⚙️ 仅门控</button>
            <button class="btn btn-outline" onclick="App._runPostflightOnly()">📋 仅后置检查</button>
        </div>
        <div id="wfResult" class="mt-16"></div></div>`;
        const resp = await API.listNovels();
        if (resp.success) { const sel = document.getElementById('wfNovel'); resp.novels.forEach(n => { const o = document.createElement('option'); o.value = n.name; o.textContent = n.title||n.name; sel.appendChild(o); }); this._initNovelSelector('wfNovel', function(){App._loadWfChapters();}); }
    },

    async _loadWfChapters() {
        const name = document.getElementById('wfNovel').value;
        const sel = document.getElementById('wfChapter'); sel.innerHTML = name ? '<option value="">加载中...</option>' : '<option value="">-- 请先选小说 --</option>';
        if (!name) return;
        const resp = await API.getNovel(name);
        if (!resp.success) return;
        sel.innerHTML = '<option value="">-- 全部章节 --</option>';
        (resp.novel.volumes||[]).forEach(v => { sel.innerHTML += `<optgroup label="${v.name}">`; v.chapters.forEach(ch => { sel.innerHTML += `<option value="${v.name}/${ch.name}">${v.name}/${ch.name}</option>`; }); sel.innerHTML += '</optgroup>'; });
    },

    _getWfData() {
        const novel = document.getElementById('wfNovel').value;
        const chRef = document.getElementById('wfChapter').value;
        const volume = document.getElementById('wfVolume').value;
        if (!novel) { App.toast('请选择小说', 'warning'); return null; }
        let chapter_num = '';
        if (chRef) { const m = chRef.match(/ch-(\\d+)/); if (m) chapter_num = m[1]; }
        return {novel, chapter_num: chapter_num || '001', chapter_ref: chRef, volume};
    },

    async _runPipeline() {
        const d = this._getWfData(); if (!d) return;
        const rd = document.getElementById('wfResult');
        rd.innerHTML = '<div class="card"><h3>⏳ 执行管道中...</h3><div class="loading mt-8"><div class="spinner"></div><span>运行全管道强制检查，请稍候...</span></div></div>';
        const startTime = Date.now();
        const resp = await API.request('POST', `/api/novels/${encodeURIComponent(d.novel)}/enforce-pipeline`, d);
        const elapsed = ((Date.now()-startTime)/1000).toFixed(1);
        if (!resp.success) { rd.innerHTML = '<div class="code-block error">'+(resp.error||'管道执行失败')+'</div>'; return; }

        let html = `<div class="card" style="border-color:${resp.all_ok?'var(--success)':'var(--danger)'}"><h3>${resp.all_ok ? '✅ 全部通过' : '❌ 未通过'}</h3><p class="text-muted">${resp.passed}/${resp.total} 项检查通过 · 耗时 ${elapsed}s</p>`;
        html += '<div class="mt-12" style="display:grid;gap:6px">';
        const entries = Object.entries(resp.pipeline||{}).sort();
        for (const [key, step] of entries) {
            if (!step) continue;
            const idx = key.replace(/^\\d+[a-z]?_/,'').replace(/_/g,' ');
            html += `<div class="review-progress-item ${step.ok?'':'danger'}" style="padding:6px 8px"><div class="review-progress-dot${step.ok?'':' idle'}" style="flex-shrink:0"></div><div style="flex:1;min-width:0"><strong>${step.name}</strong> ${step.ok?'✅':'❌'}<div class="text-muted mt-2" style="font-size:11px;white-space:pre-wrap;word-break:break-all">${step.output||''}</div></div></div>`;
        }
        html += '</div></div>';
        rd.innerHTML = html;
        this.toast(resp.all_ok ? '🎉 全管道通过' : '⚠️ ' + (resp.total-resp.passed) + ' 项未通过', resp.all_ok?'success':'warning');
    },

    async _runPreflightOnly() {
        const d = this._getWfData(); if (!d) return;
        const rd = document.getElementById('wfResult');
        rd.innerHTML = '<div class="loading"><div class="spinner sm"></div><span>门控检查中...</span></div>';
        const resp = await API.preflightCheck(d.novel, {volume: d.volume, chapter_num: d.chapter_num});
        let html = `<div class="card" style="border-color:${resp.all_ok?'var(--success)':'var(--warning)'}"><h3>${resp.all_ok ? '✅ 门控通过' : '⚠️ 门控警告'}</h3><div class="mt-8" style="display:grid;gap:4px">`;
        for (const [k, r] of Object.entries(resp.results||{})) {
            html += `<div style="display:flex;align-items:center;gap:8px;font-size:13px">${r.ok?'✅':'⚠️'} <strong>${r.name}</strong> <span class="text-muted">${r.detail||''}</span></div>`;
        }
        html += '</div></div>';
        rd.innerHTML = html;
    },

    async _runPostflightOnly() {
        const d = this._getWfData(); if (!d) return;
        const rd = document.getElementById('wfResult');
        rd.innerHTML = '<div class="loading"><div class="spinner sm"></div><span>后置检查中...</span></div>';
        const resp = await API.postflightCheck(d.novel, {chapter_ref: d.chapter_ref, volume: d.volume, chapter_num: d.chapter_num});
        let html = `<div class="card" style="border-color:${resp.all_ok?'var(--success)':'var(--warning)'}"><h3>${resp.all_ok ? '✅ 后置通过' : '⚠️ 后置未完全通过'}</h3><div class="mt-8" style="display:grid;gap:4px">`;
        for (const [k, r] of Object.entries(resp.results||{})) {
            html += `<div style="display:flex;align-items:center;gap:8px;font-size:13px">${r.ok?'✅':'❌'} <strong>${r.name}</strong> <span class="text-muted">${(r.detail||'').substring(0,150)}</span></div>`;
        }
        html += '</div></div>';
        rd.innerHTML = html;
    },

    async _renderOutlines(mc) {
        mc.innerHTML = `<div class="page-header"><div><h1 class="page-title">📐 大纲管理</h1><p class="page-subtitle">查看和编辑各卷大纲</p></div></div><div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="oNovel" onchange="App._loadOutlines()"><option value="">-- 请选择 --</option></select></div></div><div id="oList" class="mt-16"></div></div>`;
        const resp = await API.listNovels();
        if (resp.success) {
            const sel = document.getElementById('oNovel');
            resp.novels.forEach(n => { const o = document.createElement('option'); o.value = n.name; o.textContent = n.title || n.name; sel.appendChild(o); });
            this._initNovelSelector('oNovel', function(){App._loadOutlines();});
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
        var ta = document.getElementById('outlineEdit');
        var modal = document.querySelector('.modal');
        var content = ta ? ta.value : (modal && modal._content ? modal._content : '');
        if (!content) { this.toast('无内容可保存', 'warning'); return; }
        if (modal) modal._content = content;
        const resp = await API.editOutline(novel, vol, content);
        resp.success ? (this.toast('✅ 大纲已保存', 'success'), document.querySelectorAll('.modal-overlay').forEach(m => m.remove()), this._loadOutlines()) : this.toast(resp.error, 'error');
    },

    // ═══════════════════════════════════════════════════════════════════
    //  QUALITY REPORT
    // ═══════════════════════════════════════════════════════════════════

    async _cleanupBak(novel) {
        if (!confirm('确认删除「' + novel + '」的所有 .bak 备份文件？此操作不可撤销。')) return;
        const resp = await fetch('/api/novels/' + encodeURIComponent(novel) + '/cleanup-bak', {method:'POST'}).then(function(r){return r.json();});
        resp.success ? this.toast('🗑 ' + resp.message + '，刷新后统计数据将更新', 'success') : this.toast(resp.error, 'error');
    },

    async _renderQuality(mc) {
        mc.innerHTML = '<div class="page-header"><div><h1 class="page-title">📈 质量报告</h1><p class="page-subtitle">写作质量趋势 · 审稿通过率 · 问题分布</p></div></div>' +
            '<div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="qNovel" onchange="App._loadQuality()"><option value="">-- 请选择 --</option></select></div></div><div id="qContent" class="mt-16"></div></div>';
        var resp = await API.listNovels();
        if (resp.success) {
            var sel = document.getElementById('qNovel');
            resp.novels.forEach(function(n) { var o = document.createElement('option'); o.value = n.name; o.textContent = n.title||n.name; sel.appendChild(o); });
            this._initNovelSelector('qNovel', function(){App._loadQuality();});
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
        const resp = await API.usageStats({ days: 7 });
        if (resp.success) {
            document.getElementById('statsDisplay').innerHTML = this._renderUsageStats(resp);
        } else {
            document.getElementById('statsDisplay').innerHTML = `<div class="code-block error">${resp.error || '加载失败'}</div>`;
        }
        btn.disabled = false; btn.textContent = '🔄 刷新统计';
    },

    _renderUsageStats(stats) {
        const totalTokens = stats.total_tokens || 0;
        const totalCost = stats.total_cost || 0;
        const totalCalls = Object.values(stats.by_operation || {}).reduce((s, op) => s + (op.calls || 0), 0);
        const days = stats.days || 7;

        // Top KPI cards: tokens / cost / calls / days
        let html = '<div class="stats-grid" style="grid-template-columns:repeat(4,1fr)">'
            + `<div class="stat-card"><div class="stat-value">${totalTokens.toLocaleString()}</div><div class="stat-label">总 Tokens</div></div>`
            + `<div class="stat-card"><div class="stat-value">$${totalCost.toFixed(4)}</div><div class="stat-label">总成本</div></div>`
            + `<div class="stat-card"><div class="stat-value">${totalCalls}</div><div class="stat-label">API 调用</div></div>`
            + `<div class="stat-card"><div class="stat-value">${days}</div><div class="stat-label">统计天数</div></div>`
            + '</div>';

        // By-operation table
        const opEntries = Object.entries(stats.by_operation || {}).sort((a, b) => b[1].tokens - a[1].tokens);
        if (opEntries.length) {
            html += '<div class="card mt-16"><h3 class="card-title">🔧 按操作类型</h3>'
                + '<table class="mt-8" style="width:100%;font-size:13px;border-collapse:collapse"><thead><tr style="color:var(--text-muted);text-align:left">'
                + '<th style="padding:6px 8px">操作</th><th style="padding:6px 8px">调用</th><th style="padding:6px 8px">Tokens</th><th style="padding:6px 8px">成本</th></tr></thead><tbody>';
            for (const [op, v] of opEntries) {
                html += `<tr style="border-top:1px solid var(--border-default)"><td style="padding:6px 8px">${op}</td><td style="padding:6px 8px">${v.calls}</td><td style="padding:6px 8px">${v.tokens.toLocaleString()}</td><td style="padding:6px 8px">$${(v.cost || 0).toFixed(4)}</td></tr>`;
            }
            html += '</tbody></table></div>';
        }

        // By-novel table
        const novelEntries = Object.entries(stats.by_novel || {}).sort((a, b) => b[1].tokens - a[1].tokens);
        if (novelEntries.length) {
            html += '<div class="card mt-16"><h3 class="card-title">📚 按小说</h3>'
                + '<table class="mt-8" style="width:100%;font-size:13px;border-collapse:collapse"><thead><tr style="color:var(--text-muted);text-align:left">'
                + '<th style="padding:6px 8px">小说</th><th style="padding:6px 8px">调用</th><th style="padding:6px 8px">Tokens</th><th style="padding:6px 8px">成本</th></tr></thead><tbody>';
            for (const [name, v] of novelEntries) {
                html += `<tr style="border-top:1px solid var(--border-default)"><td style="padding:6px 8px">${name}</td><td style="padding:6px 8px">${v.calls}</td><td style="padding:6px 8px">${v.tokens.toLocaleString()}</td><td style="padding:6px 8px">$${(v.cost || 0).toFixed(4)}</td></tr>`;
            }
            html += '</tbody></table></div>';
        }

        // Daily trend (last N days)
        const daily = stats.daily || [];
        if (daily.length) {
            const maxTokens = Math.max(...daily.map(d => d.tokens || 0), 1);
            html += `<div class="card mt-16"><h3 class="card-title">📈 最近 ${days} 天趋势</h3>`
                + '<div class="mt-8">';
            for (const d of daily) {
                const pct = Math.round(((d.tokens || 0) / maxTokens) * 100);
                html += `<div class="mt-8"><div class="progress-label"><span>${d.day}</span><span>${(d.tokens || 0).toLocaleString()} tokens · $${(d.cost || 0).toFixed(4)}</span></div>`
                    + `<div class="progress-bar"><div class="progress-bar-fill" style="width:${pct}%"></div></div></div>`;
            }
            html += '</div></div>';
        }

        // Empty state
        if (!opEntries.length && !novelEntries.length && !daily.length) {
            html += '<div class="code-block mt-8">暂无 token 用量记录。请先进行一次生成/审稿/优化等操作。</div>';
        }

        return html;
    },

    // ═══════════════════════════════════════════════════════════════════
    //  V3 MANAGEMENT: World Building
    // ═══════════════════════════════════════════════════════════════════

    async _renderWorldBuilding(mc) {
        mc.innerHTML = '<div class="page-header"><div><h1 class="page-title">🌍 世界观管理</h1><p class="page-subtitle">世界观条目 · 按领域分组 · 关联卷章</p></div></div>' +
            '<div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="wbNovel" onchange="App._loadWorldBuilding()"><option value="">-- 请选择 --</option></select></div></div>' +
            '<div class="flex gap-8 mt-12"><button class="btn btn-primary" onclick="App._initWorldBuilding()">🌱 从文件初始化</button><button class="btn btn-secondary" onclick="App._showAddWorldBuilding()">+ 添加条目</button></div>' +
            '<div id="wbList" class="mt-16"></div></div>';
        const resp = await API.listNovels();
        if (resp.success) { const sel = document.getElementById('wbNovel'); resp.novels.forEach(function(n) { const o = document.createElement('option'); o.value = n.name; o.textContent = n.title||n.name; sel.appendChild(o); }); this._initNovelSelector('wbNovel', function(){App._loadWorldBuilding();}); }
    },

    async _loadWorldBuilding() {
        const novel = document.getElementById('wbNovel').value;
        if (!novel) return;
        const ct = document.getElementById('wbList');
        ct.innerHTML = '<div class="loading"><div class="spinner sm"></div><span>加载中...</span></div>';
        const resp = await API.worldBuilding.list(novel);
        if (!resp.success) { ct.innerHTML = '<div class="code-block error">' + (resp.error||'') + '</div>'; return; }
        const items = resp.items || [];
        if (!items.length) { ct.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🌍</div><div class="empty-state-title">暂无世界观条目</div><div class="empty-state-desc">点击"从文件初始化"从 world_bible.md 导入，或手动添加</div></div>'; return; }
        // Build HTML table grouped by domain
        var html = '<div class="text-muted mb-12" style="font-size:12px">共 ' + items.length + ' 条</div>';
        var domains = {};
        items.forEach(function(item) { var d = item.domain || '其他'; if (!domains[d]) domains[d] = []; domains[d].push(item); });
        for (var domain in domains) {
            html += '<div class="card mb-16"><h3 class="card-title" style="font-size:14px;margin-bottom:10px">📂 ' + domain + ' (' + domains[domain].length + ')</h3>';
            html += '<div style="overflow-x:auto"><table class="wb-table" style="width:100%;border-collapse:collapse;font-size:13px">';
            html += '<thead><tr style="background:var(--bg-raised);text-align:left">';
            html += '<th style="padding:8px 12px;border-bottom:2px solid var(--border);min-width:100px">名称</th>';
            html += '<th style="padding:8px 12px;border-bottom:2px solid var(--border);min-width:200px">内容</th>';
            html += '<th style="padding:8px 12px;border-bottom:2px solid var(--border);min-width:80px">关联</th>';
            html += '<th style="padding:8px 12px;border-bottom:2px solid var(--border);min-width:100px">标签</th>';
            html += '<th style="padding:8px 12px;border-bottom:2px solid var(--border);width:70px">操作</th>';
            html += '</tr></thead><tbody>';
            domains[domain].forEach(function(item) {
                var ref = item.related_vol ? '卷' + item.related_vol + (item.related_ch ? ' 章' + item.related_ch : '') : '-';
                var tagsHtml = '';
                if (item.tags) { try { var tags = JSON.parse(item.tags); if (Array.isArray(tags)) tagsHtml = tags.map(function(t){ return '<span style="font-size:10px;padding:1px 6px;border-radius:8px;background:var(--accent-soft);color:var(--accent);margin:0 2px">' + t + '</span>'; }).join(''); } catch(e) {} }
                // Render content: convert markdown tables to HTML, plain text as-is
                var contentHtml = App._renderTableContent(item.content || '');
                html += '<tr style="border-bottom:1px solid var(--border-subtle)">';
                html += '<td style="padding:8px 12px;vertical-align:top"><strong>' + item.name + '</strong></td>';
                html += '<td style="padding:8px 12px;vertical-align:top">' + contentHtml + '</td>';
                html += '<td style="padding:8px 12px;vertical-align:top;color:var(--text-secondary);font-size:11px;white-space:nowrap">' + ref + '</td>';
                html += '<td style="padding:8px 12px;vertical-align:top">' + (tagsHtml || '-') + '</td>';
                html += '<td style="padding:8px 12px;vertical-align:top;white-space:nowrap"><button class="btn btn-sm btn-primary" onclick="App._editWorldBuilding(' + item.id + ')" style="margin-right:4px">✏️</button><button class="btn btn-sm btn-outline" onclick="App._deleteWorldBuilding(' + item.id + ')" style="color:var(--danger)">🗑</button></td>';
                html += '</tr>';
            });
            html += '</tbody></table></div></div>';
        }
        ct.innerHTML = html;
    },

    // Render content with markdown table → HTML table conversion
    _renderTableContent(text) {
        if (!text) return '';
        // Check if text contains a markdown table (| col | col | ... followed by | --- |)
        var lines = text.split('\n');
        var result = '';
        var i = 0;
        while (i < lines.length) {
            var line = lines[i].trim();
            // Detect markdown table start: line with | and next line with |---|
            if (line.startsWith('|') && line.endsWith('|') &&
                i + 1 < lines.length && lines[i+1].trim().match(/^\|[\s\-:|]+\|$/)) {
                // Collect all table rows
                var tableRows = [];
                tableRows.push(line); // header
                i++;
                tableRows.push(lines[i].trim()); // separator
                i++;
                while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
                    tableRows.push(lines[i].trim());
                    i++;
                }
                // Render as HTML table
                result += '<table style="width:100%;border-collapse:collapse;margin:6px 0;font-size:12px">';
                // Header row
                var headerCells = tableRows[0].split('|').filter(function(c) { return c.trim(); });
                result += '<thead><tr style="background:var(--bg-raised)">';
                headerCells.forEach(function(c) {
                    result += '<th style="padding:4px 8px;border:1px solid var(--border);text-align:left">' + c.trim() + '</th>';
                });
                result += '</tr></thead><tbody>';
                // Data rows (skip separator row at index 1)
                for (var j = 2; j < tableRows.length; j++) {
                    var cells = tableRows[j].split('|').filter(function(c) { return true; });
                    // Remove first and last empty if present
                    if (cells.length > 0 && cells[0].trim() === '') cells.shift();
                    if (cells.length > 0 && cells[cells.length-1].trim() === '') cells.pop();
                    result += '<tr>';
                    cells.forEach(function(c) {
                        result += '<td style="padding:4px 8px;border:1px solid var(--border-subtle)">' + c.trim() + '</td>';
                    });
                    result += '</tr>';
                }
                result += '</tbody></table>';
            } else if (line) {
                // Plain text line
                result += '<div style="margin:2px 0">' + line + '</div>';
            }
            i++;
        }
        return result || text;
    },

    async _initWorldBuilding() {
        const novel = document.getElementById('wbNovel').value;
        if (!novel) { this.toast('请选择小说', 'warning'); return; }
        const resp = await fetch('/api/novels/' + encodeURIComponent(novel) + '/world-building/init', {method:'POST'}).then(function(r){return r.json();});
        resp.success ? (this.toast('✅ ' + (resp.message||'初始化完成'), 'success'), this._loadWorldBuilding()) : this.toast(resp.error, 'error');
    },

    _showAddWorldBuilding(item) {
        const i = item || {};
        const body = '<div class="form-row"><div class="form-group"><label class="form-label">名称 *</label><input class="form-input" id="awbName" value="' + (i.name||'') + '"></div>' +
            '<div class="form-group"><label class="form-label">领域</label><input class="form-input" id="awbDomain" placeholder="如：地理/势力/魔法/历史" value="' + (i.domain||'') + '"></div></div>' +
            '<div class="form-group mt-8"><label class="form-label">内容</label><textarea class="form-textarea" id="awbContent" rows="4" placeholder="世界观设定描述...">' + (i.content||'') + '</textarea></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">关联卷</label><input class="form-input" id="awbVol" type="number" value="' + (i.related_vol||0) + '"></div>' +
            '<div class="form-group"><label class="form-label">关联章</label><input class="form-input" id="awbCh" type="number" value="' + (i.related_ch||0) + '"></div></div>' +
            '<div class="form-group mt-8"><label class="form-label">标签 (逗号分隔)</label><input class="form-input" id="awbTags" placeholder="如：核心设定,后期揭示" value="' + (Array.isArray(i.tags) ? i.tags.join(', ') : (typeof i.tags === 'string' ? i.tags : '')) + '"></div>';
        const footer = '<button class="btn btn-primary" onclick="App._saveWorldBuilding(' + (i.id||0) + ')">💾 保存</button><button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">取消</button>';
        this.modal((i.id ? '✏️ 编辑' : '+ 添加') + ' 世界观条目', body, footer, '550px');
    },

    async _editWorldBuilding(id) {
        const novel = document.getElementById('wbNovel').value;
        const resp = await API.worldBuilding.list(novel);
        if (!resp.success) return;
        const item = (resp.items||[]).find(function(x){return x.id === id;});
        if (!item) { this.toast('未找到条目', 'error'); return; }
        this._showAddWorldBuilding(item);
    },

    async _saveWorldBuilding(id) {
        const novel = document.getElementById('wbNovel').value;
        var g = function(id) { var el = document.getElementById(id); return el ? el.value : ''; };
        var tagsRaw = g('awbTags');
        var tags = null;
        if (tagsRaw.trim()) tags = tagsRaw.split(',').map(function(s){return s.trim();}).filter(function(s){return s;});
        const data = {
            name: g('awbName'), domain: g('awbDomain'), content: g('awbContent'),
            related_vol: parseInt(g('awbVol'))||0, related_ch: parseInt(g('awbCh'))||0,
            tags: tags,
        };
        if (!data.name) { this.toast('请填写名称', 'warning'); return; }
        const resp = id ? await API.worldBuilding.update(novel, id, data) : await API.worldBuilding.create(novel, data);
        resp.success ? (this.toast('✅ 已保存', 'success'), document.querySelectorAll('.modal-overlay').forEach(function(m){m.remove();}), this._loadWorldBuilding()) : this.toast(resp.error, 'error');
    },

    async _deleteWorldBuilding(id) {
        if (!await this.confirm('确认删除', '确定要删除这个世界观条目吗？此操作不可撤销。')) return;
        const novel = document.getElementById('wbNovel').value;
        const resp = await API.worldBuilding.delete(novel, id);
        resp.success ? (this.toast('✅ 已删除', 'success'), this._loadWorldBuilding()) : this.toast(resp.error, 'error');
    },

    // ═══════════════════════════════════════════════════════════════════
    //  V3 MANAGEMENT: Plot Arcs
    // ═══════════════════════════════════════════════════════════════════

    async _renderPlotArcs(mc) {
        mc.innerHTML = '<div class="page-header"><div><h1 class="page-title">📐 剧情弧线</h1><p class="page-subtitle">多线剧情管理 · 主线/支线 · 里程碑追踪</p></div></div>' +
            '<div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="paNovel" onchange="App._loadPlotArcs()"><option value="">-- 请选择 --</option></select></div></div>' +
            '<div class="flex gap-8 mt-12"><button class="btn btn-primary" onclick="App._initPlotArcs()">🌱 从文件初始化</button><button class="btn btn-secondary" onclick="App._showAddPlotArc()">+ 添加弧线</button></div>' +
            '<div id="paList" class="mt-16"></div></div>';
        const resp = await API.listNovels();
        if (resp.success) { const sel = document.getElementById('paNovel'); resp.novels.forEach(function(n) { const o = document.createElement('option'); o.value = n.name; o.textContent = n.title||n.name; sel.appendChild(o); }); this._initNovelSelector('paNovel', function(){App._loadPlotArcs();}); }
    },

    async _loadPlotArcs() {
        const novel = document.getElementById('paNovel').value;
        if (!novel) return;
        const ct = document.getElementById('paList');
        ct.innerHTML = '<div class="loading"><div class="spinner sm"></div><span>加载中...</span></div>';
        const resp = await API.plotArcs.list(novel);
        if (!resp.success) { ct.innerHTML = '<div class="code-block error">' + (resp.error||'') + '</div>'; return; }
        const items = resp.items || [];
        if (!items.length) { ct.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📐</div><div class="empty-state-title">暂无剧情弧线</div><div class="empty-state-desc">点击"从文件初始化"从 full_story_arc.md 导入，或手动添加</div></div>'; return; }
        var typeColors = {'主线':'var(--accent)', '支线':'var(--info)', '伏笔':'var(--warning)', '反派线':'var(--danger)', '感情线':'#e91e63'};
        var statusColors = {'active':'var(--success)','completed':'var(--text-tertiary)','planned':'var(--warning)','paused':'var(--text-quaternary)'};
        var html = '<div class="text-muted mb-8" style="font-size:12px">共 ' + items.length + ' 条弧线</div><div style="display:grid;gap:8px">';
        items.forEach(function(item) {
            var range = '';
            if (item.volume_start) {
                range = '第' + item.volume_start + '卷';
                if (item.chapter_start) range += '第' + item.chapter_start + '章';
                if (item.volume_end) { range += ' → 第' + item.volume_end + '卷'; if (item.chapter_end) range += '第' + item.chapter_end + '章'; }
            }
            var milestones = [];
            try { if (item.milestones && item.milestones !== '[]') milestones = JSON.parse(item.milestones); } catch(e) {}
            var milestoneHtml = '';
            if (milestones.length > 0) milestoneHtml = '<div class="mt-4" style="font-size:11px;color:var(--text-tertiary)">📌 ' + milestones.map(function(m){ return typeof m === 'string' ? m : (m.label||m.title||''); }).filter(function(x){return x;}).join(' → ') + '</div>';
            html += '<div class="card" style="border-left:3px solid ' + (typeColors[item.type]||'var(--text-secondary)') + '"><div style="display:flex;justify-content:space-between;align-items:start;gap:8px"><div style="flex:1">' +
                '<div style="display:flex;align-items:center;gap:8px"><strong style="font-size:15px">' + item.name + '</strong>' +
                '<span style="font-size:10px;padding:1px 6px;border-radius:8px;background:' + (typeColors[item.type]||'#888') + ';color:#fff">' + (item.type||'主线') + '</span>' +
                '<span style="font-size:10px;padding:1px 6px;border-radius:8px;background:' + (statusColors[item.status] || 'var(--text-quaternary)') + ';color:#fff;opacity:0.8">' + (item.status||'active') + '</span></div>' +
                (range ? '<div class="text-muted mt-2" style="font-size:11px">📖 ' + range + '</div>' : '') +
                (item.summary ? '<div class="text-secondary mt-2" style="font-size:12px">' + item.summary.substring(0, 200) + '</div>' : '') +
                milestoneHtml +
                '</div><div class="flex gap-4" style="flex-shrink:0"><button class="btn btn-sm btn-primary" onclick="App._editPlotArc(' + item.id + ')">✏️</button><button class="btn btn-sm btn-outline" onclick="App._deletePlotArc(' + item.id + ')" style="color:var(--danger)">🗑</button></div></div></div>';
        });
        html += '</div>';
        ct.innerHTML = html;
    },

    async _initPlotArcs() {
        const novel = document.getElementById('paNovel').value;
        if (!novel) { this.toast('请选择小说', 'warning'); return; }
        const resp = await fetch('/api/novels/' + encodeURIComponent(novel) + '/plot-arcs/init', {method:'POST'}).then(function(r){return r.json();});
        resp.success ? (this.toast('✅ ' + (resp.message||'初始化完成'), 'success'), this._loadPlotArcs()) : this.toast(resp.error, 'error');
    },

    _showAddPlotArc(item) {
        const i = item || {};
        const body = '<div class="form-row"><div class="form-group"><label class="form-label">名称 *</label><input class="form-input" id="apaName" value="' + (i.name||'') + '"></div>' +
            '<div class="form-group"><label class="form-label">类型</label><select class="form-select" id="apaType"><option>主线</option><option>支线</option><option>伏笔</option><option>反派线</option><option>感情线</option></select></div></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">起始卷</label><input class="form-input" id="apaVStart" type="number" value="' + (i.volume_start||0) + '"></div>' +
            '<div class="form-group"><label class="form-label">起始章</label><input class="form-input" id="apaChStart" type="number" value="' + (i.chapter_start||0) + '"></div></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">结束卷</label><input class="form-input" id="apaVEnd" type="number" value="' + (i.volume_end||0) + '"></div>' +
            '<div class="form-group"><label class="form-label">结束章</label><input class="form-input" id="apaChEnd" type="number" value="' + (i.chapter_end||0) + '"></div></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">状态</label><select class="form-select" id="apaStatus"><option>active</option><option>planned</option><option>completed</option><option>paused</option></select></div>' +
            '<div class="form-group"><label class="form-label">优先级</label><select class="form-select" id="apaPriority"><option>normal</option><option>high</option><option>low</option></select></div></div>' +
            '<div class="form-group mt-8"><label class="form-label">摘要</label><textarea class="form-textarea" id="apaSummary" rows="3" placeholder="剧情弧线概述...">' + (i.summary||'') + '</textarea></div>' +
            '<div class="form-group mt-8"><label class="form-label">里程碑 (JSON数组)</label><textarea class="form-textarea" id="apaMilestones" rows="3" placeholder=\'["起","承","转","合"]\'>' + (typeof i.milestones === 'string' ? i.milestones : JSON.stringify(i.milestones||[])) + '</textarea></div>';
        const footer = '<button class="btn btn-primary" onclick="App._savePlotArc(' + (i.id||0) + ')">💾 保存</button><button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">取消</button>';
        this.modal((i.id ? '✏️ 编辑' : '+ 添加') + ' 剧情弧线', body, footer, '580px');
        if (i.type) document.getElementById('apaType').value = i.type;
        if (i.status) document.getElementById('apaStatus').value = i.status;
        if (i.priority) document.getElementById('apaPriority').value = i.priority;
    },

    async _editPlotArc(id) {
        const novel = document.getElementById('paNovel').value;
        const resp = await API.plotArcs.list(novel);
        if (!resp.success) return;
        const item = (resp.items||[]).find(function(x){return x.id === id;});
        if (!item) { this.toast('未找到弧线', 'error'); return; }
        this._showAddPlotArc(item);
    },

    async _savePlotArc(id) {
        const novel = document.getElementById('paNovel').value;
        var g = function(id) { var el = document.getElementById(id); return el ? el.value : ''; };
        var milestones = [];
        var mRaw = g('apaMilestones');
        try { if (mRaw.trim()) milestones = JSON.parse(mRaw); } catch(e) { milestones = mRaw.split(',').map(function(s){return s.trim();}).filter(function(s){return s;}); }
        const data = {
            name: g('apaName'), type: g('apaType'),
            volume_start: parseInt(g('apaVStart'))||0, chapter_start: parseInt(g('apaChStart'))||0,
            volume_end: parseInt(g('apaVEnd'))||0, chapter_end: parseInt(g('apaChEnd'))||0,
            summary: g('apaSummary'), milestones: milestones,
            status: g('apaStatus'), priority: g('apaPriority'),
        };
        if (!data.name) { this.toast('请填写名称', 'warning'); return; }
        const resp = id ? await API.plotArcs.update(novel, id, data) : await API.plotArcs.create(novel, data);
        resp.success ? (this.toast('✅ 已保存', 'success'), document.querySelectorAll('.modal-overlay').forEach(function(m){m.remove();}), this._loadPlotArcs()) : this.toast(resp.error, 'error');
    },

    async _deletePlotArc(id) {
        if (!await this.confirm('确认删除', '确定要删除这条剧情弧线吗？')) return;
        const novel = document.getElementById('paNovel').value;
        const resp = await API.plotArcs.delete(novel, id);
        resp.success ? (this.toast('✅ 已删除', 'success'), this._loadPlotArcs()) : this.toast(resp.error, 'error');
    },

    // ═══════════════════════════════════════════════════════════════════
    //  V3 MANAGEMENT: Pacing Control
    // ═══════════════════════════════════════════════════════════════════

    async _renderPacing(mc) {
        mc.innerHTML = '<div class="page-header"><div><h1 class="page-title">🎵 节奏控制</h1><p class="page-subtitle">卷章节奏 · 强度管理 · 情绪目标</p></div></div>' +
            '<div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="pcNovel" onchange="App._loadPacing()"><option value="">-- 请选择 --</option></select></div></div>' +
            '<div class="flex gap-8 mt-12"><button class="btn btn-primary" onclick="App._initPacing()">🌱 从大纲初始化</button><button class="btn btn-secondary" onclick="App._showAddPacing()">+ 添加节奏</button></div>' +
            '<div id="pcList" class="mt-16"></div></div>';
        const resp = await API.listNovels();
        if (resp.success) { const sel = document.getElementById('pcNovel'); resp.novels.forEach(function(n) { const o = document.createElement('option'); o.value = n.name; o.textContent = n.title||n.name; sel.appendChild(o); }); this._initNovelSelector('pcNovel', function(){App._loadPacing();}); }
    },

    async _loadPacing() {
        const novel = document.getElementById('pcNovel').value;
        if (!novel) return;
        const ct = document.getElementById('pcList');
        ct.innerHTML = '<div class="loading"><div class="spinner sm"></div><span>加载中...</span></div>';
        const resp = await API.pacingControl.list(novel);
        if (!resp.success) { ct.innerHTML = '<div class="code-block error">' + (resp.error||'') + '</div>'; return; }
        const items = resp.items || [];
        if (!items.length) { ct.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🎵</div><div class="empty-state-title">暂无节奏控制条目</div><div class="empty-state-desc">点击"从大纲初始化"解析大纲中的节奏信息，或手动添加</div></div>'; return; }
        var paceColors = {'高潮':'var(--danger)','铺垫':'var(--info)','过渡':'var(--text-secondary)','日常':'var(--success)','反转':'var(--warning)','战斗':'#e91e63'};
        var html = '<div class="text-muted mb-8" style="font-size:12px">共 ' + items.length + ' 条节奏 · 按卷排序</div><div style="display:grid;gap:8px">';
        items.sort(function(a,b){ return (a.volume - b.volume) || (a.chapter_start - b.chapter_start); });
        items.forEach(function(item) {
            var range = 'Vol.' + item.volume + ' · Ch.' + item.chapter_start + (item.chapter_end && item.chapter_end !== item.chapter_start ? '~' + item.chapter_end : '');
            var intensityBars = '';
            for (var i = 0; i < 10; i++) intensityBars += '<span style="display:inline-block;width:14px;height:4px;border-radius:2px;margin-right:2px;background:' + (i < (item.intensity||5) ? (item.intensity >= 8 ? 'var(--danger)' : item.intensity >= 5 ? 'var(--warning)' : 'var(--success)') : 'var(--border-default)') + '"></span>';
            html += '<div class="card" style="padding:10px 14px"><div style="display:flex;justify-content:space-between;align-items:start;gap:8px"><div style="flex:1">' +
                '<div style="display:flex;align-items:center;gap:8px"><strong style="font-size:14px">' + range + '</strong>' +
                '<span style="font-size:10px;padding:1px 6px;border-radius:8px;background:' + (paceColors[item.pace_type]||'var(--text-secondary)') + ';color:#fff">' + (item.pace_type||'过渡') + '</span></div>' +
                '<div class="mt-4">' + intensityBars + ' <span class="text-muted" style="font-size:11px">' + (item.intensity||5) + '/10</span></div>' +
                (item.emotion_target ? '<div class="mt-2" style="font-size:12px;color:var(--text-secondary)">🎯 ' + item.emotion_target.substring(0, 80) + '</div>' : '') +
                (item.notes ? '<div class="mt-2" style="font-size:11px;color:var(--text-tertiary)">📝 ' + item.notes.substring(0, 120) + '</div>' : '') +
                '</div><div class="flex gap-4" style="flex-shrink:0"><button class="btn btn-sm btn-primary" onclick="App._editPacing(' + item.id + ')">✏️</button><button class="btn btn-sm btn-outline" onclick="App._deletePacing(' + item.id + ')" style="color:var(--danger)">🗑</button></div></div></div>';
        });
        html += '</div>';
        ct.innerHTML = html;
    },

    async _initPacing() {
        const novel = document.getElementById('pcNovel').value;
        if (!novel) { this.toast('请选择小说', 'warning'); return; }
        const resp = await fetch('/api/novels/' + encodeURIComponent(novel) + '/pacing/init', {method:'POST'}).then(function(r){return r.json();});
        resp.success ? (this.toast('✅ ' + (resp.message||'初始化完成'), 'success'), this._loadPacing()) : this.toast(resp.error, 'error');
    },

    _showAddPacing(item) {
        const i = item || {};
        const body = '<div class="form-row"><div class="form-group"><label class="form-label">卷 *</label><input class="form-input" id="apcVol" type="number" value="' + (i.volume||1) + '"></div>' +
            '<div class="form-group"><label class="form-label">起始章</label><input class="form-input" id="apcChStart" type="number" value="' + (i.chapter_start||0) + '"></div>' +
            '<div class="form-group"><label class="form-label">结束章</label><input class="form-input" id="apcChEnd" type="number" value="' + (i.chapter_end||0) + '"></div></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">节奏类型</label><select class="form-select" id="apcType"><option>过渡</option><option>高潮</option><option>铺垫</option><option>日常</option><option>反转</option><option>战斗</option></select></div>' +
            '<div class="form-group"><label class="form-label">强度 (1-10)</label><input class="form-input" id="apcIntensity" type="number" min="1" max="10" value="' + (i.intensity||5) + '"></div></div>' +
            '<div class="form-group mt-8"><label class="form-label">情绪目标</label><input class="form-input" id="apcEmotion" placeholder="如：紧张、温暖、悲伤" value="' + (i.emotion_target||'') + '"></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">字数下限</label><input class="form-input" id="apcWMin" type="number" value="' + (i.word_budget_min||2500) + '"></div>' +
            '<div class="form-group"><label class="form-label">字数上限</label><input class="form-input" id="apcWMax" type="number" value="' + (i.word_budget_max||3500) + '"></div></div>' +
            '<div class="form-group mt-8"><label class="form-label">备注</label><textarea class="form-textarea" id="apcNotes" rows="2" placeholder="额外说明...">' + (i.notes||'') + '</textarea></div>';
        const footer = '<button class="btn btn-primary" onclick="App._savePacing(' + (i.id||0) + ')">💾 保存</button><button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">取消</button>';
        this.modal((i.id ? '✏️ 编辑' : '+ 添加') + ' 节奏控制', body, footer, '520px');
        if (i.pace_type) document.getElementById('apcType').value = i.pace_type;
    },

    async _editPacing(id) {
        const novel = document.getElementById('pcNovel').value;
        const resp = await API.pacingControl.list(novel);
        if (!resp.success) return;
        const item = (resp.items||[]).find(function(x){return x.id === id;});
        if (!item) { this.toast('未找到节奏条目', 'error'); return; }
        this._showAddPacing(item);
    },

    async _savePacing(id) {
        const novel = document.getElementById('pcNovel').value;
        var g = function(id) { var el = document.getElementById(id); return el ? el.value : ''; };
        const data = {
            volume: parseInt(g('apcVol'))||0, chapter_start: parseInt(g('apcChStart'))||0, chapter_end: parseInt(g('apcChEnd'))||0,
            pace_type: g('apcType'), intensity: parseInt(g('apcIntensity'))||5,
            emotion_target: g('apcEmotion'),
            word_budget_min: parseInt(g('apcWMin'))||2500, word_budget_max: parseInt(g('apcWMax'))||3500,
            notes: g('apcNotes'),
        };
        if (!data.volume) { this.toast('请填写卷号', 'warning'); return; }
        const resp = id ? await API.pacingControl.update(novel, id, data) : await API.pacingControl.create(novel, data);
        resp.success ? (this.toast('✅ 已保存', 'success'), document.querySelectorAll('.modal-overlay').forEach(function(m){m.remove();}), this._loadPacing()) : this.toast(resp.error, 'error');
    },

    async _deletePacing(id) {
        if (!await this.confirm('确认删除', '确定要删除这条节奏记录吗？')) return;
        const novel = document.getElementById('pcNovel').value;
        const resp = await API.pacingControl.delete(novel, id);
        resp.success ? (this.toast('✅ 已删除', 'success'), this._loadPacing()) : this.toast(resp.error, 'error');
    },

    // ═══════════════════════════════════════════════════════════════════
    //  V3 MANAGEMENT: Revelation Schedule
    // ═══════════════════════════════════════════════════════════════════

    async _renderRevelation(mc) {
        mc.innerHTML = '<div class="page-header"><div><h1 class="page-title">🔓 信息释放</h1><p class="page-subtitle">信息点时间线 · 读者/主角认知差 · 悬念管理</p></div></div>' +
            '<div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="rsNovel" onchange="App._loadRevelation()"><option value="">-- 请选择 --</option></select></div></div>' +
            '<div class="flex gap-8 mt-12"><button class="btn btn-primary" onclick="App._initRevelation()">🌱 从大纲初始化</button><button class="btn btn-secondary" onclick="App._showAddRevelation()">+ 添加信息点</button></div>' +
            '<div id="rsList" class="mt-16"></div></div>';
        const resp = await API.listNovels();
        if (resp.success) { const sel = document.getElementById('rsNovel'); resp.novels.forEach(function(n) { const o = document.createElement('option'); o.value = n.name; o.textContent = n.title||n.name; sel.appendChild(o); }); this._initNovelSelector('rsNovel', function(){App._loadRevelation();}); }
    },

    async _loadRevelation() {
        const novel = document.getElementById('rsNovel').value;
        if (!novel) return;
        const ct = document.getElementById('rsList');
        ct.innerHTML = '<div class="loading"><div class="spinner sm"></div><span>加载中...</span></div>';
        const resp = await API.revelationSchedule.list(novel);
        if (!resp.success) { ct.innerHTML = '<div class="code-block error">' + (resp.error||'') + '</div>'; return; }
        const items = resp.items || [];
        if (!items.length) { ct.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔓</div><div class="empty-state-title">暂无信息释放计划</div><div class="empty-state-desc">点击"从大纲初始化"解析大纲中的信息点，或手动添加</div></div>'; return; }
        items.sort(function(a,b){ return (a.reveal_volume - b.reveal_volume) || (a.reveal_chapter - b.reveal_chapter); });
        var typeColors = {'世界观':'var(--accent)','角色':'#e91e63','剧情':'var(--warning)','伏笔':'var(--info)','反转':'var(--danger)'};
        var priorityColors = {'high':'var(--danger)','normal':'var(--info)','low':'var(--text-tertiary)'};
        var html = '<div class="text-muted mb-8" style="font-size:12px">共 ' + items.length + ' 个信息点 · 按释放时间排序</div><div style="display:grid;gap:8px">';
        items.forEach(function(item) {
            var reveaLoc = '第' + (item.reveal_volume||'?') + '卷';
            if (item.reveal_chapter) reveaLoc += ' 第' + item.reveal_chapter + '章';
            var audIcon = item.audience_knows ? '✅' : '❓';
            var protIcon = item.protagonist_knows ? '✅' : '❓';
            html += '<div class="card" style="padding:10px 14px;border-left:3px solid ' + (typeColors[item.info_type]||'var(--text-secondary)') + '"><div style="display:flex;justify-content:space-between;align-items:start;gap:8px"><div style="flex:1">' +
                '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap"><strong style="font-size:14px">' + item.name + '</strong>' +
                '<span style="font-size:10px;padding:1px 6px;border-radius:8px;background:' + (typeColors[item.info_type]||'#888') + ';color:#fff">' + (item.info_type||'世界观') + '</span>' +
                '<span style="font-size:10px;padding:1px 6px;border-radius:8px;background:' + (priorityColors[item.priority]||'#888') + ';color:#fff;opacity:0.8">' + (item.priority||'normal') + '</span>' +
                '<span class="text-muted" style="font-size:11px">📍 ' + reveaLoc + '</span></div>' +
                (item.content ? '<div class="text-secondary mt-2" style="font-size:12px">' + item.content.substring(0, 180) + '</div>' : '') +
                '<div class="mt-4" style="display:flex;gap:12px;font-size:11px">' +
                '<span title="读者已知">👁 读者: ' + audIcon + '</span>' +
                '<span title="主角已知">🎭 主角: ' + protIcon + '</span>' +
                '</div></div>' +
                '<div class="flex gap-4" style="flex-shrink:0"><button class="btn btn-sm btn-primary" onclick="App._editRevelation(' + item.id + ')">✏️</button><button class="btn btn-sm btn-outline" onclick="App._deleteRevelation(' + item.id + ')" style="color:var(--danger)">🗑</button></div></div></div>';
        });
        html += '</div>';
        ct.innerHTML = html;
    },

    async _initRevelation() {
        const novel = document.getElementById('rsNovel').value;
        if (!novel) { this.toast('请选择小说', 'warning'); return; }
        const resp = await fetch('/api/novels/' + encodeURIComponent(novel) + '/revelation/init', {method:'POST'}).then(function(r){return r.json();});
        resp.success ? (this.toast('✅ ' + (resp.message||'初始化完成'), 'success'), this._loadRevelation()) : this.toast(resp.error, 'error');
    },

    _showAddRevelation(item) {
        const i = item || {};
        const body = '<div class="form-row"><div class="form-group"><label class="form-label">名称 *</label><input class="form-input" id="arsName" value="' + (i.name||'') + '"></div>' +
            '<div class="form-group"><label class="form-label">类型</label><select class="form-select" id="arsType"><option>世界观</option><option>角色</option><option>剧情</option><option>伏笔</option><option>反转</option></select></div></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">释放卷</label><input class="form-input" id="arsVol" type="number" value="' + (i.reveal_volume||1) + '"></div>' +
            '<div class="form-group"><label class="form-label">释放章</label><input class="form-input" id="arsCh" type="number" value="' + (i.reveal_chapter||0) + '"></div>' +
            '<div class="form-group"><label class="form-label">优先级</label><select class="form-select" id="arsPriority"><option>normal</option><option>high</option><option>low</option></select></div></div>' +
            '<div class="form-group mt-8"><label class="form-label">内容</label><textarea class="form-textarea" id="arsContent" rows="3" placeholder="要揭示的具体信息...">' + (i.content||'') + '</textarea></div>' +
            '<div class="form-row mt-8"><div class="form-group"><label class="form-label">读者已知</label><select class="form-select" id="arsAudKnows"><option value="0">❓ 未揭露</option><option value="1">✅ 已揭露</option></select></div>' +
            '<div class="form-group"><label class="form-label">主角已知</label><select class="form-select" id="arsProtKnows"><option value="0">❓ 未揭露</option><option value="1">✅ 已揭露</option></select></div></div>';
        const footer = '<button class="btn btn-primary" onclick="App._saveRevelation(' + (i.id||0) + ')">💾 保存</button><button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">取消</button>';
        this.modal((i.id ? '✏️ 编辑' : '+ 添加') + ' 信息释放点', body, footer, '550px');
        if (i.info_type) document.getElementById('arsType').value = i.info_type;
        if (i.priority) document.getElementById('arsPriority').value = i.priority;
        if (i.audience_knows !== undefined) document.getElementById('arsAudKnows').value = i.audience_knows;
        if (i.protagonist_knows !== undefined) document.getElementById('arsProtKnows').value = i.protagonist_knows;
    },

    async _editRevelation(id) {
        const novel = document.getElementById('rsNovel').value;
        const resp = await API.revelationSchedule.list(novel);
        if (!resp.success) return;
        const item = (resp.items||[]).find(function(x){return x.id === id;});
        if (!item) { this.toast('未找到信息点', 'error'); return; }
        this._showAddRevelation(item);
    },

    async _saveRevelation(id) {
        const novel = document.getElementById('rsNovel').value;
        var g = function(id) { var el = document.getElementById(id); return el ? el.value : ''; };
        const data = {
            name: g('arsName'), info_type: g('arsType'),
            reveal_volume: parseInt(g('arsVol'))||0, reveal_chapter: parseInt(g('arsCh'))||0,
            content: g('arsContent'), priority: g('arsPriority'),
            audience_knows: parseInt(g('arsAudKnows'))||0, protagonist_knows: parseInt(g('arsProtKnows'))||0,
        };
        if (!data.name) { this.toast('请填写名称', 'warning'); return; }
        const resp = id ? await API.revelationSchedule.update(novel, id, data) : await API.revelationSchedule.create(novel, data);
        resp.success ? (this.toast('✅ 已保存', 'success'), document.querySelectorAll('.modal-overlay').forEach(function(m){m.remove();}), this._loadRevelation()) : this.toast(resp.error, 'error');
    },

    async _deleteRevelation(id) {
        if (!await this.confirm('确认删除', '确定要删除这个信息释放点吗？')) return;
        const novel = document.getElementById('rsNovel').value;
        const resp = await API.revelationSchedule.delete(novel, id);
        resp.success ? (this.toast('✅ 已删除', 'success'), this._loadRevelation()) : this.toast(resp.error, 'error');
    },

    // ═══════════════════════════════════════════════════════════════════
    //  New Domain Pages
    // ═══════════════════════════════════════════════════════════════════

    async _renderGenreRules(mc) {
        await this._renderTablePage(mc, '📜 类型规则', 'genre_rules', 'genre_rules',
            ['规则类别', '规则内容'], ['rule_category', 'rule_content']);
    },
    async _renderStoryVolumes(mc) {
        await this._renderTablePage(mc, '📚 分卷结构', 'story_volumes', 'story_volumes',
            ['卷', '名称', '字数', '目标', '冲突', '回报', '伏笔', '状态'],
            ['vol_num', 'vol_name', 'word_range', 'goal', 'conflict', 'payoff', 'foreshadowing', 'status']);
    },
    async _renderVolumePlans(mc) {
        mc.innerHTML = '<div class="page-header"><h1 class="page-title">📋 卷规划</h1><p class="page-subtitle">各卷详细规划 · 从 volume_plan/ 目录导入</p></div>' +
            '<div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="vpNovel" onchange="App._loadVolumePlans()"><option value="">-- 请选择 --</option></select></div></div>' +
            '<div id="vpList" class="mt-16"></div></div>';
        const resp = await API.listNovels();
        if (resp.success) { const sel = document.getElementById('vpNovel'); resp.novels.forEach(function(n) { const o = document.createElement('option'); o.value = n.name; o.textContent = n.title||n.name; sel.appendChild(o); }); this._initNovelSelector('vpNovel', function(){App._loadVolumePlans();}); }
    },
    async _loadVolumePlans() {
        const novel = document.getElementById('vpNovel').value;
        if (!novel) return;
        const ct = document.getElementById('vpList');
        ct.innerHTML = '<div class="loading"><div class="spinner sm"></div></div>';
        const resp = await fetch('/api/volume_plans/' + encodeURIComponent(novel)).then(r => r.json());
        if (!resp.success) { ct.innerHTML = '<div class="code-block error">' + (resp.error||'') + '</div>'; return; }
        var html = '<div class="text-muted mb-8">共 ' + resp.total + ' 卷</div>';
        resp.items.forEach(function(item) {
            html += '<div class="card mb-8"><h3 style="font-size:14px">📖 第' + item.vol_num + '卷' + (item.title ? ': ' + item.title : '') + '</h3>' +
                '<div class="text-muted" style="font-size:11px">' + item.word_count + ' 字</div></div>';
        });
        ct.innerHTML = html;
    },
    async _renderAliasNames(mc) {
        await this._renderTablePage(mc, '🏷️ 别名表', 'alias_names', 'alias_names',
            ['类别', '别名', '说明', '使用范围', '首次章'], ['category', 'alias_name', 'description', 'scope', 'first_chapter']);
    },
    async _renderProjectMeta(mc) {
        await this._renderTablePage(mc, '📋 项目元数据', 'project_meta', 'project_meta',
            ['键', '值'], ['meta_key', 'meta_value']);
    },

    // Generic table page renderer
    async _renderTablePage(mc, title, apiPath, apiMethod, cols, keys) {
        mc.innerHTML = '<div class="page-header"><h1 class="page-title">' + title + '</h1><p class="page-subtitle">从数据库读取</p></div>' +
            '<div class="card"><div class="form-row"><div class="form-group"><label class="form-label">选择小说</label><select class="form-select" id="gtNovel" onchange="App._loadTablePage(\'' + apiPath + '\',\'' + JSON.stringify(cols).replace(/"/g,'&quot;') + '\',\'' + JSON.stringify(keys).replace(/"/g,'&quot;') + '\')"><option value="">-- 请选择 --</option></select></div></div>' +
            '<div id="gtList" class="mt-16"></div></div>';
        const resp = await API.listNovels();
        if (resp.success) { const sel = document.getElementById('gtNovel'); resp.novels.forEach(function(n) { const o = document.createElement('option'); o.value = n.name; o.textContent = n.title||n.name; sel.appendChild(o); }); }
    },

    async _loadTablePage(apiPath, colsJson, keysJson) {
        const novel = document.getElementById('gtNovel').value;
        if (!novel) return;
        const cols = JSON.parse(colsJson);
        const keys = JSON.parse(keysJson);
        const ct = document.getElementById('gtList');
        ct.innerHTML = '<div class="loading"><div class="spinner sm"></div></div>';
        const resp = await fetch('/api/' + apiPath + '/' + encodeURIComponent(novel)).then(r => r.json());
        if (!resp.success) { ct.innerHTML = '<div class="code-block error">' + (resp.error||'') + '</div>'; return; }
        if (!resp.total) { ct.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-title">暂无数据</div></div>'; return; }
        var html = '<div class="text-muted mb-8" style="font-size:12px">共 ' + resp.total + ' 条</div>';
        html += '<div style="overflow-x:auto"><table class="wb-table" style="width:100%;border-collapse:collapse;font-size:13px">';
        html += '<thead><tr style="background:var(--bg-raised);text-align:left">';
        cols.forEach(function(c) { html += '<th style="padding:8px 12px;border-bottom:2px solid var(--border)">' + c + '</th>'; });
        html += '</tr></thead><tbody>';
        resp.items.forEach(function(item) {
            html += '<tr style="border-bottom:1px solid var(--border-subtle)">';
            keys.forEach(function(k) {
                var v = item[k];
                if (v === null || v === undefined) v = '-';
                else if (typeof v === 'number' && k === 'vol_num') v = '第' + v + '卷';
                html += '<td style="padding:6px 12px;vertical-align:top">' + v + '</td>';
            });
            html += '</tr>';
        });
        html += '</tbody></table></div>';
        ct.innerHTML = html;
    },

};

document.addEventListener('DOMContentLoaded', () => App.init());