// Google Forms (replace with your live form URLs)
const FEEDBACK_FORM_URL = "https://forms.gle/jWRDuhSsNjv4ESK76";
// Privacy-friendly analytics (replace with your GoatCounter URL)
const GOATCOUNTER_URL = "https://thracion.goatcounter.com/count";

const SORT_OPTIONS = [
    {
        value: "total-roi",
        label: "Total ROI",
        direction: "desc",
        compare: (a, b) => b.totalROIValue - a.totalROIValue
    },
    {
        value: "jackpot-roi",
        label: "Jackpot ROI",
        direction: "desc",
        compare: (a, b) => b.jackpotROIValue - a.jackpotROIValue
    },
    {
        value: "jackpot",
        label: "Jackpot Size",
        direction: "desc",
        compare: (a, b) => b.jackpotValue - a.jackpotValue
    },
    {
        value: "next-draw",
        label: "Next Draw",
        direction: "asc",
        compare: (a, b) => {
            const aTime = a.nextDrawDate ? a.nextDrawDate.getTime() : Number.POSITIVE_INFINITY;
            const bTime = b.nextDrawDate ? b.nextDrawDate.getTime() : Number.POSITIVE_INFINITY;
            return aTime - bTime;
        }
    }
];

const LOGO_MAP = [
    { match: key => key.includes("eurojackpot"), label: "EUROJACKPOT", background: "#f1c40f", foreground: "#1c1c1c" },
    { match: key => key.includes("euromillions"), label: "EUROMILLIONS", background: "#1e88e5", foreground: "#ffd54f" },
    { match: key => key.includes("superenalotto"), label: "SUPERENALOTTO", background: "#8e24aa", foreground: "#ffffff" },
    { match: key => key.includes("uk lotto"), label: "UK LOTTO", background: "#d32f2f", foreground: "#ffffff" },
    { match: key => key.includes("german lotto"), label: "GERMAN LOTTO", background: "#000000", foreground: "#ffcc00" },
    { match: key => key.includes("french loto"), label: "FRENCH LOTO", background: "#0055a4", foreground: "#ef4135" },
    { match: key => key.includes("irish lotto"), label: "IRISH LOTTO", background: "#169b62", foreground: "#ff883e" },
    { match: key => key.includes("swiss lotto"), label: "SWISS LOTTO", background: "#ff0000", foreground: "#ffffff" },
    { match: key => key.includes("austrian lotto"), label: "AUSTRIAN LOTTO", background: "#ed2939", foreground: "#ffffff" },
    { match: key => key.includes("viking"), label: "VIKINGLOTTO", background: "#2196f3", foreground: "#ffffff" },
    { match: key => key.includes("powerball"), label: "POWERBALL", background: "#e53935", foreground: "#ffffff" },
    { match: key => key.includes("mega millions"), label: "MEGA MILLIONS", background: "#1565c0", foreground: "#ffffff" },
    { match: key => key.includes("finnish lotto") || key === "lotto", label: "FINNISH LOTTO", background: "#ef5350", foreground: "#ffffff" }
];

const state = {
    sortMode: SORT_OPTIONS[0].value
};

let appData = null;
const logoCache = new Map();

function setState(partial) {
    Object.assign(state, partial);
    if (appData) {
        render(appData);
    }
}

async function loadData() {
    try {
        // TRICK: Add "?t=" + current timestamp
        // Browser sees: "lottery_data.json?t=1769251023456"
        // Since the number changes every second, the browser MUST fetch a fresh copy.
        const url = `lottery_data.json?t=${new Date().getTime()}`;
        
        // EXTRA SAFETY: Tell the fetch API explicitly "no caching"
        const response = await fetch(url, { cache: "no-store" });
        
        if (!response.ok) throw new Error("File not found");
        
        appData = await response.json();
        render(appData);
    } catch (error) {
        console.error("Error loading data:", error);
        document.getElementById('app').innerHTML = "<p>Could not load data.</p>";
    }
}

function calculateMetrics(game) {
    // 1. Jackpot EV (Jackpot / Odds)
    const jackpotEV = game.jackpot / game.odds_jackpot;
    
    // 2. Base EV (Expected return from smaller prizes)
    // Price * RTP for non-jackpot tiers
    const baseEV = game.price * game.base_rtp;
    
    // 3. Total EV
    const totalEV = jackpotEV + baseEV;

    // 4. ROIs
    const jackpotROI = ((jackpotEV / game.price) * 100).toFixed(1);
    const totalROI = ((totalEV / game.price) * 100).toFixed(1); // Usually expressed as Return % (e.g. 80%)

    return { jackpotROI, totalROI };
}

