#!/usr/bin/env python3
"""Regenerate every figure in docs/research/def-scoring-distribution.md
from the committed CSV. No API calls.

Usage: analyse-def-calibration.py [path/to/def-calibration-team-games.csv]
"""
import collections, csv, os, statistics as st, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, '..', 'def-calibration-team-games.csv')
NUM_COLS = ('season week team_id points_for points_allowed sacks def_interceptions '
            'int_return_yards int_tds fumbles_recovered defensive_tds kick_return_tds '
            'punt_return_tds tackles_for_loss passes_deflected qb_hurries safeties '
            'opp_fumbles_lost opp_ints_thrown').split()

# Yahoo/ESPN standard NFL DEF/ST schedule.
NFL_BANDS = [(0, 0, '0', 10), (1, 6, '1-6', 7), (7, 13, '7-13', 4), (14, 20, '14-20', 1),
             (21, 27, '21-27', 0), (28, 34, '28-34', -1), (35, 10**9, '35+', -4)]
NFL_PLAY = {'sacks': 1, 'opp_ints_thrown': 2, 'opp_fumbles_lost': 2,
            'defensive_tds': 6, 'st_tds': 6, 'safeties': 2}
SEGMENTS = ('conference', 'non-conf FBS', 'FCS')


def load(path):
    rows = []
    for r in csv.DictReader(open(path)):
        for c in NUM_COLS:
            v = float(r[c])
            r[c] = int(v) if v.is_integer() else v   # sacks and TFL arrive as halves
        r['segment'] = ('FCS' if r['opponent_classification'] != 'fbs'
                        else 'conference' if r['conference_game'] == 'True' else 'non-conf FBS')
        r['st_tds'] = r['kick_return_tds'] + r['punt_return_tds']
        rows.append(r)
    return rows


