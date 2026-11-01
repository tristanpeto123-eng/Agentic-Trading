"""
Auto-labeller + classifier for one "skill" at a time (FVG, liquidity sweep).

Pipeline:
  1. Rule-based detector finds candidate setups (objective definitions)
  2. Triple-barrier labeller scores each: TP before SL = 1, else 0
  3. Gradient-boosting classifier learns which setups are high quality
  4. Walk-forward validation with purging (no leakage)

Usage:
  python autolabel.py --demo --skill fvg
  python autolabel.py --csv EURUSD_M15.csv --skill sweep
CSV columns: time, open, high, low, close [, volume]  (time parseable by pandas)
Skills: fvg, sweep, breakout, keylevel, volspike (volspike needs volume)
"""
import argparse
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

# ---------- config ----------
RR = 2.0          # take-profit = RR * ATR
SL_ATR = 1.0      # stop-loss = SL_ATR * ATR
HORIZON = 24      # max bars to hold before timeout (counted as loss)
MIN_GAP_ATR = 0.3 # min FVG size in ATR
SWING_N = 5       # bars each side to confirm a swing high/low


# ---------- indicators ----------
def atr(df, n=14):
    pc = df.close.shift(1)
    tr = pd.concat([df.high - df.low, (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


# ---------- detectors (signal on bar i close, direction +1 long / -1 short) ----------
def detect_fvg(df, a):
    gap_up = df.low - df.high.shift(2)      # bullish gap between candle i-2 high and candle i low
    gap_dn = df.low.shift(2) - df.high      # bearish gap
    bull = gap_up >= MIN_GAP_ATR * a
    bear = gap_dn >= MIN_GAP_ATR * a
    direction = pd.Series(0, index=df.index)
    direction[bull] = 1
    direction[bear] = -1
    size = pd.concat([gap_up, gap_dn], axis=1).max(axis=1) / a
    return direction, size


def detect_sweep(df, a, n=SWING_N):
    h, l = df.high, df.low
    sh = h.where(h == h.rolling(2 * n + 1, center=True).max())
    sl = l.where(l == l.rolling(2 * n + 1, center=True).min())
    # swing at j is only confirmed at j+n; use levels known as of the previous bar
    last_sh = sh.shift(n).ffill().shift(1)
    last_sl = sl.shift(n).ffill().shift(1)
    bear = (h > last_sh) & (df.close < last_sh)   # swept highs, closed back below -> short
    bull = (l < last_sl) & (df.close > last_sl)   # swept lows, closed back above -> long
    direction = pd.Series(0, index=df.index)
    direction[bull] = 1
    direction[bear] = -1
    depth = pd.Series(0.0, index=df.index)
    depth[bear] = (h - last_sh)[bear] / a[bear]
    depth[bull] = (last_sl - l)[bull] / a[bull]
    return direction, depth

def detect_breakout(df, a, n=20):
    hh = df.high.rolling(n).max().shift(1)
    ll = df.low.rolling(n).min().shift(1)
    bull = (df.close > hh) & (df.close.shift(1) <= hh.shift(1))   # first close beyond range
    bear = (df.close < ll) & (df.close.shift(1) >= ll.shift(1))
    direction = pd.Series(0, index=df.index)
    direction[bull] = 1
    direction[bear] = -1
    strength = pd.Series(0.0, index=df.index)
    strength[bull] = ((df.close - hh) / a)[bull]
    strength[bear] = ((ll - df.close) / a)[bear]
    return direction, strength


def detect_keylevel(df, a):
    """Rejection of the previous day's high/low (wick through, close back inside)."""
    day = pd.to_datetime(df["time"]).dt.date
    g = df.groupby(day)
    pdh = day.map(g.high.max().shift(1))
    pdl = day.map(g.low.min().shift(1))
    pdh, pdl = pd.Series(pdh.values, index=df.index), pd.Series(pdl.values, index=df.index)
    bear = (df.high >= pdh) & (df.close < pdh)
    bull = (df.low <= pdl) & (df.close > pdl)
    direction = pd.Series(0, index=df.index)
    direction[bull] = 1
    direction[bear] = -1
    strength = pd.Series(0.0, index=df.index)
    strength[bear] = ((df.high - df.close) / a)[bear]   # rejection wick size
    strength[bull] = ((df.close - df.low) / a)[bull]
    return direction, strength


def detect_volspike(df, a, n=50):
    """PROXY for block/institutional activity: abnormal tick volume + strong body."""
    if "volume" not in df:
        raise SystemExit("volspike skill needs a 'volume' column")
    z = (df.volume - df.volume.rolling(n).mean()) / df.volume.rolling(n).std()
    body = (df.close - df.open)
    big = (z >= 2) & (body.abs() >= 0.5 * a)
    direction = pd.Series(0, index=df.index)
    direction[big & (body > 0)] = 1
    direction[big & (body < 0)] = -1
    return direction, z.where(big, 0.0)


DETECTORS = {"fvg": detect_fvg, "sweep": detect_sweep, "breakout": detect_breakout,
             "keylevel": detect_keylevel, "volspike": detect_volspike}


# ---------- triple-barrier labeller ----------
def triple_barrier(df, a, idx, dirs):
    o, h, l = df.open.values, df.high.values, df.low.values
    av = a.values
    n = len(df)
    labels, t_end = [], []
    for i, d in zip(idx, dirs):
        e = i + 1
        if e + HORIZON > n or np.isnan(av[i]):
            labels.append(np.nan); t_end.append(np.nan); continue
        entry, risk = o[e], av[i]
        tp = entry + d * RR * risk
        sl = entry - d * SL_ATR * risk
        out, end = 0, e + HORIZON - 1
        for k in range(e, e + HORIZON):
            hit_sl = l[k] <= sl if d == 1 else h[k] >= sl
            hit_tp = h[k] >= tp if d == 1 else l[k] <= tp
            if hit_sl:           # conservative: SL wins if both hit in one bar
                out, end = 0, k; break
            if hit_tp:
                out, end = 1, k; break
        labels.append(out); t_end.append(end)
    return np.array(labels, dtype=float), np.array(t_end, dtype=float)


# ---------- dataset ----------
def build_dataset(df, skill):
    a = atr(df)
    direction, strength = DETECTORS[skill](df, a)
    feats = pd.DataFrame(index=df.index)
    feats["direction"] = direction
    feats["strength"] = strength
    feats["atr_pct"] = a / df.close
    for w in (1, 5, 20):
        feats[f"ret{w}"] = df.close.pct_change(w) * direction  # signed with trade direction
    feats["dist_sma50"] = (df.close - df.close.rolling(50).mean()) / a * direction
    feats["rsi"] = rsi(df.close)
    t = pd.to_datetime(df["time"])
    feats["hour_sin"] = np.sin(2 * np.pi * t.dt.hour / 24)
    feats["hour_cos"] = np.cos(2 * np.pi * t.dt.hour / 24)

    cand = np.where(direction.values != 0)[0]
    y, t_end = triple_barrier(df, a, cand, direction.values[cand])
    ds = feats.iloc[cand].copy()
    ds["y"], ds["t_end"], ds["i"] = y, t_end, cand
    return ds.dropna().reset_index(drop=True)


# ---------- walk-forward with purging ----------
def walk_forward(ds, n_splits=5, min_train_frac=0.4):
    X_cols = [c for c in ds.columns if c not in ("y", "t_end", "i")]
    n = len(ds)
    start = int(n * min_train_frac)
    edges = np.linspace(start, n, n_splits + 1, dtype=int)
    results, oos = [], []
    for k in range(n_splits):
        te = ds.iloc[edges[k]:edges[k + 1]]
        test_start_bar = te["i"].min()
        tr = ds.iloc[:edges[k]]
        tr = tr[tr["t_end"] < test_start_bar]       # purge overlapping labels
        if tr["y"].nunique() < 2 or te["y"].nunique() < 2:
            continue
        model = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05,
                                               max_iter=200, l2_regularization=1.0)
        model.fit(tr[X_cols], tr["y"])
        p = model.predict_proba(te[X_cols])[:, 1]
        auc = roc_auc_score(te["y"], p)
        top = te["y"][p >= np.quantile(p, 0.75)].mean()
        results.append((k, len(tr), len(te), auc, te["y"].mean(), top))
        oos.append(pd.DataFrame({"i": te["i"].values, "p": p, "y": te["y"].values}))
    return results, (pd.concat(oos) if oos else None)


# ---------- demo data ----------
def demo_data(n=30000, seed=0):
    rng = np.random.default_rng(seed)
    close = 1.1 + np.cumsum(rng.normal(0, 0.0005, n))
    open_ = np.r_[close[0], close[:-1]]
    spread = np.abs(rng.normal(0, 0.0003, n))
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    t = pd.date_range("2022-01-03", periods=n, freq="15min")
    vol = rng.lognormal(6, 0.5, n)
    return pd.DataFrame({"time": t, "open": open_, "high": high, "low": low, "close": close, "volume": vol})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--skill", choices=DETECTORS, default="fvg")
    args = ap.parse_args()
    df = demo_data() if args.demo else pd.read_csv(args.csv)
    df = df.sort_values("time").reset_index(drop=True)

    ds = build_dataset(df, args.skill)
    print(f"{args.skill}: {len(ds)} labelled setups, win rate {ds['y'].mean():.1%} "
          f"(breakeven at RR {RR} is {SL_ATR / (SL_ATR + RR):.1%})")
    res, oos = walk_forward(ds)
    print("fold  train  test   AUC    base_win  top25%_win")
    for k, ntr, nte, auc, base, top in res:
        print(f"{k:<5} {ntr:<6} {nte:<6} {auc:.3f}  {base:.1%}     {top:.1%}")
    if res:
        print(f"mean AUC {np.mean([r[3] for r in res]):.3f}  (0.5 = no skill)")
    ds.to_csv(f"{args.skill}_labelled.csv", index=False)
    print(f"saved {args.skill}_labelled.csv")


if __name__ == "__main__":
    main()