function parseDate(input, options = {}) {
    if (!input || input === "Unknown") return null;
    const rawValue = options.dateOnly ? input.split(" ")[0] : input;
    const normalized = rawValue.includes("T") ? rawValue : rawValue.replace(" ", "T");
    const parsed = new Date(normalized);
    if (Number.isNaN(parsed.getTime())) return null;
    return parsed;
}

function formatInternationalDate(dateTime) {
    if (!dateTime) return '';
    if (dateTime === 'Unknown') return dateTime;
    const parsed = parseDate(dateTime, { dateOnly: true });
    if (!parsed) return dateTime.split(' ')[0];
    return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long' }).format(parsed);
}

function formatInternationalDateTime(dateTime) {
    if (!dateTime) return '';
    const parsed = parseDate(dateTime);
    if (!parsed) return dateTime;
    return new Intl.DateTimeFormat('en-GB', {
        day: 'numeric',
        month: 'long',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    }).format(parsed);
}

function makeLogo(label, background, foreground) {
    const normalizedLabel = String(label || '');
    const isLongLabel = normalizedLabel.length > 12;
    const fontSize = isLongLabel ? 22 : 28;
    const textLength = isLongLabel ? '200' : null;
    const lengthAdjust = isLongLabel ? 'spacingAndGlyphs' : null;
    const textLengthAttr = textLength ? `textLength="${textLength}"` : '';
    const lengthAdjustAttr = lengthAdjust ? `lengthAdjust="${lengthAdjust}"` : '';
    const svg = `
        <svg xmlns="http://www.w3.org/2000/svg" width="240" height="96" viewBox="0 0 240 96">
            <rect width="240" height="96" rx="16" fill="${background}"/>
            <text x="120" y="58" font-family="Segoe UI, Arial, sans-serif" font-size="${fontSize}" font-weight="700" text-anchor="middle" fill="${foreground}" ${textLengthAttr} ${lengthAdjustAttr}>
                ${normalizedLabel}
            </text>
        </svg>
    `;
    return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function getGameImage(gameName) {
    const key = (gameName || '').toLowerCase();
    if (logoCache.has(key)) return logoCache.get(key);
    const entry = LOGO_MAP.find(({ match }) => match(key));
    const logo = entry
        ? makeLogo(entry.label, entry.background, entry.foreground)
        : makeLogo('LOTTO', '#ef5350', '#ffffff');
    logoCache.set(key, logo);
    return logo;
}

function buildViewModels(games) {
    return games.map(game => {
        const metrics = calculateMetrics(game);
        return {
            game,
            metrics,
            totalROIValue: parseFloat(metrics.totalROI),
            jackpotROIValue: parseFloat(metrics.jackpotROI),
            jackpotValue: game.jackpot,
            nextDrawDate: parseDate(game.next_draw)
        };
    });
}

function applyFilters(viewModels) {
    return viewModels;
}

function applySort(viewModels, sortMode) {
    const option = SORT_OPTIONS.find(item => item.value === sortMode) || SORT_OPTIONS[0];
    return [...viewModels].sort(option.compare);
}

function updateSortIndicator() {
    const indicator = document.getElementById('sort-direction');
    const option = SORT_OPTIONS.find(item => item.value === state.sortMode) || SORT_OPTIONS[0];
    indicator.textContent = option.direction === "asc" ? "↑" : "↓";
}

function renderSortOptions() {
    const sortSelect = document.getElementById('sort-select');
    sortSelect.innerHTML = "";
    SORT_OPTIONS.forEach(option => {
        const item = document.createElement("option");
        item.value = option.value;
        item.textContent = option.label;
        sortSelect.appendChild(item);
    });
    sortSelect.value = state.sortMode;
}

function buildCardNode({ game, metrics }) {
    const isPositive = parseFloat(metrics.totalROI) > 100;
    const badgeClass = isPositive ? 'good' : (metrics.totalROI > 60 ? 'mid' : 'bad');
    const nameKey = (game.name || '').toLowerCase();
    const borderColor = isPositive ? '#4caf50' : (
        nameKey.includes('eurojackpot') ? '#e6b800' :
        nameKey.includes('euromillions') ? '#1e88e5' :
        nameKey.includes('superenalotto') ? '#8e24aa' :
        nameKey.includes('uk lotto') ? '#d32f2f' :
        nameKey.includes('german lotto') ? '#ffcc00' :
        nameKey.includes('french loto') ? '#0055a4' :
        nameKey.includes('irish lotto') ? '#169b62' :
        nameKey.includes('swiss lotto') ? '#ff0000' :
        nameKey.includes('austrian lotto') ? '#ed2939' :
        nameKey.includes('powerball') ? '#e53935' :
        nameKey.includes('mega millions') ? '#1565c0' :
        nameKey.includes('viking') ? '#2196f3' :
        '#ef5350'
    );
    const wrapper = document.createElement("div");
    wrapper.innerHTML = `
        <div class="card" style="border-top-color: ${borderColor}">
            <img class="game-logo" src="${getGameImage(game.name)}" alt="${game.name} logo" />
            <!-- <h3>${game.name}</h3> -->
            <div class="jackpot">${game.currency}${(game.jackpot / 1000000).toFixed(1)}M</div>
            <div class="roi-badge ${badgeClass}">
                <span class="label-with-help">
                    Total ROI
                    <button
                        class="help-button"
                        type="button"
                        aria-label="Total ROI explained"
                        data-tooltip="Total expected return per ticket spent. Calculated as: (Jackpot ÷ Odds of Winning + Ticket Price × RTP for smaller prizes) ÷ Ticket Price × 100%. Example: If you spend $100, an 80% ROI means you'd expect $80 back on average. 100% = break-even, >100% = positive expected value."
                    >?</button>
                </span>
                : ${metrics.totalROI}%
            </div>
            
            <div class="stat-row">
                <span class="label label-with-help">
                    Jackpot Only ROI
                    <button
                        class="help-button"
                        type="button"
                        aria-label="Jackpot-only ROI explained"
                        data-tooltip="Expected return from ONLY the jackpot prize, excluding all smaller prizes. Calculated as: (Jackpot Amount ÷ Odds of Winning Jackpot) ÷ Ticket Price × 100%. Example: $100M jackpot with 1-in-300M odds and $2 ticket = ($100M ÷ 300M) ÷ $2 × 100% = 16.7% ROI."
                    >?</button>
                </span>
                <span>${metrics.jackpotROI}%</span>
            </div>
            <div class="stat-row">
                <span class="label">Ticket Price</span>
                <span>${game.currency}${game.price.toFixed(2)}</span>
            </div>
            <div class="stat-row">
                <span class="label">Next Draw</span>
                <span>${formatInternationalDate(game.next_draw)}</span>
            </div>
        </div>
    `;
    return wrapper.firstElementChild;
}

function render(data) {
    const container = document.getElementById('app');
    container.innerHTML = '';
    
    const updatedDate = formatInternationalDateTime(data.last_updated);
    document.getElementById('last-updated').innerText = "Last Updated: " + updatedDate + " (UTC)";
    const feedbackLink = document.getElementById('feedback-link');
    if (FEEDBACK_FORM_URL && !FEEDBACK_FORM_URL.includes("FORM_ID")) {
        feedbackLink.href = FEEDBACK_FORM_URL;
    } else {
        feedbackLink.href = "#";
        feedbackLink.title = "Set FEEDBACK_FORM_URL to enable feedback";
    }

    updateSortIndicator();

    const viewModels = buildViewModels(data.games);
    const filteredViewModels = applyFilters(viewModels);
    const sortedViewModels = applySort(filteredViewModels, state.sortMode);

    const fragment = document.createDocumentFragment();
    sortedViewModels.forEach(model => {
        fragment.appendChild(buildCardNode(model));
    });
    container.appendChild(fragment);
}

function trackVisit() {
    if (!GOATCOUNTER_URL || GOATCOUNTER_URL.includes("YOURCODE")) return;
    const img = new Image();
    const url = new URL(GOATCOUNTER_URL);
    url.searchParams.set("p", window.location.pathname);
    url.searchParams.set("t", document.title);
    img.src = url.toString();
}

function initControls() {
    renderSortOptions();
    const sortSelect = document.getElementById('sort-select');
    sortSelect.addEventListener('change', () => {
        setState({ sortMode: sortSelect.value });
    });
}

initControls();
loadData();
trackVisit();