def pct(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100
    f = int(k)
    return xs[f] + (xs[min(f + 1, len(xs) - 1)] - xs[f]) * (k - f)


def desc(xs):
    return (f'n={len(xs):5d}  mean {st.mean(xs):5.2f}  median {st.median(xs):5.1f}  '
            f'sd {st.pstdev(xs):5.2f}  p25 {pct(xs,25):4.1f}  p75 {pct(xs,75):4.1f}  max {max(xs)}')


def band_points(p):
    return next(pts for lo, hi, _, pts in NFL_BANDS if lo <= p <= hi)


def nfl_score(r):
    return band_points(r['points_allowed']) + sum(r[k] * v for k, v in NFL_PLAY.items())


def main(path):
    rows = load(path)
    reg = [r for r in rows if r['season_type'] == 'regular']
    post = [r for r in rows if r['season_type'] != 'regular']
    seg = {s: [r for r in reg if r['segment'] == s] for s in SEGMENTS}
    pa = [r['points_allowed'] for r in reg]

    print('=== 1. POINTS ALLOWED (regular season) ===')
    print('all           ', desc(pa))
    for s in SEGMENTS:
        print(f'{s:<14}', desc([r['points_allowed'] for r in seg[s]]))
    print('ex-FCS        ', desc([r['points_allowed'] for r in reg if r['segment'] != 'FCS']))
    print('postseason    ', desc([r['points_allowed'] for r in post]))
    print('\ndeciles, all:', [round(pct(pa, p), 1) for p in range(0, 101, 10)])
    for s in SEGMENTS:
        print(f'deciles, {s}:', [round(pct([r['points_allowed'] for r in seg[s]], p), 1) for p in range(0, 101, 10)])
    print('\nby season:')
    for y in sorted({r['season'] for r in reg}):
        print(f'  {y}        ', desc([r['points_allowed'] for r in reg if r['season'] == y]))
    print('\nhome/away:', {h: round(st.mean([r['points_allowed'] for r in reg if r['home_away'] == h]), 2)
                           for h in ('home', 'away')})

    print('\n=== 2. THE LOW END (regular season) ===')
    for t in (0, 3, 7, 10, 14):
        sub = [r for r in reg if r['points_allowed'] <= t]
        print(f'<= {t:2d} allowed: {len(sub):4d} ({len(sub)/len(reg):5.1%})  {dict(collections.Counter(r["segment"] for r in sub))}')
    print('P(shutout | segment):', {s: f'{sum(1 for r in seg[s] if r["points_allowed"]==0)/len(seg[s]):.1%}' for s in SEGMENTS})
    print('P(>=35 allowed | segment):', {s: f'{sum(1 for r in seg[s] if r["points_allowed"]>=35)/len(seg[s]):.1%}' for s in SEGMENTS})
    print('FCS share of all team-games: %.1f%%' % (100 * len(seg['FCS']) / len(reg)))

    print('\n=== 3. PLAY-BASED STATS (regular season) ===')
    fields = [('sacks', 'sacks'), ('opp_ints_thrown', 'interceptions'),
              ('opp_fumbles_lost', 'fumbles recovered'), ('defensive_tds', 'defensive TDs'),
              ('st_tds', 'special-teams TDs'), ('safeties', 'safeties'),
              ('tackles_for_loss', 'tackles for loss'), ('passes_deflected', 'passes deflected'),
              ('qb_hurries', 'QB hurries'),
              ('def_interceptions', '[raw field] passesIntercepted'),
              ('fumbles_recovered', '[raw field] fumblesRecovered')]
    print(f'{"stat":<32}{"mean":>7}{"sd":>6}{"max":>5}{"P(>=1)":>8}{"P(>=2)":>8}{"P(>=3)":>8}')
    for f, label in fields:
        xs = [r[f] for r in reg]
        print(f'{label:<32}{st.mean(xs):>7.3f}{st.pstdev(xs):>6.2f}{max(xs):>5}'
              f'{sum(1 for x in xs if x>=1)/len(xs):>8.1%}{sum(1 for x in xs if x>=2)/len(xs):>8.1%}'
              f'{sum(1 for x in xs if x>=3)/len(xs):>8.1%}')
    print('\ncount distributions:')
    for f, label in fields[:6]:
        c = collections.Counter(r[f] for r in reg)
        print(f'  {label:<20}', ', '.join(f'{k}:{c[k]/len(reg):.1%}' for k in sorted(c) if k <= 6))
    print('\nmeans by segment:')
    for f, label in fields[:6]:
        print(f'  {label:<20}', {s: round(st.mean([r[f] for r in seg[s]]), 3) for s in SEGMENTS})
    print('\nmeans by season:')
    for y in sorted({r['season'] for r in reg}):
        sub = [r for r in reg if r['season'] == y]
        print(f'  {y}', {f: round(st.mean([r[f] for r in sub]), 3) for f, _ in fields[:6]})

    print('\n=== 4. NFL BANDS APPLIED TO COLLEGE ===')
    print(f'{"band":<8}{"pts":>5}{"all":>9}' + ''.join(f'{s:>14}' for s in SEGMENTS))
    for lo, hi, label, pts in NFL_BANDS:
        share = lambda sub: sum(1 for r in sub if lo <= r['points_allowed'] <= hi) / len(sub)
        print(f'{label:<8}{pts:>5}{share(reg):>9.1%}' + ''.join(f'{share(seg[s]):>14.1%}' for s in SEGMENTS))
    bp = [band_points(r['points_allowed']) for r in reg]
    print(f'\nband component alone: mean {st.mean(bp):.2f}  median {st.median(bp):.0f}  sd {st.pstdev(bp):.2f}')
    print('  team-games earning <= 0 from points allowed: %.1f%%' % (100 * sum(1 for x in bp if x <= 0) / len(bp)))
    sc = [nfl_score(r) for r in reg]
    print(f'\nfull NFL-style DEF score: mean {st.mean(sc):.2f}  median {st.median(sc):.0f}  sd {st.pstdev(sc):.2f}  '
          f'p10 {pct(sc,10):.0f}  p90 {pct(sc,90):.0f}  min {min(sc)}  max {max(sc)}')
    print('  negative games: %.1f%%   band share of mean score: %.0f%%'
          % (100 * sum(1 for x in sc if x < 0) / len(sc), 100 * st.mean(bp) / st.mean(sc)))
    print('  by segment:', {s: round(st.mean([nfl_score(r) for r in seg[s]]), 2) for s in SEGMENTS})
    totals = collections.defaultdict(float)
    for r in reg:
        totals[(r['season'], r['team'])] += nfl_score(r)
    v = list(totals.values())
    print(f'  team-season totals: mean {st.mean(v):.1f}  sd {st.pstdev(v):.1f}  range {min(v):.0f}-{max(v):.0f}')
    top = sorted(totals.items(), key=lambda kv: -kv[1])
    print('  top 5:', [(f'{t} {y}', round(x)) for (y, t), x in top[:5]])
    print('  bottom 5:', [(f'{t} {y}', round(x)) for (y, t), x in top[-5:]])
    share = [100 * sum(nfl_score(r) for r in rs if r['segment'] == 'FCS') / sum(nfl_score(r) for r in rs)
             for rs in ([r for r in reg if (r['season'], r['team']) == k] for k in totals)
             if any(r['segment'] == 'FCS' for r in rs) and sum(nfl_score(r) for r in rs) > 0]
    print('  for teams with an FCS game, that one game is %.1f%% of the season DEF total (median %.1f%%, max %.1f%%)'
          % (st.mean(share), st.median(share), max(share)))

    print('\n=== 5. CANDIDATE BAND SETS (frequency on college data) ===')
    srt = sorted(pa)
    septile = [srt[int((len(srt) - 1) * k / 7)] for k in range(1, 7)] + [10**9]
    for name, cuts in (('NFL standard', [0, 6, 13, 20, 27, 34, 10**9]),
                       ('NFL + 7', [0, 13, 20, 27, 34, 41, 10**9]),
                       ('even-ish college', [0, 9, 16, 23, 30, 40, 10**9]),
                       ('septile-matched', septile)):
        labels = (['0' if cuts[0] == 0 else f'<={cuts[0]}']
                  + [f'{cuts[i-1]+1}-{cuts[i]}' for i in range(1, len(cuts) - 1)] + [f'{cuts[-2]+1}+'])
        out, prev = [], -1
        for c, lab in zip(cuts, labels):
            out.append(f'{lab}:{sum(1 for r in reg if prev < r["points_allowed"] <= c)/len(reg):.1%}')
            prev = c
        print(f'{name:<18}', ' '.join(out))

    print('\n=== 6. FIELD-SEMANTICS CHECKS ===')
    # Each row already carries the opponent's offensive giveaways, so the
    # identity is checked within a row, not across the pair.
    allr = reg + post
    n = len(allr)
    ok_i = sum(1 for r in allr if r['def_interceptions'] == r['opp_ints_thrown'])
    ok_f = sum(1 for r in allr if r['fumbles_recovered'] == r['opp_fumbles_lost'])
    print(f'rows: {n}')
    print(f'  passesIntercepted == opponent `interceptions` (INTs thrown): {ok_i}/{n} ({ok_i/n:.1%})')
    print(f'  fumblesRecovered  == opponent fumblesLost:                  {ok_f}/{n} ({ok_f/n:.1%})')
    excess = collections.Counter(r['fumbles_recovered'] - r['opp_fumbles_lost'] for r in allr)
    print('  fumblesRecovered - opponent fumblesLost:', sorted(excess.items()))
    fr = sum(r['fumbles_recovered'] for r in allr)
    fl = sum(r['opp_fumbles_lost'] for r in allr)
    print(f'  aggregate fumblesRecovered {fr} vs actual takeaways {fl} (+{100*(fr/fl-1):.1f}%)')
    print('  int_tds <= defensive_tds:', f"{sum(1 for r in allr if r['int_tds'] <= r['defensive_tds'])}/{n}")
    print('  half-values present: sacks %.1f%% of rows, tackles_for_loss %.1f%%'
          % (100*sum(1 for r in allr if float(r['sacks']) % 1)/n,
             100*sum(1 for r in allr if float(r['tackles_for_loss']) % 1)/n))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
