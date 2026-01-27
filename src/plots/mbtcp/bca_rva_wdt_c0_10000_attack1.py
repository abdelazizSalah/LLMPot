from src.plots.from_csv import NATURE, Plots


plot = Plots("wdt-dataset-mbtcp-protocol-emulation-attack1-c0-10000.json", "20260126T1343")
colors = {dataset.functions_str(): NATURE[i] for i, dataset in enumerate(plot.finetuner.datasets)}
labels = [dataset.functions_str() for dataset in plot.finetuner.datasets]
plot.accuracy_per_epoch(colors, labels)
plot.loss_per_epoch(colors, labels)

