from src.plots.from_csv import NATURE, Plots

plot = Plots("wdt_normal_c1_400.json", "20260203T1606")
colors = {dataset.functions_str(): NATURE[i] for i, dataset in enumerate(plot.finetuner.datasets)}
labels = [dataset.functions_str() for dataset in plot.finetuner.datasets]
plot.accuracy_per_epoch(colors, labels)
plot.loss_per_epoch(colors, labels)
