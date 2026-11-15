from scipy import stats

def correlacao(x, y, alpha=0.05):
    normal = stats.shapiro(x).pvalue > alpha and stats.shapiro(y).pvalue > alpha
    teste = stats.pearsonr if normal else stats.spearmanr
    r, p = teste(x, y)
    return dict(metodo="pearson" if normal else "spearman", r=float(r), p=float(p),
                n=len(x), significativo=bool(p < alpha))
