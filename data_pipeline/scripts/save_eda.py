"""Save a cleaned panel, clear charts and an EDA summary without changing source data."""
import argparse
import hashlib
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
try:
    from .clean_data import clean_data
except ImportError:
    from clean_data import clean_data


def save_eda(output):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory is not empty; choose a new directory to preserve previous work.')
    output.mkdir(parents=True, exist_ok=True)
    panel = clean_data(impute_national_monthly=True)
    filename = output / 'cleaned_panel.csv'
    panel.to_csv(filename, index=False)
    plt.style.use('default')
    monthly = panel.groupby('month')[['rainfall_mm', 'ndvi_mean']].mean()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(monthly.index, monthly.rainfall_mm, color='#79a879')
    ax.set(xlabel='Calendar month', ylabel='Mean monthly rainfall (mm)', title='Rainfall seasonality in the packaged panel')
    ax.set_xticks(range(1, 13)); fig.tight_layout(); fig.savefig(output / 'rainfall_by_month.png', dpi=140); plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(monthly.index, monthly.ndvi_mean, marker='o', color='#2b6842')
    ax.set(xlabel='Calendar month', ylabel='Mean NDVI', title='Vegetation seasonality in the packaged panel')
    ax.set_xticks(range(1, 13)); fig.tight_layout(); fig.savefig(output / 'ndvi_by_month.png', dpi=140); plt.close(fig)
    missing = {col: int(panel[col].sum()) for col in panel if col.endswith('_imputed')}
    annual = panel.groupby('year')['ndvi_mean'].mean()
    text = f'''# Packaged panel: exploratory analysis

- Rows: {len(panel):,}; counties: {panel.county.nunique()}; period: {panel.year_month.min()} to {panel.year_month.max()}.
- Cleaned panel SHA-256: `{hashlib.sha256(filename.read_bytes()).hexdigest()}`.
- Explicit same-year/month national mean imputation counts: {missing}.
- Missing climate values after imputation: {int(panel[['ndvi_mean', 'temp_mean_c', 'rainfall_mm', 'soil_moisture']].isna().sum().sum())}.
- Lowest and highest unweighted annual mean NDVI: {annual.idxmin()} ({annual.min():.3f}) and {annual.idxmax()} ({annual.max():.3f}).

![Average rainfall by calendar month](rainfall_by_month.png)

![Average vegetation greenness by calendar month](ndvi_by_month.png)

Both charts are unweighted means of the checked-in county-month panel. They describe that dataset, not measured crop losses or forage availability. Source acquisition and licenses have not been independently verified; imputed soil values are not measurements. This descriptive analysis cannot establish causes or forecast performance.
'''
    (output / 'EDA_ANALYSIS.md').write_text(text, encoding='utf-8')
    print(f'Saved {len(panel)} rows, charts and analysis to {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    save_eda(parser.parse_args().output)
