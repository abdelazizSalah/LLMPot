'''
@Reviewer: Abdelaziz Neamatallah
@Date: 15.12.25
@Description: Reviewing the plots class to understand how they generate the plots for the generalization experiment.
'''

# importing important libraries
import json
import os
from typing import List

import plotly.express as px

import pandas as pd
import plotly.graph_objects as go

from src.cfg import EXPERIMENTS, ASSETS
from src.finetune.model.finetuner_model import FinetunerModel

import plotly.io as pio
pio.kaleido.scope.mathjax = None


# defining static variables
FONT_FAMILY = "Serif"
SYMBOL = ['cross', 'diamond-open', 'circle-dot', 'triangle-up-open', 'diamond-open', 'star-triangle-up']

VIOLET_PALETTE = ['#caa8f5', '#592e83', '#b27c66']
NATURE = ['#C03221', '#87BCDE', '#EDB88B', '#545E75', '#3F826D', '#88498F']


# Plot Class:
class Plots:
    '''
        Helper class that loads an experiment config using its timestamp, then generates plots
        from its saved metric CSVs.

    '''
    def __init__(self, experiment: str, timestamp: str):
        '''
            Constructor takes experiment name and timestamp as input to load the correct experiment.
        '''

        # defining metrics to be used in plots
        self._metrics = ['csv-accuracy/validator', 'csv-accuracy/exact']
        self._test_metrics = ['accuracy/validator', 'accuracy/exact']

        # loading finetuner model configured with the given experiment and timestamp
        self._finetuner = self._load_experiment(experiment, timestamp)

    @property
    def finetuner(self):
        # returning the used finetuner model
        return self._finetuner

    @staticmethod
    def get_symbol(key: str, keys: List, options: List):
        # builds a dictionary mapping each option to a key, then returns the symbol for the given key
        return {key: options[i] for i, key in enumerate(keys)}[key] #! reuse of key is confusing. (can be chosen_key)

    @staticmethod
    def darken_hex_color(hex_color, reduction_percentage=30):
        '''
            Takes a hex color like #EDB88B.
            Parses its RGB channels as integers.
            Reduces each channel by percentage.
            Returns the new hex color.
        '''
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:], 16)

        r = max(0, r - (r * reduction_percentage // 100))
        g = max(0, g - (g * reduction_percentage // 100))
        b = max(0, b - (b * reduction_percentage // 100))

        return "#{:02X}{:02X}{:02X}".format(r, g, b)

    @staticmethod
    def _load_experiment(experiment: str, timestamp: str):
        '''
            1. opens the experiment config file located under experiments/byt5-small/{experiment}
            2. reads file text and parses it into python dict via json.loads
            3. initializes FinetunerModel with the experiment name and config dict unpacked as kwargs
            4. sets the finetuner model's start_datetime to the given timestamp
            5. returns the configured finetuner model
        '''
        with open(f"{EXPERIMENTS}/byt5-small/{experiment}", "r") as cfg:
            config = cfg.read()
            config = json.loads(config)
            finetuner_model = FinetunerModel(experiment=experiment, **config)
            finetuner_model.start_datetime = timestamp

            return finetuner_model



    def accuracy_with_random_dataset(self):
        '''
            Generates bar plots for BCA and RVA metrics using test datasets with different (same vs different) PLC configurations.
            Fig 7 in the paper.
        '''
        print('generating accuracy with random dataset plot...')
        # create empty dataframe
        dfs = pd.DataFrame()

        # iterate over all datasets in the finetuner model (defined in json)
        for dataset in self._finetuner.datasets:
            # set the current dataset in the finetuner model
            self._finetuner.current_dataset = dataset

            # if the metrics CSV file does not exist, raise FileNotFoundError
            if not os.path.exists(self.finetuner.experiment_csv_metrics_path):
                raise FileNotFoundError(f"{self.finetuner.experiment_csv_metrics_path} not found")

            # read the metrics CSV file into a dataframe
            df = pd.read_csv(self.finetuner.experiment_csv_metrics_path)

            ## add additional columns to the dataframe for analysis

            # add new column 'test_dataset' describing the PLC server configuration (datablock for s7comm, coils for mbtcp)
            df.loc[:, 'test_dataset'] = dataset.server.datablock if hasattr(dataset.server, "datablock") else dataset.server.coils # coils names in s7comm and mbtcp

            # add 'plc_cfg' column to indicate if the test dataset has same size (40) as the training dataset or different.
            df.loc[:, 'plc_cfg'] = df['test_dataset'].apply(lambda x: "same" if x == 40 else "different")

            # add 'size' and 'functions' columns extracted from the dataset name
            df.loc[:, 'size'] = df['dataset'].apply(lambda x: f"{x.split('-')[3]}")

            # add 'functions' column extracted from the dataset name
            df.loc[:, 'functions'] = df['dataset'].apply(lambda x: f"{x.split('-')[4].split('f')[1]}")# takes the part after f
            # append it to the main dataframe
            dfs = pd.concat([dfs, df])

        # iterate over the test metrics (BCA and RVA)
        for metric in self._test_metrics:
            validation_type = metric.split("/")[1]
            df = dfs.query("functions == '1_5_15_3_6_16'") # filter to these functions only.

            # create grouped bar chart
            # x-axis: dataset size
            # y-axis: metric (BCA or RVA) -> chosen metric
            # color: plc_cfg (same vs different)
            # group mode so bars appear side by side.
            fig = px.bar(df, x='size', y=metric, color='plc_cfg', barmode='group',
                         color_discrete_sequence=['#EDB88B', '#545E75'])

            # set titles, margins, fonts, and variable names.
            fig.update_layout(
                barmode='group',
                xaxis_title='<b>Model</b>',
                yaxis_title='<b>BCA</b>' if validation_type == 'exact' else '<b>RVA</b>',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=0, r=0, b=0, t=0, pad=0),
                font=dict(family=FONT_FAMILY, size=34, color="Black"),
                xaxis=dict(type='category', categoryorder='array'),
                legend=dict(yanchor="bottom", y=0.7, xanchor="right", x=0.25, orientation='v', font=dict(family=FONT_FAMILY, size=28)),

            )

            # Add axis lines and dotted grid
            fig.update_xaxes(showline=True, linewidth=1.5, linecolor='gray', gridcolor='gray', gridwidth=1, griddash="dot",
                             zeroline=False, zerolinewidth=3, zerolinecolor='black',
                             )

            # Set y-axis range from 0 to 1.002 to looks clean
            fig.update_yaxes(showline=True, linewidth=1.5, linecolor='gray',gridcolor='gray', gridwidth=1, griddash="dot",
                             zeroline=False, zerolinewidth=3, zerolinecolor='black', range=[0, 1.002]
                             )

            # fig.show()

            # save the figures at the assets directory under the experiment name
            os.makedirs(f"{ASSETS}/{self._finetuner.experiment}/", exist_ok=True)
            fig.write_image(f"{ASSETS}/{self._finetuner.experiment}/{validation_type}.pdf")

    def accuracy_per_epoch(self, colors: dict, labels: List, max_epochs: int = 1000):
        '''
            Fig 6 in the paper.



        '''

        # create empty dataframe
        dfs = pd.DataFrame()
        # iterate over all datasets in the finetuner model (defined in json)
        for dataset in self._finetuner.datasets:
            # set the current dataset in the finetuner model
            self._finetuner.current_dataset = dataset
            # if the metrics CSV file does not exist, raise FileNotFoundError
            if not os.path.exists(self.finetuner.experiment_csv_metrics_path):
                raise FileNotFoundError(f"{self.finetuner.experiment_csv_metrics_path} not found")

            # read the metrics CSV file into a dataframe
            df = pd.read_csv(self.finetuner.experiment_csv_metrics_path)

            # remove unnecessary columns
            df.drop(columns=['csv-val_loss_step', 'csv-val_loss_epoch', 'csv-train_loss_step', 'csv-train_loss_epoch'], inplace=True)

            # drop rows with NaN values in the accuracy columns
            df.dropna(subset=["csv-accuracy/validator", "csv-accuracy/exact"], inplace=True)

            # add 'dataset' with the name of the dataset
            df.loc[:, 'dataset'] = str(dataset)

            # add to the main dataframe
            dfs = pd.concat([dfs, df])

        # iterate over the metrics (BCA and RVA)
        for metric in self._metrics:

            # determine validation type (exact or validator)
            validation_type = metric.split("/")[1]

            # create a new figure
            fig = go.Figure()

            # iterate over all datasets in the finetuner model
            for index, dataset in enumerate(self._finetuner.datasets):
                self._finetuner.current_dataset = dataset

                # filter the main dataframe for the current dataset
                df = dfs.query(f"dataset == '{dataset}'")

                # add a smooth line using:
                # x: epoch column
                # y: the selected metric column (BCA or RVA)
                # legend name comes from the labels[index]
                # line color comes from the colors dict
                fig.add_trace(go.Scatter(x=df['csv-epoch'], y=df[metric],
                                         mode='lines',
                                         name=labels[index],
                                         line=dict(width=5, color=colors[labels[index]], shape='spline'),
                                         )
                              )

            fig.update_layout(
                xaxis_title='<b>Epoch</b>',
                yaxis_title='<b>BCA</b>' if validation_type == 'exact' else '<b>RVA</b>',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=0, r=0, b=0, t=0, pad=0),
                font=dict(family=FONT_FAMILY, size=32, color="Black"),
                legend=dict(yanchor="bottom", y=1, xanchor="right", x=1, orientation='h', font=dict(family=FONT_FAMILY, size=28)),
                )

            fig.update_xaxes(showline=True, linewidth=1.5, linecolor='gray', gridcolor='gray', gridwidth=1, griddash="dot",
                             zeroline=False, zerolinewidth=3, zerolinecolor='black',
                             )
            fig.update_yaxes(showline=True, linewidth=1.5, linecolor='gray',gridcolor='gray', gridwidth=1, griddash="dot",
                             zeroline=False, zerolinewidth=3, zerolinecolor='black', range=[0, 1.002]
                             )

            # fig.show()

            # save the figures at the assets directory under the experiment name
            os.makedirs(f"{ASSETS}/{self._finetuner.experiment}/", exist_ok=True)
            fig.write_image(f"{ASSETS}/{self._finetuner.experiment}/{validation_type}.pdf")

    def loss_per_epoch(self, colors: dict, labels: List, log_y_axis: bool = True):
        '''
            Fig 8 in the paper.
        '''
        dfs = pd.DataFrame()
        for dataset in self._finetuner.datasets:
            self._finetuner.current_dataset = dataset
            if not os.path.exists(self.finetuner.experiment_csv_metrics_path):
                continue
            df = pd.read_csv(self.finetuner.experiment_csv_metrics_path)
            df.drop(columns=['csv-val_loss_step', 'csv-train_loss_step', 'csv-accuracy/validator', 'csv-accuracy/exact', 'step'], inplace=True)

            val_df = df.dropna(subset=["csv-val_loss_epoch"]).drop(columns=["csv-train_loss_epoch"])
            train_df = df.dropna(subset=["csv-train_loss_epoch"]).drop(columns=["csv-val_loss_epoch"])

            df = pd.merge(val_df, train_df, on="csv-epoch", how="inner")
            df.loc[:, 'dataset'] = str(dataset)
            df.loc[:, 'functions'] = dataset.functions_str()
            dfs = pd.concat([dfs, df])

        fig = go.Figure()
        for index, dataset in enumerate(self._finetuner.datasets):
            self._finetuner.current_dataset = dataset
            df = dfs.query(f"dataset == '{dataset}'")
            fig.add_trace(go.Scatter(x=df['csv-epoch'], y=df['csv-val_loss_epoch'],
                                     mode='lines',
                                     name=f"v-{labels[index]}",
                                     line=dict(width=5, color=colors[labels[index]], shape='spline', dash="dot"),
                                     legend="legend1",
                                     showlegend=False
                                     )
                          )

            fig.add_trace(go.Scatter(x=df['csv-epoch'], y=df['csv-train_loss_epoch'],
                                     mode='lines',
                                     name=labels[index],
                                     line=dict(width=5, color=colors[labels[index]], shape='spline'),
                                     legend="legend2"
                                     )
                          )

        fig.update_layout(
            xaxis_title='<b>Epoch</b>',
            yaxis_title='<b>Loss</b>',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, b=0, t=0, pad=0),
            font=dict(family=FONT_FAMILY, size=32, color="Black"),
            legend1=dict(yanchor="bottom", y=0.8, xanchor="right", x=1, orientation='h', font=dict(family=FONT_FAMILY, size=24)),
            legend2=dict(yanchor="bottom", y=0.9, xanchor="right", x=1, orientation='h', font=dict(family=FONT_FAMILY, size=24))
            )

        if log_y_axis:
            fig.update_layout(yaxis=dict(type='log', dtick=1))

        fig.update_xaxes(showline=True, linewidth=1.5, linecolor='gray', gridcolor='gray', gridwidth=1, griddash="dot",
                         zeroline=False, zerolinewidth=3, zerolinecolor='black',
                         )
        fig.update_yaxes(showline=True,linewidth=1.5, linecolor='gray',gridcolor='gray', gridwidth=1, griddash="dot",
                         zeroline=False, zerolinewidth=3, zerolinecolor='black',
                         )

        fig.add_annotation(text='solid: training loss, dot: validation loss',
                    align='left',
                    showarrow=False,
                    xref='paper',
                    yref='paper',
                    x=1,
                    y=0.9,
                    bordercolor='gray',
                    borderwidth=2)

        # fig.show()

        os.makedirs(f"{ASSETS}/{self._finetuner.experiment}/", exist_ok=True)
        fig.write_image(f"{ASSETS}/{self._finetuner.experiment}/losses.pdf")
