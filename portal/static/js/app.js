/* ─── Novel Agent Web Portal - Main App ─────────────────────────────── */

const App = {
    currentView: 'dashboard',
    currentNovel: null,
    novels: [],
    config: {},

    // ── Initialization ──
    async init() {
        // Load config
        const cfgResp = await API.getConfig();
        if (cfgResp.success) {
            this.config = cfgResp;
            const dot = document.getElementById('configStatus');
            if (cfgResp.deepseek_configured) {
                dot.innerHTML = '<span class="status-dot green"></span> DeepSeek 已连接';
            } else {
                dot.innerHTML = '<span class="status-dot orange"></span> 需配置 API Key';
            }
        }

        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const view = item.dataset.view;
                this.navigate(view);
            });
        });

        // Load initial view
        await this.navigate('dashboard');
    },

    async navigate(view, params = {}) {
        this.currentView = view;
        // Update nav
        document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.view === view));
        const mc = document.getElementById('mainContent');
        mc.innerHTML = '<div class="loading"><div class="spinner"></div><span>加载中...</span></div>';

        try {
            switch (view) {
                case 'dashboard': await this.renderDashboard(mc); break;
                case 'novels': await this.renderNovels(mc); break;
                case 'new-book': await this.renderNewBook(mc); break;
                case 'writing': await this.renderWriting(mc, params); break;
                case 'review': await this.renderReview(mc, params); break;
                case 'settings': await this.renderSettings(mc); break;
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
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        const el = document.createElement('div');
        el.className = `toast toast-${type}`;
        el.textContent = message;
        container.appendChild(el);
        setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateX(100%)'; setTimeout(() => el.remove(), 300); }, 3500);
    },

    // ── Modal ──
    modal(title, contentHtml, footerHtml = '') {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal">
                <div class="modal-title">${title}</div>
                <div class="modal-body">${contentHtml}</div>
                <div class="modal-footer">${footerHtml}</div>
            </div>
        `;
        overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
        document.body.appendChild(overlay);
        return overlay.querySelector('.modal');
    },

    // ── Markdown Renderer ──
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
            // Lists
            .replace(/^- (.+)$/gm, '<li>$1</li>')
            .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
            // HR
            .replace(/^---$/gm, '<hr>')
            // Blockquote
            .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
            // Paragraphs
            .replace(/\n\n/g, '</p><p>')
            .replace(/^(?!<[hul])/gm, '<p>')
            .replace(/(?<![hul]>)$/gm, '</p>');
        return html;
    },

    // ═══════════════════════════════════════════════════════════════════
    //  DASHBOARD
    // ═══════════════════════════════════════════════════════════════════

    async renderDashboard(mc) {
        const novelsResp = await API.listNovels();
        const novels = novelsResp.success ? novelsResp.novels : [];

        const totalChapters = novels.reduce((s, n) => s + (n.total_chapters || 0), 0);
        const totalReviews = novels.reduce((s, n) => s + (n.review_count || 0), 0);

        mc.innerHTML = `
            <div class="page-header">
                <div>
                    <h1 class="page-title">📊 写作控制台</h1>
                    <p class="page-subtitle">管理你的所有小说项目</p>
                </div>
                <div class="flex gap-8">
                    <button class="btn btn-primary" onclick="App.navigate('new-book')">✨ 创建新书</button>
                </div>
            </div>
            <div class="stats-grid">
                <div class="stat-card"><div class="stat-value">${novels.length}</div><div class="stat-label">项目数</div></div>
                <div class="stat-card"><div class="stat-value">${totalChapters}</div><div class="stat-label">总章节</div></div>
                <div class="stat-card"><div class="stat-value">${totalReviews}</div><div class="stat-label">审稿数</div></div>
                <div class="stat-card"><div class="stat-value">${this.config.deepseek_configured ? '✅' : '❌'}</div><div class="stat-label">DeepSeek</div></div>
            </div>
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">📚 所有项目</h2>
                </div>
                <div class="novel-grid" id="novelGrid">
                    ${novels.length === 0 ? '<div class="empty-state"><div class="empty-state-icon">📖</div><div class="empty-state-title">还没有小说项目</div><div class="empty-state-desc">点击"创建新书"开始你的第一部作品</div></div>' : ''}
                </div>
            </div>
        `;

        if (novels.length > 0) {
            const grid = document.getElementById('novelGrid');
            novels.forEach(n => {
                const card = document.createElement('div');
                card.className = 'novel-card';
                card.innerHTML = `
                    <div class="novel-card-title">${n.title || n.name}</div>
                    <div class="novel-card-meta">
                        <span class="novel-card-stat">📖 ${n.total_chapters} 章</span>
                        <span class="novel-card-stat">📐 ${n.volumes ? n.volumes.length : 0} 卷</span>
                        <span class="novel-card-stat">🔍 ${n.review_count} 审稿</span>
                    </div>
                    <div class="novel-card-summary">${n.summary || '暂无简介'}</div>
                `;
                card.addEventListener('click', () => this.showNovelDetail(n.name));
                grid.appendChild(card);
            });
        }
    },

    async showNovelDetail(name) {
        const resp = await API.getNovel(name);
        if (!resp.success) { this.toast(resp.error, 'error'); return; }
        const n = resp.novel;

        const modalHtml = `
            <div class="tabs" id="detailTabs">
                <span class="tab active" data-tab="info">概况</span>
                <span class="tab" data-tab="chapters">章节</span>
                <span class="tab" data-tab="outline">大纲</span>
                <span class="tab" data-tab="status">状态</span>
            </div>
            <div id="detailContent">
                <div class="stats-grid" style="grid-template-columns: repeat(3, 1fr);">
                    <div class="stat-card"><div class="stat-value">${n.total_chapters}</div><div class="stat-label">章节</div></div>
                    <div class="stat-card"><div class="stat-value">${n.volumes ? n.volumes.length : 0}</div><div class="stat-label">卷数</div></div>
                    <div class="stat-card"><div class="stat-value">${n.review_count}</div><div class="stat-label">审稿</div></div>
                </div>
                <div class="markdown-content">${this.renderMarkdown(n.project_content || '')}</div>
            </div>
        `;

        const footer = `
            <button class="btn btn-secondary" onclick="App.navigate('writing', {novel:'${n.name}'})">✍️ 开始写作</button>
            <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">关闭</button>
        `;

        const modalEl = this.modal(`📚 ${n.title || n.name}`, modalHtml, footer);

        // Tab switching
        modalEl.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', async () => {
                modalEl.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                const content = modalEl.querySelector('#detailContent');
                const t = tab.dataset.tab;
                if (t === 'info') {
                    content.innerHTML = `<div class="stats-grid" style="grid-template-columns: repeat(3, 1fr);"><div class="stat-card"><div class="stat-value">${n.total_chapters}</div><div class="stat-label">章节</div></div><div class="stat-card"><div class="stat-value">${n.volumes ? n.volumes.length : 0}</div><div class="stat-label">卷数</div></div><div class="stat-card"><div class="stat-value">${n.review_count}</div><div class="stat-label">审稿</div></div></div><div class="markdown-content">${this.renderMarkdown(n.project_content || '')}</div>`;
                } else if (t === 'chapters') {
                    let html = '<div class="chapter-list">';
                    if (n.volumes) {
                        n.volumes.forEach(v => {
                            html += `<div style="margin-top:12px;font-weight:600;color:var(--accent)">📁 ${v.name} (${v.chapter_count}章)</div>`;
                            v.chapters.forEach(ch => {
                                const chRef = `${v.name}/${ch}`;
                                html += `<div class="chapter-item"><span>${ch}</span><div class="ch-actions"><button class="btn btn-sm btn-secondary" onclick="App.navigate('writing',{novel:'${n.name}',chapter:'${chRef}'})">✍️</button><button class="btn btn-sm btn-secondary" onclick="App.navigate('review',{novel:'${n.name}',chapter:'${chRef}'})">🔍</button></div></div>`;
                            });
                        });
                    }
                    html += '</div>';
                    content.innerHTML = html || '<div class="empty-state"><div class="empty-state-icon">📄</div><div class="empty-state-title">暂无章节</div></div>';
                } else if (t === 'outline') {
                    let html = '';
                    if (n.outline_files && n.outline_files.length > 0) {
                        for (const f of n.outline_files) {
                            const outlineResp = await API.readOutline(n.name, f.replace('-chapters.md', ''));
                            const label = f.replace('-chapters.md', '');
                            html += `<h3>📐 ${label}</h3><div class="code-block info">${outlineResp.success ? this.renderMarkdown(outlineResp.content.substring(0, 3000)) : '加载失败'}</div>`;
                        }
                    } else {
                        html = '<div class="empty-state"><div class="empty-state-icon">📐</div><div class="empty-state-title">暂无大纲</div><div class="empty-state-desc">请先创建卷大纲</div></div>';
                    }
                    content.innerHTML = html;
                } else if (t === 'status') {
                    const statusResp = await API.getStatus(n.name);
                    content.innerHTML = statusResp.success ? `<div class="code-block info">${this.renderMarkdown(statusResp.content)}</div>` : '<div class="empty-state"><div class="empty-state-icon">📊</div><div class="empty-state-title">暂无状态</div></div>';
                }
            });
        });
    },

    // ═══════════════════════════════════════════════════════════════════
    //  NOVELS LIST
    // ═══════════════════════════════════════════════════════════════════

    async renderNovels(mc) {
        mc.innerHTML = `
            <div class="page-header">
                <div>
                    <h1 class="page-title">📚 小说管理</h1>
                    <p class="page-subtitle">查看和管理所有小说项目</p>
                </div>
                <button class="btn btn-primary" onclick="App.navigate('new-book')">✨ 创建新书</button>
            </div>
            <div id="novelsList"><div class="loading"><div class="spinner"></div></div></div>
        `;

        const resp = await API.listNovels();
        if (!resp.success) { document.getElementById('novelsList').innerHTML = `<div class="empty-state"><div class="empty-state-icon">💥</div><div class="empty-state-title">加载失败</div></div>`; return; }
        const novels = resp.novels;
        const container = document.getElementById('novelsList');

        if (novels.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📖</div><div class="empty-state-title">还没有小说项目</div><div class="empty-state-desc">点击右上角"创建新书"开始</div></div>';
            return;
        }

        let html = '<div class="novel-grid">';
        novels.forEach(n => {
            html += `
                <div class="novel-card" onclick="App.showNovelDetail('${n.name}')">
                    <div class="novel-card-title">${n.title || n.name}</div>
                    <div class="novel-card-meta">
                        <span class="novel-card-stat">📖 ${n.total_chapters} 章</span>
                        <span class="novel-card-stat">📐 ${n.volumes ? n.volumes.length : 0} 卷</span>
                        <span class="novel-card-stat">🔍 ${n.review_count} 审稿</span>
                    </div>
                    <div class="novel-card-summary">${n.summary || '暂无简介'}</div>
                </div>
            `;
        });
        html += '</div>';
        container.innerHTML = html;
    },

    // ═══════════════════════════════════════════════════════════════════
    //  NEW BOOK
    // ═══════════════════════════════════════════════════════════════════

    async renderNewBook(mc) {
        const configured = this.config.deepseek_configured;
        mc.innerHTML = `
            <div class="page-header">
                <div>
                    <h1 class="page-title">✨ 创建新书</h1>
                    <p class="page-subtitle">使用 DeepSeek AI 自动生成小说基础资料</p>
                </div>
            </div>
            ${!configured ? `
            <div class="card" style="border-color: var(--warning);">
                <div class="flex items-center gap-3">
                    <span style="font-size:24px;">⚠️</span>
                    <div>
                        <strong style="color:var(--warning);">API Key 未配置</strong>
                        <p class="text-secondary mt-2">请先在 <a href="#" onclick="App.navigate('settings')" style="color:var(--accent);">⚙️ 设置页面</a> 填入 DeepSeek API Key</p>
                    </div>
                </div>
            </div>
            ` : ''}
            <div class="card">
                <div class="form-group">
                    <label class="form-label">书名 *</label>
                    <input class="form-input" id="nbName" placeholder="例如：九天剑帝">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">题材 *</label>
                        <input class="form-input" id="nbGenre" placeholder="玄幻 / 都市 / 修仙 / 科幻...">
                    </div>
                    <div class="form-group">
                        <label class="form-label">篇幅目标</label>
                        <select class="form-select" id="nbWordGoal">
                            <option value="50万">50万字</option>
                            <option value="100万" selected>100万字</option>
                            <option value="200万">200万字</option>
                            <option value="300万">300万字</option>
                        </select>
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">主角设定 *</label>
                    <textarea class="form-textarea" id="nbProtagonist" rows="3" placeholder="主角姓名、性格、背景、金手指等"></textarea>
                </div>
                <div class="form-group">
                    <label class="form-label">作品卖点</label>
                    <textarea class="form-textarea" id="nbSellingPoint" rows="2" placeholder="这本书最吸引读者的地方"></textarea>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">叙事视角</label>
                        <select class="form-select" id="nbPerspective">
                            <option value="第三人称" selected>第三人称</option>
                            <option value="第一人称">第一人称</option>
                            <option value="多视角">多视角</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">参考作品</label>
                        <input class="form-input" id="nbReferences" placeholder="可选，如：凡人修仙传...">
                    </div>
                </div>
                <button class="btn btn-primary btn-lg" onclick="App.createNovel()" id="nbBtn">
                    🚀 AI 自动创建
                </button>
                <div id="nbResult" class="mt-16"></div>
            </div>
        `;
    },

    async createNovel() {
        const name = document.getElementById('nbName').value.trim();
        if (!name) { this.toast('请填写书名', 'warning'); return; }

        const data = {
            name,
            genre: document.getElementById('nbGenre').value.trim(),
            protagonist: document.getElementById('nbProtagonist').value.trim(),
            selling_point: document.getElementById('nbSellingPoint').value.trim(),
            word_goal: document.getElementById('nbWordGoal').value,
            perspective: document.getElementById('nbPerspective').value,
            references: document.getElementById('nbReferences').value.trim(),
        };

        if (!data.genre) { this.toast('请选择题材', 'warning'); return; }
        if (!data.protagonist) { this.toast('请填写主角设定', 'warning'); return; }

        const btn = document.getElementById('nbBtn');
        btn.disabled = true;
        btn.textContent = '⏳ AI 生成中...';

        const resp = await API.createNovel(data);
        btn.disabled = false;
        btn.textContent = '🚀 AI 自动创建';

        const resultDiv = document.getElementById('nbResult');
        if (resp.success) {
            this.toast(`🎉 小说「${resp.novel_name}」创建成功！`, 'success');
            resultDiv.innerHTML = `
                <div class="card" style="border-color: var(--success);">
                    <h3>✅ 创建成功</h3>
                    <p class="text-secondary mt-8">已创建文件：</p>
                    <div class="code-block success mt-8">${resp.created_files.join('\n')}</div>
                    <div class="mt-16 flex gap-8">
                        <button class="btn btn-primary" onclick="App.navigate('novels')">📚 查看项目</button>
                        <button class="btn btn-success" onclick="App.navigate('writing',{novel:'${resp.novel_name}'})">✍️ 开始写作</button>
                    </div>
                </div>
            `;
        } else {
            this.toast(`创建失败: ${resp.error}`, 'error');
            resultDiv.innerHTML = `<div class="code-block error">${resp.error}</div>`;
        }
    },

    // ═══════════════════════════════════════════════════════════════════
    //  WRITING
    // ═══════════════════════════════════════════════════════════════════

    async renderWriting(mc, params) {
        const novelParam = params.novel || '';
        let html = `
            <div class="page-header">
                <div>
                    <h1 class="page-title">✍️ 写作台</h1>
                    <p class="page-subtitle">创建或续写章节</p>
                </div>
            </div>
            <div class="card">
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">选择小说 *</label>
                        <select class="form-select" id="wNovel" onchange="App.loadWritingContext()">
                            <option value="">-- 请选择 --</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">卷号</label>
                        <select class="form-select" id="wVolume">
                            <option value="vol-01">vol-01</option>
                            <option value="vol-02">vol-02</option>
                            <option value="vol-03">vol-03</option>
                            <option value="vol-04">vol-04</option>
                            <option value="vol-05">vol-05</option>
                            <option value="vol-06">vol-06</option>
                            <option value="vol-07">vol-07</option>
                            <option value="vol-08">vol-08</option>
                            <option value="vol-09">vol-09</option>
                            <option value="vol-10">vol-10</option>
                        </select>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">章节编号</label>
                        <input class="form-input" id="wChapterNum" placeholder="如：1, 2, 3... 留空则自动推断">
                    </div>
                    <div class="form-group">
                        <label class="form-label">风格（可选）</label>
                        <input class="form-input" id="wStyle" placeholder="默认 / 金庸 / 古龙 / 余华...">
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">写作指示（可选）</label>
                    <textarea class="form-textarea" id="wInstructions" rows="3" placeholder="对本章的特殊要求..."></textarea>
                </div>
                <div class="flex gap-8">
                    <button class="btn btn-primary btn-lg" onclick="App.generateSingleChapter()">✍️ 生成单章</button>
                    <button class="btn btn-success btn-lg" onclick="App.openBatchWriting()">📦 批量续写</button>
                </div>
                <div id="wResult" class="mt-16"></div>
            </div>
            <div id="wContext" class="mt-16"></div>
        `;
        mc.innerHTML = html;

        // Load novels into select
        const resp = await API.listNovels();
        if (resp.success) {
            const select = document.getElementById('wNovel');
            resp.novels.forEach(n => {
                const opt = document.createElement('option');
                opt.value = n.name;
                opt.textContent = `${n.title || n.name} (${n.total_chapters}章)`;
                select.appendChild(opt);
            });
            if (novelParam) {
                select.value = novelParam;
                this.loadWritingContext();
            }
        }
    },

    async loadWritingContext() {
        const name = document.getElementById('wNovel').value;
        if (!name) return;
        const container = document.getElementById('wContext');

        // Auto-detect next chapter number
        const novelResp = await API.getNovel(name);
        if (novelResp.success) {
            const n = novelResp.novel;
            if (n.total_chapters > 0) {
                const chInput = document.getElementById('wChapterNum');
                if (!chInput.value) {
                    chInput.value = n.total_chapters + 1;
                }
            } else {
                document.getElementById('wChapterNum').value = '1';
            }
        }

        // Show context info
        const statusResp = await API.getStatus(name);
        let html = '<div class="card"><h3 class="card-title">📋 项目上下文</h3>';
        if (statusResp.success) {
            html += `<div class="code-block info mt-8">${this.renderMarkdown(statusResp.content.substring(0, 1500))}</div>`;
        } else {
            html += '<p class="text-muted mt-8">暂无状态信息</p>';
        }
        html += '</div>';
        container.innerHTML = html;
    },

    async generateSingleChapter() {
        const novel = document.getElementById('wNovel').value;
        if (!novel) { this.toast('请选择小说', 'warning'); return; }

        const data = {
            volume: document.getElementById('wVolume').value,
            chapter_num: document.getElementById('wChapterNum').value,
            style: document.getElementById('wStyle').value,
            instructions: document.getElementById('wInstructions').value,
        };

        if (!data.chapter_num) { this.toast('请填写章节编号', 'warning'); return; }

        const btn = document.querySelector('#wResult');
        const resultDiv = document.getElementById('wResult');
        resultDiv.innerHTML = '<div class="loading"><div class="spinner"></div><span>AI 正在创作中...</span></div>';

        const resp = await API.generateChapter(novel, data);
        if (resp.success) {
            this.toast(`✅ 第 ${data.chapter_num} 章生成成功！`, 'success');
            resultDiv.innerHTML = `
                <div class="card" style="border-color: var(--success);">
                    <div class="flex justify-between items-center">
                        <h3>✅ 生成完成</h3>
                        <span class="badge badge-success">${resp.chapter_file}</span>
                    </div>
                    <div class="writing-area mt-16" style="height: auto; grid-template-columns: 1fr;">
                        <div class="code-block success" style="max-height: 600px;">${this.renderMarkdown(resp.content.substring(0, 5000))}</div>
                    </div>
                    <div class="flex gap-8 mt-16">
                        <button class="btn btn-primary" onclick="App.navigate('review',{novel:'${novel}',chapter:'${resp.chapter_file}'})">🔍 审稿</button>
                        <button class="btn btn-secondary" onclick="document.getElementById('wChapterNum').value = parseInt(document.getElementById('wChapterNum').value) + 1; document.getElementById('wInstructions').value=''; App.generateSingleChapter()">➡️ 写下一章</button>
                        <button class="btn btn-secondary" onclick="this.closest('.card').remove()">关闭</button>
                    </div>
                </div>
            `;
        } else {
            this.toast(`生成失败: ${resp.error}`, 'error');
            resultDiv.innerHTML = `<div class="code-block error mt-8">${resp.error}</div>`;
        }
    },

    openBatchWriting() {
        const novel = document.getElementById('wNovel').value;
        if (!novel) { this.toast('请先选择小说', 'warning'); return; }

        const modalHtml = `
            <div class="form-group">
                <label class="form-label">起始章节</label>
                <input class="form-input" id="batchStart" type="number" min="1" value="${document.getElementById('wChapterNum').value || 1}">
            </div>
            <div class="form-group">
                <label class="form-label">结束章节</label>
                <input class="form-input" id="batchEnd" type="number" min="1" value="${(parseInt(document.getElementById('wChapterNum').value) || 0) + 5}">
            </div>
            <div class="form-group">
                <label class="form-label">卷号</label>
                <select class="form-select" id="batchVolume">${document.getElementById('wVolume').innerHTML}</select>
            </div>
            <div class="form-group">
                <label class="form-label">风格（可选，所有章节统一风格）</label>
                <input class="form-input" id="batchStyle" placeholder="默认 / 金庸 / 古龙...">
            </div>
            <div id="batchResult"></div>
        `;
        const footer = `
            <button class="btn btn-success" onclick="App.runBatchWriting('${novel}')">🚀 开始批量写作</button>
            <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">取消</button>
        `;
        this.modal('📦 批量续写', modalHtml, footer);
    },

    async runBatchWriting(novel) {
        const start = parseInt(document.getElementById('batchStart').value);
        const end = parseInt(document.getElementById('batchEnd').value);
        const volume = document.getElementById('batchVolume').value;
        const style = document.getElementById('batchStyle').value;

        if (!start || !end || end < start) {
            this.toast('请填写有效的章节范围', 'warning');
            return;
        }

        const resultDiv = document.getElementById('batchResult');
        resultDiv.innerHTML = '<div class="loading"><div class="spinner"></div><span>批量写作进行中...</span></div>';

        // Disable button
        const btn = resultDiv.closest('.modal-footer')?.querySelector('.btn-success');
        if (btn) btn.disabled = true;

        const total = end - start + 1;
        let completed = 0;
        let results = [];

        for (let i = start; i <= end; i++) {
            resultDiv.innerHTML = `<div class="loading"><div class="spinner"></div><span>正在写第 ${i} 章 (${completed + 1}/${total})...</span></div>`;
            const resp = await API.generateChapter(novel, {
                volume,
                chapter_num: String(i),
                style,
                instructions: `批量写作第 ${i} 章，保持与上一章的连续性`,
            });
            if (resp.success) {
                completed++;
                results.push(`✅ 第${i}章 完成`);
            } else {
                results.push(`❌ 第${i}章 失败: ${resp.error}`);
            }
        }

        if (btn) btn.disabled = false;
        resultDiv.innerHTML = `
            <div class="card" style="border-color: ${completed === total ? 'var(--success)' : 'var(--warning)'};">
                <h3>${completed === total ? '✅ 批量完成' : '⚠️ 部分完成'}</h3>
                <p>${completed}/${total} 章已生成</p>
                <div class="code-block mt-8">${results.join('\n')}</div>
                <button class="btn btn-primary mt-16" onclick="this.closest('.modal-overlay').remove()">关闭</button>
            </div>
        `;
        this.toast(`批量写作完成: ${completed}/${total}`, completed === total ? 'success' : 'warning');
    },

    // ═══════════════════════════════════════════════════════════════════
    //  REVIEW
    // ═══════════════════════════════════════════════════════════════════

    async renderReview(mc, params) {
        mc.innerHTML = `
            <div class="page-header">
                <div>
                    <h1 class="page-title">🔍 审稿台</h1>
                    <p class="page-subtitle">AI + 脚本双重审稿</p>
                </div>
            </div>
            <div class="card">
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">选择小说</label>
                        <select class="form-select" id="rNovel" onchange="App.loadReviewChapters()">
                            <option value="">-- 请选择 --</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">选择章节</label>
                        <select class="form-select" id="rChapter">
                            <option value="">-- 请先选择小说 --</option>
                        </select>
                    </div>
                </div>
                <button class="btn btn-primary btn-lg" onclick="App.runReview()">🔍 开始审稿</button>
                <div id="rResult" class="mt-16"></div>
            </div>
        `;

        const resp = await API.listNovels();
        if (resp.success) {
            const select = document.getElementById('rNovel');
            resp.novels.forEach(n => {
                const opt = document.createElement('option');
                opt.value = n.name;
                opt.textContent = `${n.title || n.name} (${n.total_chapters}章)`;
                select.appendChild(opt);
            });
            if (params.novel) {
                select.value = params.novel;
                await this.loadReviewChapters();
                if (params.chapter) {
                    document.getElementById('rChapter').value = params.chapter;
                    this.runReview();
                }
            }
        }
    },

    async loadReviewChapters() {
        const name = document.getElementById('rNovel').value;
        const select = document.getElementById('rChapter');
        select.innerHTML = '<option value="">加载中...</option>';

        if (!name) {
            select.innerHTML = '<option value="">-- 请先选择小说 --</option>';
            return;
        }

        const resp = await API.getNovel(name);
        if (!resp.success) return;

        const n = resp.novel;
        select.innerHTML = '<option value="">-- 选择章节 --</option>';
        if (n.volumes) {
            n.volumes.forEach(v => {
                v.chapters.forEach(ch => {
                    const ref = `${v.name}/${ch}`;
                    const opt = document.createElement('option');
                    opt.value = ref;
                    opt.textContent = `${v.name} / ${ch}`;
                    select.appendChild(opt);
                });
            });
        }
        if (select.options.length === 1) {
            select.innerHTML = '<option value="">-- 暂无章节 --</option>';
        }
    },

    async runReview() {
        const novel = document.getElementById('rNovel').value;
        const chRef = document.getElementById('rChapter').value;

        if (!novel) { this.toast('请选择小说', 'warning'); return; }
        if (!chRef) { this.toast('请选择章节', 'warning'); return; }

        const resultDiv = document.getElementById('rResult');
        resultDiv.innerHTML = '<div class="loading"><div class="spinner"></div><span>审稿中：AI 分析 + 脚本检查...</span></div>';

        // Parse chapter ref
        const parts = chRef.split('/');
        const volume = parts[0];
        const chapter_ref = parts[1] || chRef;
        const chapter_num = chapter_ref.replace('ch-', '');

        const resp = await API.reviewChapter(novel, {
            chapter_ref: chRef.replace('.md', ''),
            volume,
            chapter_num,
        });

        if (resp.success) {
            resultDiv.innerHTML = `
                <div class="card" style="border-color: var(--info);">
                    <h3>📋 审稿结果</h3>
                    <div class="code-block info mt-8">${resp.ai_review}</div>
                    <h4 class="mt-16">📊 脚本检查</h4>
                    <div class="grid-3 mt-8">
                        <div class="stat-card">
                            <div class="stat-value" style="font-size:16px">${resp.script_results.analyze.success ? '✅' : '❌'}</div>
                            <div class="stat-label">字数/结构</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" style="font-size:16px">${resp.script_results.compliance.success ? '✅' : '❌'}</div>
                            <div class="stat-label">合规检查</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" style="font-size:16px">${resp.script_results.forbidden.success ? '✅' : '❌'}</div>
                            <div class="stat-label">禁用模式</div>
                        </div>
                    </div>
                    <details class="mt-8">
                        <summary style="cursor:pointer;color:var(--accent)">查看详细脚本输出</summary>
                        <div class="code-block mt-8">=== 字数/结构 ===\n${resp.script_results.analyze.stdout}\n\n=== 合规检查 ===\n${resp.script_results.compliance.stdout}\n\n=== 禁用模式 ===\n${resp.script_results.forbidden.stdout}</div>
                    </details>
                </div>
            `;
            this.toast('✅ 审稿完成', 'success');
        } else {
            this.toast(`审稿失败: ${resp.error}`, 'error');
            resultDiv.innerHTML = `<div class="code-block error">${resp.error}</div>`;
        }
    },

    // ═══════════════════════════════════════════════════════════════════
    //  SETTINGS
    // ═══════════════════════════════════════════════════════════════════

    async renderSettings(mc) {
        // Re-fetch latest config
        const cfgResp = await API.getConfig();
        if (cfgResp.success) {
            this.config = cfgResp;
            this.updateConfigStatus(cfgResp);
        }
        const cfg = this.config;

        mc.innerHTML = `
            <div class="page-header">
                <div>
                    <h1 class="page-title">⚙️ 设置</h1>
                    <p class="page-subtitle">DeepSeek API 配置和系统信息</p>
                </div>
            </div>
            <div class="grid-2">
                <div class="card with-accent">
                    <h3 class="card-title">🤖 DeepSeek API 配置</h3>
                    <p class="text-secondary mt-8" style="font-size:12px;">在此页面直接设置 API Key，无需修改环境变量。保存后即时生效。</p>
                    <div class="form-group mt-16">
                        <label class="form-label">API Key *</label>
                        <div class="password-wrapper">
                            <input class="form-input" id="sApiKey" type="password"
                                placeholder="sk-..."
                                value="${cfg.deepseek_key_set_via_ui || ''}">
                            <button class="password-toggle" onclick="App.togglePasswordVisibility('sApiKey', this)" title="显示/隐藏">👁</button>
                        </div>
                        <div class="text-muted" style="font-size:11px;margin-top:4px;">
                            ${cfg.deepseek_configured
                                ? '当前使用: <code style="color:var(--accent)">' + cfg.deepseek_key_masked + '</code>'
                                : '首次使用请在此填入你的 DeepSeek API Key'}
                        </div>
                    </div>
                    <div class="form-group mt-12">
                        <label class="form-label">API Base URL</label>
                        <input class="form-input" id="sApiBase" type="text"
                            placeholder="${cfg.deepseek_api_base || 'https://api.deepseek.com'}"
                            value="${cfg.deepseek_api_base && cfg.deepseek_api_base !== 'https://api.deepseek.com' ? cfg.deepseek_api_base : ''}">
                        <div class="text-muted" style="font-size:11px;margin-top:4px;">留空则使用默认值 <code>https://api.deepseek.com</code></div>
                    </div>
                    <div class="form-group mt-12">
                        <label class="form-label">模型</label>
                        <div class="form-row" style="grid-template-columns:1fr auto;">
                            <input class="form-input" id="sModel" type="text"
                                placeholder="${cfg.deepseek_model || 'deepseek-chat'}"
                                value="${cfg.deepseek_model && cfg.deepseek_model !== 'deepseek-chat' ? cfg.deepseek_model : ''}">
                            <select class="form-select" id="sModelPreset" style="width:auto;min-width:100px;" onchange="document.getElementById('sModel').value=this.value">
                                <option value="">常用模型</option>
                                <option value="deepseek-chat">deepseek-chat</option>
                                <option value="deepseek-reasoner">deepseek-reasoner</option>
                                <option value="deepseek-v4-flash">deepseek-v4-flash</option>
                            </select>
                        </div>
                        <div class="text-muted" style="font-size:11px;margin-top:4px;">留空则使用默认值 <code>deepseek-chat</code></div>
                    </div>
                    <div class="flex gap-8 mt-16">
                        <button class="btn btn-primary" onclick="App.saveConfig()">💾 保存配置</button>
                        <button class="btn btn-success" id="sTestBtn" onclick="App.testConfig()"
                            ${cfg.deepseek_configured ? '' : 'disabled'}>🔌 测试连接</button>
                    </div>
                    <div id="sResult" class="mt-12"></div>
                </div>

                <div class="card">
                    <h3 class="card-title">📂 系统信息</h3>
                    <div class="mt-8">
                        <div class="info-row"><span class="info-label">状态</span><span class="badge ${cfg.deepseek_configured ? 'badge-success' : 'badge-warning'}">${cfg.deepseek_configured ? '已配置' : '未配置'}</span></div>
                        <div class="info-row"><span class="info-label">模型</span><span class="text-mono">${cfg.deepseek_model || 'deepseek-chat'}</span></div>
                        <div class="info-row"><span class="info-label">API Base</span><span class="text-mono">${cfg.deepseek_api_base || 'https://api.deepseek.com'}</span></div>
                        <div class="info-row"><span class="info-label">项目目录</span><span class="text-muted text-mono">${cfg.agent_root || 'N/A'}</span></div>
                        <div class="info-row"><span class="info-label">小说目录</span><span class="text-muted text-mono">${cfg.novels_root || 'N/A'}</span></div>
                        <div class="info-row"><span class="info-label">Portal 端口</span><span class="text-mono">8686</span></div>
                    </div>
                </div>

                <div class="card">
                    <h3 class="card-title">📊 使用统计</h3>
                    <div class="mt-8">
                        <button class="btn btn-secondary" onclick="App.refreshStats(this)">🔄 刷新统计</button>
                        <div id="statsDisplay" class="mt-8"></div>
                    </div>
                </div>

                <div class="card">
                    <h3 class="card-title">🔌 脚本辅助</h3>
                    <div class="mt-8">
                        <p class="text-secondary">系统自带以下 Python 脚本辅助写作流程：</p>
                        <ul class="mt-8 text-secondary" style="padding-left:20px;">
                            <li>analyze_chapter.py — 字数/结构检测</li>
                            <li>check_compliance.py — 合规名称检查</li>
                            <li>detect_forbidden_patterns.py — 禁用模式检测</li>
                            <li>stage_gate.py — 阶段门控</li>
                            <li>rag_context.py / rag_index.py — RAG 记忆</li>
                            <li>verify_continuity.py — 连续性校验</li>
                        </ul>
                    </div>
                </div>
            </div>
        `;
    },

    togglePasswordVisibility(inputId, btn) {
        const input = document.getElementById(inputId);
        if (input.type === 'password') {
            input.type = 'text';
            btn.textContent = '🙈';
        } else {
            input.type = 'password';
            btn.textContent = '👁';
        }
    },

    async saveConfig() {
        const apiKey = document.getElementById('sApiKey').value.trim();
        const apiBase = document.getElementById('sApiBase').value.trim();
        const model = document.getElementById('sModel').value.trim();

        if (!apiKey) {
            this.toast('请输入 API Key', 'warning');
            return;
        }

        const btn = document.querySelector('#sResult').closest('.card')?.querySelector('.btn-primary');
        if (btn) { btn.disabled = true; btn.textContent = '⏳ 保存中...'; }

        const resp = await API.saveConfig({ api_key: apiKey, api_base: apiBase, model });

        if (btn) { btn.disabled = false; btn.textContent = '💾 保存配置'; }

        const resultDiv = document.getElementById('sResult');
        if (resp.success) {
            this.toast('✅ 配置已保存', 'success');
            resultDiv.innerHTML = `<div class="code-block success">✅ 配置已保存\n模型: ${resp.deepseek_model}\nAPI Base: ${resp.deepseek_api_base}\nAPI Key: ${resp.deepseek_key_masked}</div>`;
            // Update sidebar status
            this.config.deepseek_configured = resp.deepseek_configured;
            this.config.deepseek_model = resp.deepseek_model;
            this.updateConfigStatus(resp);
            // Enable test button
            const testBtn = document.getElementById('sTestBtn');
            if (testBtn) testBtn.disabled = false;
        } else {
            this.toast(`保存失败: ${resp.error}`, 'error');
            resultDiv.innerHTML = `<div class="code-block error">${resp.error}</div>`;
        }
    },

    async testConfig() {
        const btn = document.getElementById('sTestBtn');
        const resultDiv = document.getElementById('sResult');
        btn.disabled = true;
        btn.textContent = '⏳ 测试中...';
        resultDiv.innerHTML = '<div class="loading"><div class="spinner"></div><span>正在连接 DeepSeek API...</span></div>';

        const resp = await API.testConfig();

        btn.disabled = false;
        btn.textContent = '🔌 测试连接';

        if (resp.success) {
            this.toast('✅ API 连接成功', 'success');
            resultDiv.innerHTML = `<div class="code-block success">${resp.message}\n模型: ${resp.model}</div>`;
        } else {
            this.toast(`❌ ${resp.error}`, 'error');
            resultDiv.innerHTML = `<div class="code-block error">❌ ${resp.error}</div>`;
        }
    },

    updateConfigStatus(cfg) {
        const dot = document.getElementById('configStatus');
        if (!dot) return;
        if (cfg.deepseek_configured) {
            dot.innerHTML = '<span class="status-dot green"></span> DeepSeek 已连接';
        } else {
            dot.innerHTML = '<span class="status-dot orange"></span> 需配置 API Key';
        }
    },

    async refreshStats(btn) {
        btn.disabled = true;
        btn.textContent = '⏳ 刷新中...';
        const resp = await API.listNovels();
        if (resp.success) {
            const total = resp.novels.length;
            const chapters = resp.novels.reduce((s, n) => s + (n.total_chapters || 0), 0);
            const reviews = resp.novels.reduce((s, n) => s + (n.review_count || 0), 0);
            document.getElementById('statsDisplay').innerHTML = `
                <div class="stats-grid" style="grid-template-columns: repeat(3,1fr);">
                    <div class="stat-card"><div class="stat-value">${total}</div><div class="stat-label">小说</div></div>
                    <div class="stat-card"><div class="stat-value">${chapters}</div><div class="stat-label">章节</div></div>
                    <div class="stat-card"><div class="stat-value">${reviews}</div><div class="stat-label">审稿</div></div>
                </div>
            `;
        }
        btn.disabled = false;
        btn.textContent = '🔄 刷新';
    },
};

// ── Start ──
document.addEventListener('DOMContentLoaded', () => App.init());
