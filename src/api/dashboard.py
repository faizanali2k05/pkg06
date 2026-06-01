from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Web Interface"])

@router.get("/", response_class=HTMLResponse)
async def get_dashboard() -> HTMLResponse:
    """Renders the master glassmorphic trading dashboard of ApexQuant."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ApexQuant | Trading Terminal</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-color: #0b0f19;
            --panel-bg: rgba(22, 29, 49, 0.65);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --accent-blue: #3b82f6;
            --accent-glow: rgba(59, 130, 246, 0.4);
            --green-glow: rgba(16, 185, 129, 0.2);
            --red-glow: rgba(239, 68, 68, 0.2);
            --green: #10b981;
            --red: #ef4444;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            overflow-x: hidden;
            background-image: radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.08) 0%, transparent 40%),
                              radial-gradient(circle at 90% 80%, rgba(16, 185, 129, 0.05) 0%, transparent 40%);
            background-attachment: fixed;
        }

        /* Glassmorphism Styles */
        .glass-panel {
            background: var(--panel-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            transition: all 0.3s ease;
        }

        .glass-panel:hover {
            border-color: rgba(255, 255, 255, 0.15);
            box-shadow: 0 8px 32px 0 rgba(59, 130, 246, 0.05);
        }

        /* Layout Grid */
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 24px;
            display: grid;
            grid-gap: 24px;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 20px;
            margin-bottom: 10px;
        }

        .logo-section h1 {
            font-size: 28px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(to right, #3b82f6, #10b981);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .logo-section span {
            font-size: 12px;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            padding: 8px 16px;
            border-radius: 30px;
            font-size: 14px;
            color: var(--green);
            box-shadow: 0 0 15px var(--green-glow);
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            background-color: var(--green);
            border-radius: 50%;
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.9); opacity: 1; }
            50% { transform: scale(1.3); opacity: 0.5; }
            100% { transform: scale(0.9); opacity: 1; }
        }

        /* Top metrics summary */
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            grid-gap: 24px;
        }

        .metric-card {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .metric-title {
            font-size: 13px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .metric-value {
            font-size: 32px;
            font-weight: 600;
        }

        .green-text { color: var(--green); }
        .red-text { color: var(--red); }

        /* Main Workspace Grid */
        .workspace-grid {
            display: grid;
            grid-template-columns: 1fr 2fr;
            grid-gap: 24px;
        }

        @media (max-width: 1024px) {
            .workspace-grid {
                grid-template-columns: 1fr;
            }
        }

        /* Forms, Buttons, Toggles */
        .card-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .strategy-toggle-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 14px 0;
            border-bottom: 1px solid var(--border-color);
        }

        .strategy-toggle-row:last-child {
            border-bottom: none;
        }

        .strategy-info h4 {
            font-size: 15px;
            font-weight: 600;
        }

        .strategy-info p {
            font-size: 12px;
            color: var(--text-muted);
        }

        /* Sliding Switch Toggle */
        .switch {
            position: relative;
            display: inline-block;
            width: 46px;
            height: 24px;
        }

        .switch input { opacity: 0; width: 0; height: 0; }

        .slider {
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background-color: rgba(255, 255, 255, 0.1);
            transition: .3s;
            border-radius: 24px;
        }

        .slider:before {
            position: absolute;
            content: "";
            height: 18px; width: 18px;
            left: 3px; bottom: 3px;
            background-color: white;
            transition: .3s;
            border-radius: 50%;
        }

        input:checked + .slider { background-color: var(--accent-blue); box-shadow: 0 0 10px var(--accent-glow); }
        input:checked + .slider:before { transform: translateX(22px); }

        /* Tables */
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }

        th {
            text-align: left;
            padding: 12px 16px;
            color: var(--text-muted);
            font-weight: 400;
            border-bottom: 1px solid var(--border-color);
        }

        td {
            padding: 16px;
            border-bottom: 1px solid var(--border-color);
        }

        tr:last-child td {
            border-bottom: none;
        }

        /* Backtester styling */
        .backtest-form {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)) auto;
            grid-gap: 16px;
            align-items: flex-end;
            margin-bottom: 24px;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .form-group label {
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
        }

        select, input[type="number"] {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            padding: 10px 14px;
            border-radius: 8px;
            color: var(--text-main);
            font-family: inherit;
            outline: none;
            transition: border 0.3s ease;
        }

        select:focus, input[type="number"]:focus {
            border-color: var(--accent-blue);
        }

        .btn {
            background: linear-gradient(135deg, var(--accent-blue), #2563eb);
            border: none;
            color: white;
            padding: 11px 24px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px var(--accent-glow);
        }

        .btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 20px var(--accent-glow);
        }

        .btn:active {
            transform: translateY(0);
        }

        /* Backtester Terminal output card */
        .terminal {
            background: rgba(5, 8, 16, 0.95);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            line-height: 1.6;
            color: #38bdf8;
            max-height: 380px;
            overflow-y: auto;
            border-left: 4px solid var(--accent-blue);
            white-space: pre-wrap;
        }

        .balance-badge {
            background: rgba(255, 255, 255, 0.04);
            padding: 4px 10px;
            border-radius: 6px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- HEADER -->
        <header class="glass-panel" style="padding: 16px 24px;">
            <div class="logo-section">
                <h1>ApexQuant</h1>
                <span>Trading Engine v1.0.0</span>
            </div>
            <div class="status-badge">
                <div class="pulse-dot"></div>
                <span>SYSTEM ONLINE (DRY RUN ACTIVE)</span>
            </div>
        </header>

        <!-- TOP SUMMARY BLOCK -->
        <div class="summary-grid">
            <div class="glass-panel metric-card">
                <span class="metric-title">Portfolio Equity</span>
                <span class="metric-value" id="equity-val">10,000.00 <span style="font-size: 16px; color: var(--text-muted);">USDT</span></span>
            </div>
            <div class="glass-panel metric-card">
                <span class="metric-title">Daily Drawdown</span>
                <span class="metric-value green-text" id="drawdown-val">0.00%</span>
            </div>
            <div class="glass-panel metric-card">
                <span class="metric-title">Open Positions</span>
                <span class="metric-value" id="open-positions-count">0 / 3</span>
            </div>
            <div class="glass-panel metric-card">
                <span class="metric-title">Risk Allocation Limit</span>
                <span class="metric-value" style="color: #60a5fa;">1.0% <span style="font-size: 16px; color: var(--text-muted);">per Trade</span></span>
            </div>
        </div>

        <!-- MAIN WORKSPACE -->
        <div class="workspace-grid">
            <!-- LEFT PANEL: ALIGNMENT & STRATEGY STATE -->
            <div style="display: flex; flex-direction: column; gap: 24px;">
                <!-- Wallet Balance list -->
                <div class="glass-panel">
                    <div class="card-title">
                        <span>Asset Allocations</span>
                        <span class="balance-badge" style="color: var(--accent-blue);">Spot Wallet</span>
                    </div>
                    <div id="balance-container" style="display: flex; flex-direction: column; gap: 12px;">
                        <!-- JS injected assets -->
                        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-color); padding-bottom: 8px;">
                            <span style="color: var(--text-muted);">USDT</span>
                            <span style="font-weight: 600;">10,000.00</span>
                        </div>
                    </div>
                </div>

                <!-- Pluggable strategy control -->
                <div class="glass-panel">
                    <div class="card-title">Trading Strategies</div>
                    <div class="strategy-toggle-row">
                        <div class="strategy-info">
                            <h4>EMA Trend Pullback</h4>
                            <p>EMA50 > EMA200 pullback filter</p>
                        </div>
                        <label class="switch">
                            <input type="checkbox" checked id="toggle-ema" onchange="toggleStrategy('EMA_Trend_Pullback', this.checked)">
                            <span class="slider"></span>
                        </label>
                    </div>
                    <div class="strategy-toggle-row">
                        <div class="strategy-info">
                            <h4>Channel Breakout</h4>
                            <p>Donchian resistance break rules</p>
                        </div>
                        <label class="switch">
                            <input type="checkbox" checked id="toggle-breakout" onchange="toggleStrategy('Channel_Breakout', this.checked)">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>
            </div>

            <!-- RIGHT PANEL: ACTIVE POSITIONS & LIVE GRIDS -->
            <div style="display: flex; flex-direction: column; gap: 24px;">
                <div class="glass-panel">
                    <div class="card-title">Live Open Positions</div>
                    <div style="overflow-x: auto;">
                        <table>
                            <thead>
                                <tr>
                                    <th>Asset</th>
                                    <th>Strategy</th>
                                    <th>Qty</th>
                                    <th>Entry Price</th>
                                    <th>Stop Loss</th>
                                    <th>Take Profit</th>
                                    <th>Unrealized PnL</th>
                                </tr>
                            </thead>
                            <tbody id="positions-table-body">
                                <tr>
                                    <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 32px 0;">No active open positions</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- LOWER WORKSPACE: AUDIT HISTORY -->
        <div class="glass-panel">
            <div class="card-title">Execution Trade Log</div>
            <div style="overflow-x: auto; max-height: 350px;">
                <table>
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Order ID</th>
                            <th>Symbol</th>
                            <th>Side</th>
                            <th>Type</th>
                            <th>Execution Price</th>
                            <th>Filled Qty</th>
                            <th>Commission Fee</th>
                            <th>Strategy</th>
                        </tr>
                    </thead>
                    <tbody id="trades-table-body">
                        <tr>
                            <td colspan="9" style="text-align: center; color: var(--text-muted); padding: 32px 0;">No executed trades in this session</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- DYNAMIC HISTORICAL BACKTEST PANEL -->
        <div class="glass-panel">
            <div class="card-title">Interactive Strategy Backtester</div>
            <div class="backtest-form">
                <div class="form-group">
                    <label for="bt-symbol">Trading Pair</label>
                    <select id="bt-symbol">
                        <option value="BTC/USDT">BTC/USDT</option>
                        <option value="ETH/USDT">ETH/USDT</option>
                        <option value="SOL/USDT">SOL/USDT</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="bt-strategy">Strategy Plugin</label>
                    <select id="bt-strategy">
                        <option value="EMA_Trend_Pullback">EMA Trend Pullback (V1)</option>
                        <option value="Channel_Breakout">Donchian Breakout</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="bt-limit">History Depth (Bars)</label>
                    <select id="bt-limit">
                        <option value="200">200 Candles</option>
                        <option value="500" selected>500 Candles</option>
                        <option value="1000">1000 Candles</option>
                    </select>
                </div>
                <div class="form-group">
                    <label for="bt-tf">Timeframe</label>
                    <select id="bt-tf">
                        <option value="1m">1 Minute</option>
                        <option value="5m" selected>5 Minutes</option>
                        <option value="15m">15 Minutes</option>
                        <option value="1h">1 Hour</option>
                    </select>
                </div>
                <button class="btn" onclick="triggerBacktest()">Simulate Backtest</button>
            </div>
            
            <div class="terminal" id="terminal-log">Waiting to launch simulation run...</div>
        </div>
    </div>

    <!-- DYNAMIC JAVASCRIPT LAYER -->
    <script>
        async function fetchSystemData() {
            try {
                // 1. Fetch active positions
                const posRes = await fetch('/api/positions');
                const positions = await posRes.json();
                const posBody = document.getElementById('positions-table-body');
                
                document.getElementById('open-positions-count').innerText = `${positions.length} / 3`;
                
                if (positions.length === 0) {
                    posBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 32px 0;">No active open positions</td></tr>`;
                } else {
                    posBody.innerHTML = positions.map(pos => {
                        const pnlClass = pos.unrealized_pnl >= 0 ? 'green-text' : 'red-text';
                        const sign = pos.unrealized_pnl >= 0 ? '+' : '';
                        return `
                            <tr>
                                <td style="font-weight: 600;">${pos.symbol}</td>
                                <td><span class="balance-badge" style="color: var(--accent-blue);">${pos.strategy_name}</span></td>
                                <td style="font-family: 'JetBrains Mono', monospace;">${pos.qty.toFixed(5)}</td>
                                <td style="font-family: 'JetBrains Mono', monospace;">${pos.entry_price.toFixed(2)}</td>
                                <td style="font-family: 'JetBrains Mono', monospace; color: var(--red);">${pos.stop_loss.toFixed(2)}</td>
                                <td style="font-family: 'JetBrains Mono', monospace; color: var(--green);">${pos.take_profit.toFixed(2)}</td>
                                <td style="font-family: 'JetBrains Mono', monospace;" class="${pnlClass}">${sign}${pos.unrealized_pnl.toFixed(4)} USDT</td>
                            </tr>
                        `;
                    }).join('');
                }

                // 2. Fetch balance allocations
                const balRes = await fetch('/api/balance');
                const balance = await balRes.json();
                const balContainer = document.getElementById('balance-container');
                
                let usdtFree = 10000.0;
                let html = '';
                for (const coin in balance.free) {
                    const totalVal = balance.total[coin];
                    const freeVal = balance.free[coin];
                    if (coin === 'USDT') {
                        usdtFree = freeVal;
                    }
                    html += `
                        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--border-color); padding-bottom: 8px;">
                            <span style="color: var(--text-muted); font-weight: 600;">${coin}</span>
                            <span style="font-family: 'JetBrains Mono', monospace; font-weight: 600;">${totalVal.toFixed(4)} <span style="font-size: 11px; font-weight: 300; color: var(--text-muted);">(${freeVal.toFixed(4)} Free)</span></span>
                        </div>
                    `;
                }
                
                // Account equity simple evaluation: USDT + open positions cost/valuation
                let totalCost = 0;
                positions.forEach(p => {
                    totalCost += (p.qty * p.entry_price) + p.unrealized_pnl;
                });
                const totalEquity = usdtFree + totalCost;
                
                document.getElementById('equity-val').innerHTML = `${totalEquity.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} <span style="font-size: 16px; color: var(--text-muted);">USDT</span>`;
                balContainer.innerHTML = html || `<div style="text-align: center; color: var(--text-muted); padding: 10px 0;">No balances found</div>`;

                // 3. Fetch trade audit logs
                const tradeRes = await fetch('/api/trades?limit=10');
                const trades = await tradeRes.json();
                const tradeBody = document.getElementById('trades-table-body');
                
                if (trades.length === 0) {
                    tradeBody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 32px 0;">No executed trades in this session</td></tr>`;
                } else {
                    tradeBody.innerHTML = trades.map(t => {
                        const sideClass = t.side === 'BUY' ? 'green-text' : 'red-text';
                        return `
                            <tr>
                                <td style="color: var(--text-muted); font-size: 12px;">${t.timestamp}</td>
                                <td style="font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--text-muted);">${t.exchange_order_id}</td>
                                <td style="font-weight: 600;">${t.symbol}</td>
                                <td class="${sideClass}" style="font-weight: 600;">${t.side}</td>
                                <td>${t.type}</td>
                                <td style="font-family: 'JetBrains Mono', monospace;">${t.price.toFixed(2)}</td>
                                <td style="font-family: 'JetBrains Mono', monospace;">${t.qty.toFixed(5)}</td>
                                <td style="font-family: 'JetBrains Mono', monospace; color: var(--text-muted);">${t.commission.toFixed(4)}</td>
                                <td><span class="balance-badge" style="color: var(--accent-blue);">${t.strategy_name}</span></td>
                            </tr>
                        `;
                    }).join('');
                }

            } catch (err) {
                console.error("Dashboard failed to poll updates: ", err);
            }
        }

        async function toggleStrategy(name, enabled) {
            try {
                await fetch('/api/strategy/toggle', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ strategy_name: name, enabled: enabled })
                });
            } catch (err) {
                console.error("Failed to toggle strategy: ", err);
            }
        }

        async function triggerBacktest() {
            const terminal = document.getElementById('terminal-log');
            terminal.innerText = "Initiating historical simulations... Download candles in progress...";
            
            const req = {
                symbol: document.getElementById('bt-symbol').value,
                strategy_name: document.getElementById('bt-strategy').value,
                limit: parseInt(document.getElementById('bt-limit').value),
                timeframe: document.getElementById('bt-tf').value
            };
            
            try {
                const res = await fetch('/api/backtest', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(req)
                });
                const data = await res.json();
                
                if (res.status === 200) {
                    terminal.innerText = data.text_report;
                    // Automatically trigger standard refresh
                    fetchSystemData();
                } else {
                    terminal.innerText = `Error: ${data.detail || 'Backtest simulation run failed.'}`;
                }
            } catch (err) {
                terminal.innerText = `Network crash error: ${err.message}`;
            }
        }

        // Periodically poll updates
        fetchSystemData();
        setInterval(fetchSystemData, 3000);
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content, status_code=200)
