/**
 * 每日简报 · Daily Briefing
 * 仪表盘前端 — 双语展示 · 语音播报 · 语言切换
 */

const STATE = { currentLang: 'chinese', isPlaying: false, briefingData: null };
const $ = sel => document.querySelector(sel);
const $$ = sel => document.querySelectorAll(sel);

const briefingContent = $('#briefingContent');
// 美股
const stocksSectionUS = $('#stocksSectionUS');
const marketBar = $('#marketBar');
const highPotentialList = $('#highPotentialList');
const eventDrivenList = $('#eventDrivenList');
// A股
const stocksSectionA = $('#stocksSectionA');
const aHighPotentialList = $('#aHighPotentialList');
const aEventDrivenList = $('#aEventDrivenList');
// 港股
const stocksSectionHK = $('#stocksSectionHK');
const hkHighPotentialList = $('#hkHighPotentialList');
const hkEventDrivenList = $('#hkEventDrivenList');

const loadingState = $('#loadingState');
const emptyState = $('#emptyState');
const playBtn = $('#playBtn');
const audioPlayer = $('#audioPlayer');
const dateDisplay = $('#dateDisplay');
const statusText = $('#statusText');
const statusLang = $('#statusLang');
const statusTime = $('#statusTime');

// ==================== 初始化 ====================
async function init() {
    updateClock();
    setInterval(updateClock, 1000);
    $$('.lang-btn').forEach(btn => btn.addEventListener('click', () => switchLanguage(btn.dataset.lang)));
    playBtn.addEventListener('click', togglePlayback);
    $('#refreshBtn').addEventListener('click', forceRefresh);
    audioPlayer.addEventListener('ended', () => { STATE.isPlaying = false; updatePlayButton(); });
    audioPlayer.addEventListener('error', () => { STATE.isPlaying = false; updatePlayButton(); });
    await loadBriefing(STATE.currentLang);
}

// ==================== 加载简报 ====================
async function loadBriefing(lang) {
    showLoading(true);
    hideEmpty();
    try {
        const resp = await fetch(`/api/briefing?lang=${lang}`);
        const json = await resp.json();
        if (!json.success) { showEmpty(); setStatus('暂无简报'); return; }
        STATE.briefingData = json.data;
        STATE.currentLang = lang;
        renderBriefing(json.data.summary, lang);
        renderStocks(json.data.stocks, lang);
        updateDateDisplay(lang);
        updateLanguageButtons(lang);
        setStatus('简报就绪');
    } catch (err) {
        console.error(err);
        showEmpty();
        setStatus('加载失败');
    } finally {
        showLoading(false);
    }
}

// ==================== 强制刷新 ====================
async function forceRefresh() {
    setStatus('正在重新采集新闻...');
    showLoading(true);
    hideEmpty();
    try {
        const resp = await fetch(`/api/refresh?lang=${STATE.currentLang}`);
        const json = await resp.json();
        if (json.success) {
            await loadBriefing(STATE.currentLang);
            setStatus('简报已更新');
        } else {
            setStatus('刷新失败: ' + (json.message || ''));
            showLoading(false);
        }
    } catch (err) {
        setStatus('刷新失败');
        showLoading(false);
    }
}

// ==================== 渲染简报 ====================
function renderBriefing(summary, lang) {
    const isEn = lang === 'english';
    const cats = {
        political: { name: { chinese: '政治', english: 'Politics', cantonese: '政治' }, icon: '🏛️', color: '#e74c3c' },
        economic:  { name: { chinese: '经济', english: 'Economy', cantonese: '經濟' }, icon: '💰', color: '#f39c12' },
        military:  { name: { chinese: '军事', english: 'Military', cantonese: '軍事' }, icon: '⚔️', color: '#27ae60' },
        technology:{ name: { chinese: '科技', english: 'Technology', cantonese: '科技' }, icon: '🔬', color: '#3498db' },
    };

    let html = '';
    for (const [key, cat] of Object.entries(cats)) {
        const items = summary[key] || [];
        const catName = cat.name[lang] || cat.name.chinese;
        html += `<div class="category-card" style="border-left: 4px solid ${cat.color}">`;
        html += `<h2 class="category-title">${cat.icon} ${catName}</h2>`;
        if (!items.length) {
            html += '<p class="no-news">暂无重要新闻 / No major news</p>';
        } else {
            html += '<ol class="news-list">';
            for (const item of items.slice(0, 5)) {
                const stars = '★'.repeat(item.importance || 3) + '☆'.repeat(5 - (item.importance || 3));
                // 主语言标题和摘要
                let titleMain, summaryMain, titleSub;
                if (isEn) {
                    titleMain = item.title_en || item.title || '';
                    summaryMain = item.summary_en || item.summary || '';
                    titleSub = item.title_zh || '';
                } else {
                    titleMain = item.title_zh || item.title_en || item.title || '';
                    summaryMain = item.summary_zh || item.summary_en || item.summary || '';
                    titleSub = item.title_en || '';
                }
                html += `<li class="news-item">`;
                html += `<div class="news-title">${esc(titleMain)}</div>`;
                if (summaryMain) html += `<div class="news-summary">${esc(summaryMain)}</div>`;
                // 双语对照
                if (titleSub && titleSub !== titleMain) {
                    html += `<div class="news-original">🌐 ${esc(titleSub)}</div>`;
                }
                html += `<div class="news-importance" style="color:${cat.color}">${stars}</div>`;
                html += `</li>`;
            }
            html += '</ol>';
        }
        html += '</div>';
    }
    briefingContent.innerHTML = html;
    briefingContent.style.display = '';
}

