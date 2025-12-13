'''
@Reviewer: Abdelaziz Neamatallah
@Date: 13.12.25
@Description: Trying to analyze this script to understand what is its functionality.
'''

import argparse
import os

import pandas as pd

from src.utilities.utils import load_cfg


def main(model: str, experiment: str):
    # Loading the finetuner model with the specified model and experiment configuration
    finetuner_model = load_cfg(model, experiment)

    print("model, size, accuracy/validator, accuracy/exact")
    # creating dataframe to store matching rows
    matching_df  = pd.DataFrame()

    # iterating through each dataset in the finetuner model
    for dataset in finetuner_model.datasets:
        # assigning the current dataset to the finetuner model
        finetuner_model.current_dataset = dataset

        # list all versions in the experiments, and neglect the csv folder -> [20240918T1049,20240918T1110, 20240918T1717, YYYYMMDD*T*HHMM]
        versions = os.listdir(finetuner_model.experiment_dataset_result_path)
        versions = [folder for folder in versions if not folder == 'csv']
        print("Found versions:", versions)
        # iterating through each version of the dataset
        for version in versions:
            # assigning the current version to the finetuner model datetime.
            finetuner_model.start_datetime = version

            # getting the metris for the current experiment
            print(f"Loading metrics for model: {model}, version: {version}, dataset size: {dataset.size}, from path: {finetuner_model.experiment_csv_metrics_path}")
            with open(f"{finetuner_model.experiment_csv_metrics_path}") as metrics:
                new_metrics = pd.read_csv(metrics)
                new_metrics['size'] = dataset.size
                new_metrics['version'] = version
                print(f'new metrics columns: {new_metrics.columns}')
                print(f'new metrics size: {new_metrics.size}')
                print(f'new metrics version: {new_metrics.version}')
            #! error is here.
            # checkpoint_files = os.listdir(f"{finetuner_model.experiment_instance_result_path}/checkpoints/")
            # best_checkpoints = [file for file in checkpoint_files if file.startswith('best-')][0]
            # best_checkpoints = [file for file in checkpoint_files][0]
            # best_epoch = best_checkpoints.split('-')[1].split('.')[0]
            best_row = new_metrics.loc[
                new_metrics['csv-val_loss_epoch'].idxmin()
            ]

            best_epoch = int(best_row.at['csv-epoch'])




            matching_row = new_metrics[new_metrics['csv-epoch'] == int(best_epoch)]
            matching_row = matching_row[matching_row['csv-accuracy/validator'].notna()]
            print('--- Matching Row ---')
            print(f"current model {model}, with {version}, and size {dataset.size}, matching validator{matching_row['csv-accuracy/validator'].values[0]}, matching exact {matching_row['csv-accuracy/exact'].values[0]}")

            matching_df = pd.concat([matching_df, matching_row])



        pd.set_option('display.max_rows', None)
        # print(matching_df)

    # group them by size and calculate mean and std
    grouped = matching_df.groupby(['size']).agg({
        'csv-accuracy/validator': ['mean', 'std'],
        'csv-accuracy/exact': ['mean', 'std'],
        'csv-epoch': ['mean', 'std'],
    }).reset_index()

    # print the results in latex table format
    for size, row in grouped.iterrows():
        validator_mean = row[('csv-accuracy/validator', 'mean')]
        validator_std = row[('csv-accuracy/validator', 'std')]
        exact_mean = row[('csv-accuracy/exact', 'mean')]
        exact_std = row[('csv-accuracy/exact', 'std')]
        epoch_mean = row[('csv-epoch', 'mean')]
        epoch_std = row[('csv-epoch', 'std')]

        print(f"{size} & ${exact_mean * 100:.2f} \pm {exact_std * 100:.2f}$ & ${validator_mean * 100:.2f} \pm {validator_std * 100:.2f}$ & ${epoch_mean:.0f} \pm {epoch_std:.0f}$")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-model', default="byt5-base", required=False)
    parser.add_argument('-cfg', default="mbtcp-protocol-emulation.json", required=False)
    args = parser.parse_args()
    main(args.model, args.cfg)
