"""Save descriptive charts of reported county maize outcomes; never overwrite."""
import argparse
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data_pipeline/data/external/knbs_candidate/maize_outcomes_clean.csv'


def save(out):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output is not empty.')
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA)
    valid = df[df.quality_flag == 'ok']
    years = valid.groupby('year')['yield_tonnes_per_ha'].agg(['median', 'count'])
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(years.index.astype(str), years['median'], color='#618f62')
    ax.set(xlabel='Year', ylabel='Median county yield (tonnes/ha)', title='Reported county maize yields')
    fig.tight_layout(); fig.savefig(out / 'maize_median_yield.png', dpi=140); plt.close(fig)
    summary = (f"# Reported maize outcome exploration\n\n"
               f"The mirrored workbook contains {len(df)} county-year rows for 47 counties across 2012–2018 and 2020; "
               f"2019 is missing. {len(valid)} rows pass the basic area and consistency checks; "
               f"{len(df)-len(valid)} are flagged, not corrected.\n\n"
               f"The chart gives each county equal weight and is not a national production-weighted yield. "
               f"The reported yield is a historical crop outcome, not a loss or real-time risk. Source and redistribution rights require independent verification.\n\n"
               f"![Median maize yield](maize_median_yield.png)\n")
    (out / 'EDA_ANALYSIS.md').write_text(summary, encoding='utf-8')
    print(f'Saved analysis to {out}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    save(parser.parse_args().output)
