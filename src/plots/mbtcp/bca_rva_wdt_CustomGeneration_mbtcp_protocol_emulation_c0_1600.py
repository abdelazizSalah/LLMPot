from src.plots.from_csv import NATURE, Plots

plot = Plots("CustomGeneration-mbtcp-protocol-emulation-c0-1600.json", "20260318T0035")
colors = {dataset.functions_str(): NATURE[i] for i, dataset in enumerate(plot.finetuner.datasets)}
labels = [dataset.functions_str() for dataset in plot.finetuner.datasets]
plot.accuracy_per_epoch(colors, labels)
plot.loss_per_epoch(colors, labels)