// ==================== 语言切换 ====================
async function switchLanguage(lang) {
    if (STATE.currentLang === lang) return;
    if (STATE.isPlaying) { audioPlayer.pause(); STATE.isPlaying = false; updatePlayButton(); }
    await loadBriefing(lang);
}

function updateLanguageButtons(lang) {
    $$('.lang-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.lang === lang));
    const names = { chinese: '中文', english: 'English', cantonese: '粵語' };
    statusLang.textContent = names[lang] || lang;
}

// ==================== 音频播放 ====================
function togglePlayback() {
    if (STATE.isPlaying) {
        audioPlayer.pause();
        STATE.isPlaying = false;
        updatePlayButton();
        setStatus('已暂停');
        return;
    }
    const audioUrl = `/audio/${STATE.currentLang}`;
    setStatus('正在加载语音...');
    audioPlayer.src = audioUrl;
    audioPlayer.load();
    audioPlayer.play().then(() => {
        STATE.isPlaying = true;
        updatePlayButton();
        setStatus('正在播报...');
    }).catch(() => {
        STATE.isPlaying = false;
        updatePlayButton();
        setStatus('语音尚未生成，请先运行 python main.py');
    });
}

function updatePlayButton() {
    playBtn.innerHTML = STATE.isPlaying ? '⏸️ 暂停' : '🔊 播报';
    playBtn.classList.toggle('playing', STATE.isPlaying);
}

// ==================== UI 辅助 ====================
function showLoading(s) { loadingState.style.display = s ? '' : 'none'; }
function showEmpty() { emptyState.style.display = ''; briefingContent.style.display = 'none'; }
function hideEmpty() { emptyState.style.display = 'none'; }

function updateDateDisplay(lang) {
    const now = new Date();
    const loc = { chinese: 'zh-CN', english: 'en-US', cantonese: 'zh-HK' }[lang] || 'zh-CN';
    try { dateDisplay.textContent = now.toLocaleDateString(loc, { year:'numeric', month:'2-digit', day:'2-digit', weekday:'long' }); }
    catch { dateDisplay.textContent = now.toISOString().split('T')[0]; }
}

function updateClock() { statusTime.textContent = new Date().toLocaleTimeString('zh-CN', { hour12: false }); }
function setStatus(m) { statusText.textContent = m; }
function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

// ==================== 股票分析渲染 ====================
function renderStocks(stocksData, lang) {
    if (!stocksData) {
        stocksSectionUS.style.display = 'none';
        stocksSectionA.style.display = 'none';
        stocksSectionHK.style.display = 'none';
        return;
    }
    const isEn = lang === 'english';

    // ── 市场总览 ──
    renderMarketBar(stocksData.market_overview, isEn);

    // ── 美股 ──
    const usHP = stocksData.high_potential || [];
    const usED = stocksData.event_driven || [];
    if (usHP.length || usED.length) {
        stocksSectionUS.style.display = '';
        renderStockMarket(highPotentialList, usHP, 'high_potential', 'us', isEn);
        renderStockMarket(eventDrivenList, usED, 'event_driven', 'us', isEn);
    } else {
        stocksSectionUS.style.display = 'none';
    }

    // ── A股 ──
    const aData = stocksData.a_shares || {};
    const aHP = aData.high_potential || [];
    const aED = aData.event_driven || [];
    if (aHP.length || aED.length) {
        stocksSectionA.style.display = '';
        renderStockMarket(aHighPotentialList, aHP, 'high_potential', 'a', isEn);
        renderStockMarket(aEventDrivenList, aED, 'event_driven', 'a', isEn);
    } else {
        stocksSectionA.style.display = 'none';
    }

    // ── 港股 ──
    const hkData = stocksData.hk_stocks || {};
    const hkHP = hkData.high_potential || [];
    const hkED = hkData.event_driven || [];
    if (hkHP.length || hkED.length) {
        stocksSectionHK.style.display = '';
        renderStockMarket(hkHighPotentialList, hkHP, 'high_potential', 'hk', isEn);
        renderStockMarket(hkEventDrivenList, hkED, 'event_driven', 'hk', isEn);
    } else {
        stocksSectionHK.style.display = 'none';
    }
}

function renderMarketBar(overview, isEn) {
    if (!overview) { marketBar.innerHTML = ''; return; }

    const indices = overview.indices || [];
    const sentiment = overview.market_sentiment || '';
    const summary = isEn ? (overview.summary_en || overview.summary_zh || '') : (overview.summary_zh || overview.summary_en || '');

    let html = '';

    // 指数行情条
    if (indices.length > 0) {
        html += '<div class="market-indices">';
        for (const idx of indices) {
            const changeClass = idx.change_pct > 0 ? 'up' : (idx.change_pct < 0 ? 'down' : 'flat');
            const arrow = idx.change_pct > 0 ? '▲' : (idx.change_pct < 0 ? '▼' : '─');
            html += `<div class="market-index-item">
                <span class="index-name">${esc(idx.name)}</span>
                <span class="index-value">${idx.value != null ? idx.value.toLocaleString() : '---'}</span>
                <span class="index-change ${changeClass}">${arrow} ${Math.abs(idx.change_pct || 0).toFixed(2)}%</span>
            </div>`;
        }
        html += '</div>';
    }

    // 市场情绪 & 概要
    if (sentiment || summary) {
        html += '<div class="market-sentiment">';
        if (sentiment) {
            html += `<span class="sentiment-badge">${esc(sentiment)}</span>`;
        }
        if (summary) {
            html += `<span class="sentiment-summary">${esc(summary)}</span>`;
        }
        html += '</div>';
    }

    marketBar.innerHTML = html;
}

/**
 * 渲染一个市场的股票列表
 * @param {string} market - 'us' | 'a' | 'hk'
 */
function renderStockMarket(container, stocks, type, market, isEn) {
    if (!stocks || stocks.length === 0) {
        container.innerHTML = '<p class="no-news">暂无推荐 / No recommendations</p>';
        return;
    }

    // 货币符号
    const currencyMap = { us: '$', a: '¥', hk: 'HK$' };
    const currency = currencyMap[market] || '$';

    let html = '';
    for (const s of stocks) {
        const confidence = s.confidence || 3;
        const stars = '★'.repeat(confidence) + '☆'.repeat(5 - confidence);

        if (type === 'high_potential') {
            const name = esc(s.name || s.symbol);
            const symbol = esc(s.symbol);
            const price = s.price != null ? currency + s.price.toFixed(2) : '---';
            const upside = s.upside_pct != null ? '+' + s.upside_pct.toFixed(1) + '%' : '---';
            const downside = s.downside_pct != null ? '-' + s.downside_pct.toFixed(1) + '%' : '---';
            const rr = s.risk_reward != null ? s.risk_reward.toFixed(1) + 'x' : '---';
            const catalyst = isEn ? (s.catalyst_en || s.catalyst_zh || '') : (s.catalyst_zh || s.catalyst_en || '');

            html += `<div class="stock-card hp-card">
                <div class="stock-card-header">
                    <span class="stock-symbol">${symbol}</span>
                    <span class="stock-name">${name}</span>
                    <span class="stock-price">${price}</span>
                </div>
                <div class="stock-metrics">
                    <div class="stock-metric up">
                        <span class="metric-label">${isEn ? 'Upside' : '上涨空间'}</span>
                        <span class="metric-value">${upside}</span>
                    </div>
                    <div class="stock-metric down">
                        <span class="metric-label">${isEn ? 'Downside' : '下跌风险'}</span>
                        <span class="metric-value">${downside}</span>
                    </div>
                    <div class="stock-metric">
                        <span class="metric-label">${isEn ? 'Risk/Reward' : '风险收益比'}</span>
                        <span class="metric-value risk-reward-badge">${rr}</span>
                    </div>
                </div>
                ${catalyst ? `<div class="stock-catalyst">💡 ${esc(catalyst)}</div>` : ''}
                <div class="stock-confidence">${stars}</div>
            </div>`;
        } else {
            // event_driven
            const name = esc(s.name || s.symbol);
            const symbol = esc(s.symbol);
            const price = s.price != null ? currency + s.price.toFixed(2) : '---';
            const event = isEn ? (s.event_en || s.event_zh || '') : (s.event_zh || s.event_en || '');
            const analysis = isEn ? (s.analysis_en || s.analysis_zh || '') : (s.analysis_zh || s.analysis_en || '');
            const impact = s.expected_impact || '';
            const impactClass = impact === 'positive' ? 'impact-positive' : (impact === 'negative' ? 'impact-negative' : 'impact-neutral');

            html += `<div class="stock-card ed-card">
                <div class="stock-card-header">
                    <span class="stock-symbol">${symbol}</span>
                    <span class="stock-name">${name}</span>
                    <span class="stock-price">${price}</span>
                    ${impact ? `<span class="impact-badge ${impactClass}">${esc(impact)}</span>` : ''}
                </div>
                ${event ? `<div class="stock-event">📰 ${esc(event)}</div>` : ''}
                ${analysis ? `<div class="stock-analysis">${esc(analysis)}</div>` : ''}
                <div class="stock-confidence">${stars}</div>
            </div>`;
        }
    }

    container.innerHTML = html;
}

// ==================== 键盘快捷键 ====================
document.addEventListener('keydown', e => {
    switch (e.key) {
        case ' ': e.preventDefault(); togglePlayback(); break;
        case '1': switchLanguage('chinese'); break;
        case '2': switchLanguage('english'); break;
        case '3': switchLanguage('cantonese'); break;
    }
});

document.addEventListener('DOMContentLoaded', init);
